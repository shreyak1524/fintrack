
import requests
from app import app

print("Testing Groq API...")

api_key = app.config.get("AI_API_KEY")

if not api_key:
    print("ERROR: Groq API key not found in .env")
    exit()

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

try:
    # Get available models
    url = "https://api.groq.com/openai/v1/models"

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    models = response.json().get("data", [])

    # Select an available chat model
    preferred_models = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b"
    ]

    available = [m["id"] for m in models]

    model = next(
        (m for m in preferred_models if m in available),
        None
    )

    if not model:
        print("No preferred chat model found.")
        print("Available models:", available)
        exit()

    print("Model selected:", model)

    # Send test message
    chat_url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful financial advisor."
            },
            {
                "role": "user",
                "content": "Give me three simple tips to save money."
            }
        ],
        "max_completion_tokens": 200
    }

    result = requests.post(
        chat_url,
        headers=headers,
        json=payload,
        timeout=60
    )

    result.raise_for_status()

    answer = result.json()["choices"][0]["message"]["content"]

    print("\nGROQ WORKING!")
    print("\nAI RESPONSE:")
    print(answer)

except requests.exceptions.RequestException as e:
    print("\nGROQ API FAILED!")
    print("Error:", e)

    if getattr(e, "response", None) is not None:
        print(e.response.text[:1500])

