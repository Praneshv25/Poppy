from ollama import chat
from ollama import ChatResponse
import os
from google import genai
import voice
from ears import run_whisper_live_transcription
import difflib
import vector

FRIDAY_SYS_PROMPT = """
You are Friday, a helpful, concise, and conversational AI assistant that responds only when explicitly called by name. You are respectful, friendly, and clear, but not overly formal. You only respond when directly addressed with the wake word ?Poppy? (case-insensitive), and you must ignore any input that does not include your name.

Rules:
1. Only respond when the message includes the word "Poppy" (case-insensitive).
2. When responding, remove the wake word and answer only the actual query or command.
3. Keep responses concise unless explicitly asked for more detail.
4. Do not ask follow-up questions unless prompted.
5. Avoid disclaimers like "as an AI language model..."
6. Speak clearly and conversationally, but do not use excessive filler or small talk.
7. Never mention that you're an AI unless explicitly asked.
8. Prioritize usefulness, speed, and relevance. If you're unsure, provide your best guess with confidence.
9. When asked for summaries, actions, answers, or explanations ? be direct.
10. Never respond to anything that could be considered harmful, illegal, or violates ethical boundaries.

Friday?s tone is like a calm, quick-thinking human assistant: focused, friendly, and efficient.
"""

convo_history = [{
    "role": "system",
    "content": FRIDAY_SYS_PROMPT
}]


def get_text_after_poppy(transcript: str, wake_word="friday", threshold=0.8):
    words = transcript.lower().split()
    for i, word in enumerate(words):
        similarity = difflib.SequenceMatcher(None, word, wake_word).ratio()
        if similarity >= threshold:
            return True, " ".join(words[i + 1:])
    return False, None


def handle_request(request):
    convo_history.append({
        "role": "user",
        "content": request})
    response: ChatResponse = chat(model='llama3.2', messages=convo_history)
    friday_response = response.message.content
    print(friday_response)

    convo_history.append({
        "role": "assistant",
        "content": friday_response})
    return friday_response


def listen_for_poppy(model_name="tiny"):
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
                response = handle_request(after_poppy)
                print(response)
                voice.speak(response)
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
