import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Initialize the 2026 SDK client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def ask_gemini(question: str):
    try:
        # Using the asynchronous client (.aio) for FastAPI compatibility
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=question
        )
        
        return {
            "explanation": response.text,
            "content_type": "text",
            "visual_content": ""
        }
    except Exception as e:
        return {"error": str(e)}