import speech_recognition as sr
import pyttsx3
import google.genai as genai
from google.genai.types import GenerateContentConfig, SafetySetting, HarmCategory, HarmBlockThreshold
import cv2
import base64

# === VOICE SETUP ===
engine = pyttsx3.init()
voices = engine.getProperty('voices')
rate = engine.getProperty('rate')
volume = engine.getProperty('volume')

# === GEMINI CLIENT SETUP ===
client = genai.Client(api_key="AIzaSyDosNbIypDa8kk3LLIWrVNGPwYkzj9V0UE")  # <-- Replace with your Gemini API key

generation_config = GenerateContentConfig(
    temperature=0.8,
    top_p=0.9,
    top_k=40,
    max_output_tokens=8192,
)

# safety_settings = [
#     SafetySetting(HarmCategory.HARM_CATEGORY_HARASSMENT, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
#     SafetySetting(HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
#     SafetySetting(HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
#     SafetySetting(HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
# ]

# === SYSTEM PROMPT ===
# Load system prompt from an external file
try:
    with open('libra_system_prompt.txt', 'r') as f:
        system_prompt = f.read()
except FileNotFoundError:
    print("Error: libra_system_prompt.txt not found. Please create the file with the system prompt content.")
    system_prompt = "" # Fallback to empty string or a default prompt

# === INITIAL STATE ===
conversation_history = []
listening = True
sending_to_gemini = False
wake_word = "gemini"
exit_words = ["exit", "stop", "quit", "bye", "goodbye"]

# === CAMERA SETUP ===
cam = cv2.VideoCapture(0)

def get_frame_data():
    ret, frame = cam.read()
    if not ret:
        print("Failed to capture frame.")
        return None
    resized = cv2.resize(frame, (224, 224))
    _, buffer = cv2.imencode('.jpg', resized)
    return base64.b64encode(buffer).decode('utf-8')

# === GEMINI REQUEST FUNCTION ===
def get_response(user_input):
    global conversation_history

    frame_data = get_frame_data()
    if not frame_data:
        return "Camera input failed."

    vision_parts = [
        {"text": "User command: " + user_input},
        {"text": "Here is the current visual scene."},
        {"inline_data": {
            "mime_type": "image/jpeg",
            "data": frame_data
        }}
    ]

    conversation_history.append({"role": "user", "parts": vision_parts})

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=conversation_history,
        # config=generation_config,
        config=GenerateContentConfig(
            system_instruction= system_prompt)
        # safety_settings=safety_settings
    )

    gemini_reply = response.text
    print("Gemini:", gemini_reply)

    conversation_history.append({"role": "model", "parts": [{"text": gemini_reply}]})
    return gemini_reply

# === MAIN LOOP ===
recognizer = sr.Recognizer()

while listening:
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=7.0)
            response = recognizer.recognize_google(audio)
            print("Heard:", response)

            if any(word in response.lower() for word in exit_words):
                sending_to_gemini = False
                print("Stopped sending responses to Gemini.")
                continue

            if wake_word in response.lower() and not sending_to_gemini:
                sending_to_gemini = True
                print("Wake word detected. Resumed Gemini interaction.")
                continue

            if sending_to_gemini:
                reply = get_response(response)
                engine.setProperty('rate', 200)
                engine.setProperty('volume', volume)
                engine.setProperty('voice', voices[0].id)
                engine.say(reply)
                engine.runAndWait()

        except sr.UnknownValueError:
            print("Didn't recognize anything.")
        except sr.RequestError as e:
            print(f"Speech Recognition error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
