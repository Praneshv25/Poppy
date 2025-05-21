from ollama import chat
from ollama import ChatResponse
import os
from google import genai
import voice
from ears import run_whisper_live_transcription
import difflib


def get_text_after_poppy(transcript: str, wake_word="friday", threshold=0.8):
    words = transcript.lower().split()
    for i, word in enumerate(words):
        similarity = difflib.SequenceMatcher(None, word, wake_word).ratio()
        if similarity >= threshold:
            return True, " ".join(words[i + 1:])
    return False, None


def listen_for_poppy(model_name="base"):
    while True:
        transcript_lines = run_whisper_live_transcription(model_name=model_name)
        print(transcript_lines)
        if not transcript_lines:
            continue
        print("package sent")
        full_transcript = " ".join(transcript_lines).lower()
        print(full_transcript)
        wake_detected, after_poppy = get_text_after_poppy(full_transcript)

        if wake_detected:
            print(after_poppy)

            if after_poppy:
                response: ChatResponse = chat(model='llama3.2', messages=[
                  {
                    'role': 'user',
                    'content': after_poppy,
                  },
                ])
                print(response)
                voice.speak(response.message.content)
            else:
                print("Heard 'poppy' but no follow-up command.")
        else:
            print("No wake word detected.")


if __name__ == "__main__":
    listen_for_poppy()

# while True:
#     transcript = run_whisper_live_transcription()
#
#
#
#     # Response code
#     response: ChatResponse = chat(model='llama3.2', messages=[
#         {
#             'role': 'user',
#             'content': 'Keep this response concise. Why is the sky blue?',
#         },
#     ])
#     voice.generate(response.message.content)

# api_key = os.getenv("API_KEY")
# client = genai.Client(api_key=api_key)
#
# gem_response = client.models.generate_content(model="gemini-2.0-flash", contents="")
# print(gem_response.text)
