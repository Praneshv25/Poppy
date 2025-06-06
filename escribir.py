from ollama import chat, ChatResponse
from eyes import capture_image, describe_image_with_llava
import json

FRIDAY_SYS_PROMPT = """
You are Friday, a helpful, concise, and conversational AI assistant. You are respectful, friendly, and clear, but not overly formal.

You can process text, images, personal memory, and schedule tasks. You must analyze each user message and respond in the following strict JSON format:

{
  "requires_vision": true | false,
  "requires_external_context": true | false,
  "requires_personal_context": true | false,
  "store_personal_context": true | false,
  "store_as_task": true | false,
  "model_complexity": "default" | "advanced",
  "reason": "Why these flags were set",
  "response": "Your reply based on the context you have"
}

Rules:
1. Use "requires_vision" if the question depends on what the user sees.
2. Use "requires_external_context" if the answer depends on current events, weather, or up-to-date info you can't answer alone.
3. Use "requires_personal_context" if the user asks something about their memory, history, or preferences.
4. Use "store_personal_context" if the user gives new facts or memories you should remember.
5. Use "store_as_task" if the message includes a future action (reminder, todo, meeting).
6. Set "model_complexity" to "advanced" only for abstract, nuanced, or high-risk reasoning.
7. Keep "reason" short but meaningful.
8. Always return valid JSON with no formatting outside the object.
9. Never include disclaimers or ask follow-up questions unless asked.
10. Your tone should be direct, efficient, and human.

Friday?s voice is calm, competent, and action-oriented.
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
    reply = response.message.content.strip()

    try:
        parsed = json.loads(reply)
        convo_history.append({ "role": "assistant", "content": reply })

        return {
            **parsed,
            "original_request": request
        }

    except json.JSONDecodeError:
        print("[?] Failed to parse JSON from assistant response.")
        print("Raw reply:", reply)

        convo_history.append({ "role": "assistant", "content": reply })
        return {
            "requires_vision": False,
            "requires_external_context": False,
            "requires_personal_context": False,
            "store_personal_context": False,
            "store_as_task": False,
            "model_complexity": "default",
            "reason": "Parsing failed",
            "response": reply,
            "original_request": request
        }


def process_user_request(user_input):
    result = handle_request(user_input)
    print(f"[?] Reason: {result['reason']}")

    # Step 1: Handle vision
    if result["requires_vision"]:
        image_path = capture_image("frame.jpg")
        vision_desc = describe_image_with_llava(image_path)

        followup = f"""The user asked: "{result['original_request']}"
Here is what I see: "{vision_desc}"
Please answer the original question now using this visual context."""

        convo_history.append({ "role": "user", "content": followup })
        response = chat(model='llama3.2', messages=convo_history)
        reply = response.message.content.strip()
        convo_history.append({ "role": "assistant", "content": reply })
        print("\nFriday (vision-assisted):", reply)
        return reply

    # Step 2: External context (placeholder)
    if result["requires_external_context"]:
        print("[?] External context needed ? Not yet implemented.")

    # Step 3: Query personal context (placeholder)
    if result["requires_personal_context"]:
        print("[?] Retrieve personal context ? Not yet implemented.")

    # Step 4: Store new memory or task
    if result["store_personal_context"]:
        print("[?] Store personal context ? Not yet implemented.")

    if result["store_as_task"]:
        print("[?] Store task/reminder ? Not yet implemented.")

    # Step 5: Handle complex models (optional switch)
    if result["model_complexity"] == "advanced":
        print("[?] Consider switching to an advanced model ? optional.")

    print("Friday:", result["response"])
    return result["response"]


def terminal_loop():
    print("Talk to Friday. Type your message below:")
    while True:
        user_input = input("> ").strip()
        if user_input:
            process_user_request(user_input)


if __name__ == "__main__":
    terminal_loop()
