"""
Quick test script for Salieri AI backend.
Tests the LLM connection with your OpenAI-compatible API.

Usage:
    # OpenAI
    set OPENAI_API_KEY=sk-...
    python test_api.py

    # Custom OpenAI-compatible (OpenRouter, Groq, DeepSeek, Together, etc.)
    set OPENAI_API_KEY=your-key
    set OPENAI_BASE_URL=https://api.openrouter.ai/v1
    set SALIERI_LLM_MODEL=openai/gpt-4o-mini
    python test_api.py

    # Or pass as env vars inline:
    OPENAI_API_KEY=sk-... OPENAI_BASE_URL=https://api.openrouter.ai/v1 python test_api.py
"""

import os
import sys
import asyncio

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Force OpenAI provider for testing
os.environ["SALIERI_LLM_PROVIDER"] = "openai"

from llm import LLMEngine
from personality import PersonalityEngine


async def main():
    print("=" * 50)
    print("Salieri AI - API Connection Test")
    print("=" * 50)

    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("SALIERI_LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        print("\nERROR: OPENAI_API_KEY not set!")
        print("\nSet your API key:")
        print('  set OPENAI_API_KEY=sk-...')
        print("\nFor custom endpoints, also set:")
        print('  set OPENAI_BASE_URL=https://your-endpoint.com/v1')
        print('  set SALIERI_LLM_MODEL=your-model-name')
        return

    print(f"\nProvider:  OpenAI-compatible")
    print(f"Base URL:  {base_url or 'https://api.openai.com/v1'}")
    print(f"Model:     {model}")
    print(f"Key:       {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else ''}")

    # Initialize LLM
    print("\n[1] Initializing LLM engine...")
    try:
        llm = LLMEngine()
        print("    OK - LLM engine initialized")
    except Exception as e:
        print(f"    FAILED: {e}")
        return

    # Build test messages
    pe = PersonalityEngine()
    messages = pe.build_messages("Hello! Who are you?", [], [])

    print(f"\n[2] Sending test message...")
    print(f"    Messages: {len(messages)} (system + user)")
    print(f"    System prompt length: {len(messages[0]['content'])} chars")

    try:
        response = await llm.chat(messages)
        print(f"\n[3] Response received:")
        print(f"    {response}")
        print(f"    Length: {len(response)} chars")

        # Detect emotion
        emotion = pe.detect_emotion(response)
        print(f"    Emotion: {emotion}")

        print("\n" + "=" * 50)
        print("SUCCESS! Your API connection is working.")
        print("=" * 50)
        print("\nTo start the full backend:")
        print("  cd backend && python server.py")
        print("\nThen in another terminal:")
        print("  npm run dev")

    except Exception as e:
        print(f"\n[3] FAILED: {e}")
        print("\nTroubleshooting:")
        print("  - Check your API key is correct")
        print("  - Check your base URL includes /v1")
        print("  - Check the model name is valid for your provider")
        print("  - If using a custom endpoint, make sure it supports /chat/completions")


if __name__ == "__main__":
    asyncio.run(main())