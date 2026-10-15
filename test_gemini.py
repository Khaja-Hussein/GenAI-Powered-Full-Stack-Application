import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

models = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

print("\nTesting Gemini models...\n")

for model in models:
    try:
        response = client.models.generate_content(
            model=model,
            contents="Explain Python in one sentence."
        )

        print(f"SUCCESS: {model}")
        print(response.text)
        break

    except Exception as error:
        print(f"\nFAILED: {model}")
        print(error)
        print("-" * 50)

else:
    print("\nAll tested models failed.")