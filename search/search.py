from perplexity import Perplexity
import google.genai as genai
from google.genai.types import GenerateContentConfig

from dotenv import load_dotenv
import os
import time
import json

load_dotenv()
client_perplexity = Perplexity()

client = genai.Client(api_key=os.getenv("API_KEY"))



try:
    with open('search/search_sys_prompt.txt', 'r') as f:
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
            model="gemini-2.5-flash",
            contents=context_prompt,
            config=GenerateContentConfig(
                temperature=0.3,  # Lower temperature for more focused extraction
                max_output_tokens=200,
            )
                
        )
        
        # Check if response has text content
        if not response.text:
            print("[Context extraction] No text in response")
            return None
        
        result = response.text.strip()
        print(f"[Context extraction] Extracted: {result[:100]}...")
        return result if result.lower() != "none" else None
    except Exception as e:
        print(f"Error extracting context: {e}")
        return None


def validate_search_need(query, conversation_context=None):
    # Check if conversation_context is a list (conversation history) or string (old format)
    has_context = False
    if conversation_context:
        if isinstance(conversation_context, list):
            # New format: extract only relevant context
            relevant_context = extract_relevant_context(query, conversation_context)
            if relevant_context:
                prompt = f"Previous conversation context: {relevant_context}\n\nCurrent user query: {query}"
                has_context = True
            else:
                # Fallback: include raw conversation history if extraction failed
                prompt = f"Previous conversation: {json.dumps(conversation_context[-2:], indent=2)}\n\nCurrent user query: {query}"
                has_context = True
        else:
            # Old format: string context (backward compatibility)
            prompt = f"Previous conversation context: {conversation_context}\n\nCurrent user query: {query}"
            has_context = True
    else:
        prompt = query
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=generation_config
    )
    if "Yes" in response.text:
        # Always pass the enriched query with context to search
        search_query = prompt if has_context else query
        return (True, search(search_query))
    else:
        return (False, "")


def search(query):
    completion = client_perplexity.chat.completions.create(
        model="sonar",
        max_tokens=100,
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

# print("start")
# start_time = time.time()
# print(validate_search_need("When is the next Chargers game?"))
# print(time.time() - start_time)