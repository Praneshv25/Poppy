from perplexity import Perplexity
import google.genai as genai
from google.genai.types import GenerateContentConfig

from dotenv import load_dotenv
import os
import time
import json
import re
import atexit
from pathlib import Path
from typing import Dict, Tuple

load_dotenv(override=True)
client_perplexity = Perplexity(api_key=os.getenv("PERPLEXITY_API_KEY"))

client = genai.Client(api_key=os.getenv("API_KEY"))


def _extract_text(response) -> str:
    """Safely extract text from Gemini 3 response, filtering out thought_signature parts."""
    try:
        parts = response.candidates[0].content.parts
        if not parts:
            return ""
        text_parts = []
        for part in parts:
            if hasattr(part, "text") and part.text is not None:
                text_parts.append(part.text)
        return "".join(text_parts).strip()
    except (IndexError, AttributeError, TypeError):
        try:
            return (response.text or "").strip()
        except Exception:
            return ""


# === CACHE CONFIGURATION ===
CACHE_FILE = Path(__file__).parent / "query_complexity_cache.json"

# Pattern-based cache for common query types (instant, no API calls)
QUERY_PATTERNS: Dict[str, int] = {
    # Simple fact patterns - 100 tokens
    r'\b(what|when|where) (is|are|was) (the|a)\b.*\b(time|date|temperature|score)\b': 100,
    r'\bweather\b.*\b(today|tomorrow|tonight)\b': 100,
    r'\bwhat time\b': 100,
    r'\bwhat channel\b': 100,
    
    # Moderate complexity - 150 tokens
    r'\b(who|which) (is|are) (playing|performing)\b': 150,
    r'\bschedule for\b': 150,
    r'\bnext (game|match|event)\b': 150,
    
    # Complex/multiple items - 250 tokens
    r'\ball (games|matches|events)\b.*\b(today|tonight|this week)\b': 250,
    r'\b(full|complete) schedule\b': 250,
    r'\bwhat games\b.*\b(today|tonight)\b': 250,
    r'\bmultiple\b.*\b(games|events|matches)\b': 250,
}

# In-memory cache (loaded from disk on startup)
_recent_query_cache: Dict[str, Dict] = {}
_cache_max_size = 100
_cache_modified = False  # Track if cache needs saving

try:
    # Use absolute path relative to this file's location
    prompt_path = Path(__file__).parent / 'search_sys_prompt.txt'
    with open(prompt_path, 'r') as f:
        system_prompt = f.read()
except FileNotFoundError:
    print("Error: search_sys_prompt.txt not found. Please create the file with the system prompt content.")
    system_prompt = ""



generation_config = GenerateContentConfig(
    temperature=0.8,
    top_p=0.9,
    top_k=40,
    max_output_tokens=8192,
    system_instruction=system_prompt,
)


# === CACHE FUNCTIONS ===

def load_cache_from_disk():
    """Load cache from disk into memory on startup"""
    global _recent_query_cache
    
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                _recent_query_cache = json.load(f)
            print(f"[Cache] Loaded {len(_recent_query_cache)} entries from disk")
        except Exception as e:
            print(f"[Cache] Error loading cache: {e}, starting fresh")
            _recent_query_cache = {}
    else:
        print(f"[Cache] No existing cache file, starting fresh")
        _recent_query_cache = {}


def save_cache_to_disk():
    """Save in-memory cache to disk"""
    global _cache_modified
    
    if not _cache_modified:
        return  # No changes to save
    
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(_recent_query_cache, f, indent=2)
        _cache_modified = False
        print(f"[Cache] Saved {len(_recent_query_cache)} entries to disk")
    except Exception as e:
        print(f"[Cache] Error saving cache: {e}")


def get_query_fingerprint(query: str) -> str:
    """Create a fingerprint for similar queries"""
    fingerprint = re.sub(r'\b\d+\b', 'NUM', query.lower())
    fingerprint = re.sub(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', 'DAY', fingerprint)
    fingerprint = re.sub(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', 'MONTH', fingerprint)
    fingerprint = re.sub(r'\b(warriors|lakers|kings|bulls|heat|celtics|nets|sixers|pacers|suns|nuggets|[a-z]+ers)\b', 'TEAM', fingerprint)
    return fingerprint


def check_pattern_cache(query: str) -> Tuple[bool, int]:
    """Check if query matches any pre-defined patterns"""
    query_lower = query.lower()
    
    for pattern, token_limit in QUERY_PATTERNS.items():
        if re.search(pattern, query_lower):
            print(f"[Cache] Pattern match: {token_limit} tokens")
            return True, token_limit
    
    return False, 0


def check_recent_cache(query: str) -> Tuple[bool, int]:
    """Check if similar query was recently processed"""
    fingerprint = get_query_fingerprint(query)
    
    if fingerprint in _recent_query_cache:
        cache_entry = _recent_query_cache[fingerprint]
        token_limit = cache_entry['token_limit']
        
        # Update last accessed time (for LRU tracking)
        cache_entry['last_accessed'] = time.time()
        
        print(f"[Cache] Recent query match: {token_limit} tokens")
        return True, token_limit
    
    return False, 0


def cache_query_result(query: str, token_limit: int):
    """Store query result in recent cache and mark for disk sync"""
    global _recent_query_cache, _cache_modified
    
    fingerprint = get_query_fingerprint(query)
    
    _recent_query_cache[fingerprint] = {
        'token_limit': token_limit,
        'last_accessed': time.time(),
        'example_query': query  # Store one example for debugging
    }
    
    _cache_modified = True
    
    # Implement LRU: keep only most recent N items
    if len(_recent_query_cache) > _cache_max_size:
        # Sort by last_accessed and remove oldest
        sorted_entries = sorted(
            _recent_query_cache.items(),
            key=lambda x: x[1]['last_accessed']
        )
        # Remove oldest 10% to avoid frequent pruning
        num_to_remove = _cache_max_size // 10
        for fingerprint, _ in sorted_entries[:num_to_remove]:
            del _recent_query_cache[fingerprint]
        print(f"[Cache] Pruned {num_to_remove} old entries")


def determine_search_token_limit(query: str) -> int:
    """
    Use multi-level caching + Gemini to determine optimal token limit.
    
    Cache levels:
    1. Pattern cache (instant, regex-based)
    2. Persistent fingerprint cache (in-memory, loaded from disk)
    3. Gemini analysis (fallback for novel queries)
    """
    
    # Level 1: Check pattern cache
    found, token_limit = check_pattern_cache(query)
    if found:
        return token_limit
    
    # Level 2: Check persistent cache (in-memory)
    found, token_limit = check_recent_cache(query)
    if found:
        return token_limit
    
    # Level 3: Ask Gemini (cache miss)
    print(f"[Cache] Miss - querying Gemini for complexity analysis")
    
    analysis_prompt = f"""Analyze this search query and determine the optimal response length needed:

Query: "{query}"

Consider:
- Simple facts (weather, time, single game) → 100 tokens
- Moderate complexity (schedule with 2-3 items, comparison) → 150 tokens  
- Complex/multiple items (full day schedule, multiple games, detailed info) → 250 tokens

Respond with ONLY the number: 100, 150, or 250"""

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=analysis_prompt,
            config=GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=10,
            )
        )
        
        token_limit = int(_extract_text(response))
        
        if token_limit in [100, 150, 250]:
            cache_query_result(query, token_limit)
            print(f"[Gemini Router] Determined: {token_limit} tokens (cached)")
            
            # Save to disk immediately to ensure persistence
            # (Low overhead since this only runs on cache misses)
            save_cache_to_disk()
            
            return token_limit
        else:
            print(f"[Gemini Router] Unexpected value {token_limit}, defaulting to 150")
            return 150
            
    except Exception as e:
        print(f"[Gemini Router] Error: {e}, defaulting to 150")
        return 150


def extract_relevant_context(query, conversation_history):
    """
    Use Gemini to extract only relevant context from conversation history
    """
    print(f"[Context extraction] Conversation history: {conversation_history}")
    if not conversation_history or len(conversation_history) == 0:
        return None
    
    # Build a prompt asking Gemini to extract relevant context
    context_prompt = f"""Given the current user query: "{query}"

Extract ONLY the relevant information from the conversation history that would help answer this query. 
Return ONLY the key facts, names, or topics from previous messages. Keep it brief.
If no relevant context exists, return "None"

Conversation history:
{json.dumps(conversation_history[-4:], indent=2)}"""
    
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=context_prompt,
            config=GenerateContentConfig(
                temperature=0.3,  # Lower temperature for more focused extraction
                max_output_tokens=200,
            )
                
        )
        
        # Check if response has text content
        result = _extract_text(response)
        if not result:
            print("[Context extraction] No text in response")
            return None
        print(f"[Context extraction] Extracted: {result[:100]}...")
        return result if result.lower() != "none" else None
    except Exception as e:
        print(f"Error extracting context: {e}")
        return None


def validate_search_need(query, conversation_context=None):
    # Check if conversation_context is a list (conversation history) or string (old format)
    relevant_context = None
    validation_prompt = query
    
    if conversation_context:
        if isinstance(conversation_context, list):
            # Extract only relevant context from conversation
            relevant_context = extract_relevant_context(query, conversation_context)
            # Build validation prompt with full context to determine if search is needed
            validation_prompt = f"Previous conversation: {json.dumps(conversation_context[-2:], indent=2)}\n\nCurrent user query: {query}"
        else:
            # Old format: string context (backward compatibility)
            relevant_context = conversation_context
            validation_prompt = f"Previous conversation context: {conversation_context}\n\nCurrent user query: {query}"
    
    # Ask Gemini if search is needed (using full conversation context)
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=validation_prompt,
        config=generation_config
    )
    
    if "Yes" in _extract_text(response):
        # Build search query: only include context if it's actually relevant
        if relevant_context:
            # Context is relevant - enrich the search query
            search_query = f"{relevant_context}\n\n{query}"
            print(f"[Search] Using enriched query with context")
        else:
            # No relevant context - search with clean query
            search_query = query
            print(f"[Search] Using clean query (no relevant context)")
        
        return (True, search(search_query))
    else:
        return (False, "")


def search(query):
    """
    Perform web search with dynamically determined token limit based on query complexity
    """
    # Dynamically determine optimal token limit
    max_tokens = determine_search_token_limit(query)
    
    completion = client_perplexity.chat.completions.create(
        model="sonar",
        max_tokens=max_tokens,
        messages=[
            {"role": "user", "content": query}
        ],
        web_search_options={
            "user_location": {
                "country": "US",
                "region": "INDIANA",
                "city": "West Lafayette",
                "latitude": 40.427539,
                "longitude": -86.907739
            }
        }
    )

    return completion.choices[0].message.content


# === MODULE INITIALIZATION ===
# Load cache from disk when module is imported
load_cache_from_disk()

# Register cleanup handler to save cache on program exit
atexit.register(save_cache_to_disk)

# print("start")
# start_time = time.time()
# print(validate_search_need("When is the next Chargers game?"))
# print(time.time() - start_time)