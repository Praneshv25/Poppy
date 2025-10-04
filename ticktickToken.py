import http.server
import socketserver
import urllib.parse
import webbrowser
import requests
import base64
import os
import json
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration (prefer environment variables; fall back to constants)
CLIENT_ID = os.getenv("TICKTICK_CLIENT_ID")
CLIENT_SECRET = os.getenv("TICKTICK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TICKTICK_REDIRECT_URI", "http://localhost:8080/callback")
SCOPES = os.getenv("TICKTICK_SCOPES", "tasks:read tasks:write")

# Token cache location
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "meLlamo")
CACHE_PATH = os.path.join(CONFIG_DIR, "ticktick_token.json")


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    return "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


def _load_cached_token() -> dict | None:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r") as f:
            data = json.load(f)
        return data
    except Exception:
        return None


def _save_cached_token(token_json: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Compute expiry instant (epoch seconds), subtract small skew for safety
    expires_in = token_json.get("expires_in")
    if isinstance(expires_in, (int, float)):
        token_json["expires_at"] = int(time.time() + max(0, expires_in - 60))
    with open(CACHE_PATH, "w") as f:
        json.dump(token_json, f)


def _token_valid(token_json: dict) -> bool:
    expires_at = token_json.get("expires_at")
    if not expires_at:
        return False
    return time.time() < float(expires_at)


def _refresh_token(refresh_token: str) -> dict:
    resp = requests.post(
        "https://ticktick.com/oauth/token",
        headers={
            "Authorization": _basic_auth_header(CLIENT_ID, CLIENT_SECRET),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    # Preserve refresh_token if not returned
    if "refresh_token" not in data:
        data["refresh_token"] = refresh_token
    _save_cached_token(data)
    return data


def _interactive_auth() -> dict:
    code_holder = {"code": None}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.urlparse(self.path)
            if q.path == "/callback":
                params = urllib.parse.parse_qs(q.query)
                code_holder["code"] = params.get("code", [None])[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Auth received. You can close this tab.")
            else:
                self.send_response(404)
                self.end_headers()

    auth_url = (
        "https://ticktick.com/oauth/authorize?"
        f"scope={urllib.parse.quote(SCOPES)}&client_id={CLIENT_ID}"
        f"&state=state&redirect_uri={urllib.parse.quote(REDIRECT_URI)}&response_type=code"
    )

    # Expect REDIRECT_URI to match your app config. If port is busy, this will fail.
    parsed = urllib.parse.urlparse(REDIRECT_URI)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8080

    with socketserver.TCPServer((host, port), Handler) as httpd:
        webbrowser.open(auth_url)
        while not code_holder["code"]:
            httpd.handle_request()

    code = code_holder["code"]
    resp = requests.post(
        "https://ticktick.com/oauth/token",
        headers={
            "Authorization": _basic_auth_header(CLIENT_ID, CLIENT_SECRET),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _save_cached_token(data)
    return data


def get_access_token(force_reauth: bool = False) -> str:
    """Return a valid access token, using cache/refresh, or browser auth if needed."""
    if not force_reauth:
        cached = _load_cached_token()
        if cached and _token_valid(cached):
            return cached["access_token"]
        if cached and cached.get("refresh_token"):
            try:
                refreshed = _refresh_token(cached["refresh_token"])
                return refreshed["access_token"]
            except Exception:
                pass
    data = _interactive_auth()
    return data["access_token"]


if __name__ == "__main__":
    # For manual use: prints the access token
    print(get_access_token())