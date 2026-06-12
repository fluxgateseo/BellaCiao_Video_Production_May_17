"""
analysis.py — Skill 2: Analysis Pipeline

Synthesizes raw research signals from source_mining.py into structured
intelligence: key themes, actionable angles, audience signals, and
timing windows.

Model: Claude Haiku (cost-efficient for summarization)
Input: data/research_signals.json
Output: data/analysis_brief.json

Usage:
    python3 analysis.py                        # analyze latest signals
    python3 analysis.py --signals path/to.json  # analyze a specific file
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR        = Path(__file__).parent
SIGNALS_FILE    = BASE_DIR / "data" / "research_signals.json"
ANALYSIS_FILE   = BASE_DIR / "data" / "analysis_brief.json"
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_HAIKU     = "claude-haiku-4-5-20251001"


ANALYSIS_PROMPT = """You are the Research Analyst for the Bellaciao content engine.
Bella is a content persona for SEO For Restaurants — she helps restaurant owners
fix their Google profiles, improve local search rankings, and stop leaving money
on the table. Her audience is independent restaurant operators in Melbourne (AU),
New York City (US), and London (UK).

Below are raw research signals from multiple sources: industry news, social media
trends, competitor content, and search trends. Your job is to synthesize these
into structured intelligence the content team can act on.

Return ONLY valid JSON with this shape:
{{
  "this_week_themes": [
    {{
      "theme": "string — 5-10 word theme name",
      "evidence": "string — what signals point to this",
      "relevance_to_bella": "string — why this matters for restaurant operators"
    }}
  ],
  "actionable_angles": [
    {{
      "angle": "string — specific content angle",
      "format": "story | reel | blog | thread",
      "friend_fit": ["friend_id1", "friend_id2"],
      "urgency": "high | medium | low",
      "rationale": "string — why this angle, why now"
    }}
  ],
  "audience_signals": [
    "string — what the audience is asking / searching for / talking about"
  ],
  "timing_windows": [
    {{
      "event_or_trend": "string",
      "window": "string — e.g. 'peaks in 14 days'",
      "action_needed_by": "string — date or timeframe"
    }}
  ]
}}

Limit: 3-5 themes, 5-8 angles, 3-5 audience signals, 2-4 timing windows.
Focus on what is ACTIONABLE for restaurant operators, not general food industry news.

RAW SIGNALS:
{signals_text}
"""


def analyze_signals(signals_path: Optional[Path] = None) -> dict:
    """
    Read research signals and synthesize into an analysis brief.
    Returns the analysis dict and writes to data/analysis_brief.json.
    """
    path = signals_path or SIGNALS_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — run `python3 source_mining.py` first"
        )

    payload = json.loads(path.read_text())
    signals = payload.get("signals", [])
    if not signals:
        print("[analysis] no signals to analyze")
        return {"error": "no signals", "analyzed_at": datetime.now().isoformat()}

    # Build a text summary of all signals for the prompt
    signal_lines: list[str] = []
    for s in signals[:50]:  # cap to avoid token explosion
        source = s.get("source", "unknown")
        content = s.get("raw_content", s.get("title", ""))[:300]
        signal_lines.append(f"[{source}] {content}")
    signals_text = "\n".join(signal_lines)

    from llm_client import call_with_fallback
    prompt = ANALYSIS_PROMPT.format(signals_text=signals_text)
    raw = call_with_fallback(
        primary=MODEL_HAIKU,
        prompt=prompt,
        max_tokens=2000,
        caller_name="analysis",
    )

    # Parse JSON from response
    try:
        # Strip code fences if present
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif text.startswith("```"):
            text = text.split("```", 2)[1].split("```", 1)[0]
        analysis = json.loads(text.strip())
    except json.JSONDecodeError:
        analysis = {"raw_response": raw, "parse_error": True}

    analysis["analyzed_at"] = datetime.now().isoformat(timespec="seconds")
    analysis["signals_count"] = len(signals)
    analysis["model"] = MODEL_HAIKU

    ANALYSIS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_FILE.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    print(f"[analysis] wrote {ANALYSIS_FILE}")

    # Print summary
    themes = analysis.get("this_week_themes", [])
    angles = analysis.get("actionable_angles", [])
    print(f"  themes: {len(themes)}, angles: {len(angles)}")
    for t in themes[:3]:
        print(f"    - {t.get('theme', '?')}")
    for a in angles[:3]:
        print(f"    → {a.get('angle', '?')} ({a.get('urgency', '?')})")

    return analysis


# ─── CLI ─────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Skill 2 — Analysis Pipeline")
    p.add_argument("--signals", help="path to a signals JSON file (default: latest)")
    args = p.parse_args()
    path = Path(args.signals) if args.signals else None
    analyze_signals(path)


if __name__ == "__main__":
    main()
