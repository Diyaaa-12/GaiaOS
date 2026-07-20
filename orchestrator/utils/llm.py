"""Shared LLM completions utility module."""

from __future__ import annotations

import os

import httpx

from config.settings import get_settings


async def query_llm(messages: list[dict], response_format: dict | None = None) -> str:
    """Query OpenAI Chat Completions API using the configured key (falls back to OPENAI_API_KEY)."""
    settings = get_settings()
    api_key = settings.embedding_api_key or os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OpenAI API key not configured (neither EMBEDDING_API_KEY nor "
            "OPENAI_API_KEY environment variable is set)."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.0,
    }
    if response_format:
        payload["response_format"] = response_format

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenAI Chat API error ({response.status_code}): {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"]
