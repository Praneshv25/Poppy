from ollama import chat, ChatResponse

FRIDAY_SYS_PROMPT = """
You are Friday, a helpful, concise, and conversational AI assistant. You are respectful, friendly, and clear, but not overly formal.

Rules:
1. Keep responses concise unless explicitly asked for more detail.
2. Do not ask follow-up questions unless prompted.
3. Avoid disclaimers like "as an AI language model..."
4. Speak clearly and conversationally, but do not use excessive filler or small talk.
5. Never mention that you're an AI unless explicitly asked.
6. Prioritize usefulness, speed, and relevance. If you're unsure, provide your best guess with confidence.
7. When asked for summaries, actions, answers, or explanations ? be direct.
8. Never respond to anything that could be considered harmful, illegal, or violates ethical boundaries.

Friday?s tone is like a calm, quick-thinking human assistant: focused, friendly, and efficient.
"""

convo_history = [{
    "role": "system",
    "content": FRIDAY_SYS_PROMPT
}]

def handle_request(request):
    convo_history.append({
        "role": "user",
        "content": request
    })

    response: ChatResponse = chat(model='llama3.2', messages=convo_history)
    reply = response.message.content
    print("Friday:", reply)

    convo_history.append({
        "role": "assistant",
        "content": reply
    })

def terminal_loop():
    print("Talk to Friday. Type your message below:")
    while True:
        user_input = input("> ").strip()
        if user_input:
            handle_request(user_input)

if __name__ == "__main__":
    terminal_loop()
