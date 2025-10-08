from perplexity import Perplexity
import google.genai as genai
from google.genai.types import GenerateContentConfig

from dotenv import load_dotenv
import os

load_dotenv()
client_perplexity = Perplexity()

client = genai.Client(api_key=os.getenv("API_KEY"))



try:
    with open('search_sys_prompt.txt', 'r') as f:
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




def validate_search_need(query):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query,
        config=generation_config
    )
    if "Yes" in response.text:
        return (True, search(query))
    else:
        return (False, "")


def search(query):
    completion = client_perplexity.chat.completions.create(
        model="sonar",
        messages=[
            {"role": "user", "content": query}
        ]
    )

    return completion.choices[0].message.content

# print(validate_search_need("When is the next Chargers game?"))

