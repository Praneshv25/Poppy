from ollama import chat
from ollama import ChatResponse
import os
from google import genai
import voice



# Response code
response: ChatResponse = chat(model='llama3.2', messages=[
  {
    'role': 'user',
    'content': 'Keep this response concise. Why is the sky blue?',
  },
])
voice.generate(response.message.content)


api_key = os.getenv("API_KEY")
client = genai.Client(api_key=api_key)

gem_response = client.models.generate_content(model="gemini-2.0-flash", contents="")
print(gem_response.text)
