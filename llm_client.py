"""
llm_client.py — tiny shared helper for non-critical LLM calls across the pipeline.

Primary: Claude (Sonnet/Haiku/Opus) or OpenAI (GPT-4o)
Fallback: DeepSeek — only used when the primary call fails with an API error
          (connection, 429, 500s). This matches the project's cost strategy:
          keep premium models on content creation, use DeepSeek purely as a
          safety net.

Usage:
    from llm_client import call_with_fallback
    text = call_with_fallback(
        primary="claude-sonnet-4-6",
        prompt="...",
        max_tokens=2000,
    )
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import anthropic
import openai
from dotenv import load_dotenv
from network_probe import require_host

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_KEY  = os.getenv("DEEPSEEK_API_KEY", "")


def _call_claude(model: str, prompt: str, max_tokens: int = 2000) -> str:
    require_host("api.anthropic.com", "Anthropic")
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _call_openai(model: str, prompt: str, max_tokens: int = 2000) -> str:
    require_host("api.openai.com", "OpenAI")
    client = openai.OpenAI(api_key=OPENAI_KEY)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


def _call_deepseek(prompt: str, max_tokens: int = 2000) -> str:
    require_host("api.deepseek.com", "DeepSeek")
    client = openai.OpenAI(
        api_key=DEEPSEEK_KEY,
        base_url="https://api.deepseek.com/v1",
    )
    resp = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


def call_with_fallback(
    primary: str,
    prompt: str,
    max_tokens: int = 2000,
    caller_name: Optional[str] = None,
) -> str:
    """
    Call the primary model. On API error, fall back to DeepSeek.

    `primary` can be:
        "claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"
        "gpt-4o", "gpt-4o-mini"

    Raises RuntimeError only if BOTH primary and DeepSeek fail.
    """
    tag = f"[{caller_name}] " if caller_name else ""
    try:
        if primary.startswith("claude"):
            return _call_claude(primary, prompt, max_tokens)
        elif primary.startswith("gpt-"):
            return _call_openai(primary, prompt, max_tokens)
        else:
            raise ValueError(f"unknown primary model: {primary}")
    except Exception as e:
        print(f"  {tag}primary ({primary}) failed: {type(e).__name__}: {str(e)[:80]} — falling back to DeepSeek")
        if not DEEPSEEK_KEY:
            raise RuntimeError(f"primary failed and DEEPSEEK_API_KEY not set — {e}")
        try:
            return _call_deepseek(prompt, max_tokens)
        except Exception as e2:
            raise RuntimeError(
                f"both primary ({primary}) and DeepSeek fallback failed: "
                f"primary={e}, deepseek={e2}"
            ) from e2
