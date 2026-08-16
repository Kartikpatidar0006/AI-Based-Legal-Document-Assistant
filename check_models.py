import os
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ No API key found in .env file.")
else:
    client = genai.Client(api_key=api_key)
    print("Fetching available models...")
    for model in client.models.list():
        print(model.name)