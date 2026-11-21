
"""
AI service.

Supports OpenAI and Groq using API keys from the environment.
If the API call fails, the app falls back to rule-based recommendations.
"""

import json
import requests
from flask import current_app


def is_ai_configured():
    """Check whether provider and API key are configured."""
    provider = current_app.config.get("AI_PROVIDER", "")
    api_key = current_app.config.get("AI_API_KEY", "")
    return bool(provider) and bool(api_key)


def _build_context_prompt(context, question):
    """Build a prompt using the user's financial information."""
    return (
        "You are a friendly personal finance assistant helping an individual "
        "understand their own budget. Use the financial data below to answer "
        "the user's question with specific, practical, and encouraging advice. "
        "Keep the answer under 150 words and do not give professional legal or "
        "investment advice.\n\n"
        f"Monthly income: ₹{context.get('income', 0):,.0f}\n"
        f"Total expenses: ₹{context.get('expenses', 0):,.0f}\n"
        f"Savings: ₹{context.get('savings', 0):,.0f}\n"
        f"Savings rate: {context.get('savings_rate', 0)}%\n"
        f"Category-wise expenses: {json.dumps(context.get('category_breakdown', {}))}\n"
        f"Budget status: {json.dumps(context.get('budget_status', []))}\n"
        f"Financial goals: {json.dumps(context.get('goals', []))}\n\n"
        f"User question: {question}"
    )


def _call_openai(prompt, api_key):
    """Call OpenAI API."""
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.6,
            },
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    except Exception as exc:
        current_app.logger.warning("OpenAI API call failed: %s", exc)
        return None


def _call_groq(prompt, api_key):
    """Call Groq API."""
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-20b",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful personal finance assistant."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_completion_tokens": 300,
            },
            timeout=60,
        )

        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    except Exception as exc:
        current_app.logger.warning("Groq API call failed: %s", exc)
        return None


def get_ai_response(context, question):
    """
    Get a response from the configured AI provider.
    Returns None if unavailable so the app can use its fallback.
    """

    if not is_ai_configured():
        current_app.logger.info(
            "AI not configured - using rule-based fallback."
        )
        return None

    provider = current_app.config.get("AI_PROVIDER", "").lower()
    api_key = current_app.config.get("AI_API_KEY", "")

    prompt = _build_context_prompt(context, question)

    if provider == "openai":
        return _call_openai(prompt, api_key)

    elif provider == "groq":
        return _call_groq(prompt, api_key)

    return None
