"""
ssml_tagger.py — Agent 7: SSML Tagger.

Rule-based ElevenLabs SSML markup. Runs AFTER Quality Supervisor approval and
BEFORE the job file is written. Operates only on the approved Section 2 (the
spoken video script). Sections 1, 3, 4 are never touched.

Voice ID: 9DxYbhovJvj6zRtn0Pvc

Tagging rules (from brand.SSML_GUIDE):
  - <break time="200ms"/>                       after a punchy 1-3 word fragment
  - <prosody rate="fast">…</prosody>            wrap rapid factual lines
  - <prosody rate="slow">…</prosody>            ALWAYS wrap the elixir / payoff
  - <prosody rate="medium" pitch="+10%">…       wrap any line spoken by a friend
  - <break time="300ms"/><prosody rate="medium">…</prosody>   sign-off (always)

The tagger is conservative: when in doubt it leaves the text alone. The output
is validated as well-formed XML before being returned. If validation fails the
text is cleaned and retried once. If it still fails, the original plain text is
returned and a warning is logged — the job file is written without SSML rather
than blocking publication.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

import brand


# ─── Section extraction (kept local; mirror of engine.extract_section) ───────

def _extract_section(full: str, label: str) -> str:
    """
    Pull out the body of a "SECTION N" block. Falls back to the entire input
    when the marker is absent (which happens during synthesised tests).
    """
    if label not in full:
        return full
    lines, in_sec, out = full.split("\n"), False, []
    for line in lines:
        if label in line:
            in_sec = True
            continue
        if in_sec and line.startswith("SECTION ") and label not in line:
            break
        if in_sec:
            out.append(line)
    return "\n".join(out).strip()


# ─── Helpers ─────────────────────────────────────────────────────────────────

_BRACKET_RE   = re.compile(r"\[[^\]]*\]")              # [pacing], [pause]
_FRAGMENT_RE  = re.compile(r"^(.{1,18}?[.!?])\s+")     # leading short fragment
_FRIEND_LINE  = re.compile(r"^([A-Z][A-Z _'-]{1,30}):\s*(.+)$")  # "JAKE: line"


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def _strip_pacing_brackets(line: str) -> str:
    """[smile], [pause] etc are direction notes — strip before TTS."""
    return _BRACKET_RE.sub("", line).strip()


def _is_speaker_line(line: str) -> tuple[str, str] | None:
    """Return (speaker, body) if the line is 'NAME: text', else None."""
    m = _FRIEND_LINE.match(line.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def _wrap_friend_voice(body: str) -> str:
    return f'<prosody rate="medium" pitch="+10%">{_xml_escape(body)}</prosody>'


def _wrap_elixir(body: str) -> str:
    return f'<prosody rate="slow">{_xml_escape(body)}</prosody>'


def _wrap_signoff(body: str) -> str:
    return f'<break time="300ms"/><prosody rate="medium">{_xml_escape(body)}</prosody>'


def _split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras or [text.strip()]


def _looks_like_signoff(line: str) -> bool:
    low = line.lower().strip()
    return low.startswith("ciao") or "#bella" in low or "#ciaobella" in low


def _looks_like_elixir(line: str, position: int, total: int) -> bool:
    """Heuristic: penultimate paragraph is the payoff/elixir most of the time."""
    if total <= 2:
        return position == total - 1
    return position == total - 2


# ─── Main tagging routine ────────────────────────────────────────────────────

def _tag_paragraph(para: str, is_elixir: bool, is_signoff: bool) -> str:
    para = _strip_pacing_brackets(para)
    if not para:
        return ""

    # 1) Speaker-attributed friend lines → friend voice prosody
    speaker = _is_speaker_line(para)
    if speaker and speaker[0].lower() != "bella":
        return _wrap_friend_voice(speaker[1])

    # 2) Sign-off → always break + medium prosody
    if is_signoff:
        return _wrap_signoff(para)

    # 3) Elixir → always slow prosody
    if is_elixir:
        return _wrap_elixir(para)

    # 4) Punchy 1-3 word leading fragment → add a 200ms break after it
    short = _FRAGMENT_RE.match(para)
    if short and len(short.group(1).split()) <= 3:
        head, tail = short.group(1), para[short.end():]
        return f'{_xml_escape(head)}<break time="200ms"/> {_xml_escape(tail)}'

    return _xml_escape(para)


def _build_ssml(section_2: str) -> str:
    paras = _split_paragraphs(section_2)
    total = len(paras)

    tagged: list[str] = []
    for i, p in enumerate(paras):
        signoff = i == total - 1 and _looks_like_signoff(p)
        elixir  = (not signoff) and _looks_like_elixir(p, i, total)
        tagged.append(_tag_paragraph(p, is_elixir=elixir, is_signoff=signoff))

    inner = "\n".join(t for t in tagged if t)
    return f"<speak>\n{inner}\n</speak>"


def _validate_xml(ssml: str) -> bool:
    try:
        ET.fromstring(ssml)
        return True
    except ET.ParseError as e:
        print(f"[ssml] xml validation failed: {e}")
        return False


def _clean_for_retry(section_2: str) -> str:
    """Strip anything that could break XML on a retry pass."""
    cleaned = re.sub(r"[<>]", "", section_2)
    cleaned = _BRACKET_RE.sub("", cleaned)
    return cleaned.strip()


# ─── Public API ──────────────────────────────────────────────────────────────

def tag_script(approved_script: str, brief: dict | None = None) -> str:
    """
    Apply SSML tags to the approved Section 2 video script.

    Returns a well-formed <speak>…</speak> string ready for ElevenLabs.
    On unrecoverable failure returns the plain Section 2 text and logs a warning.
    """
    section_2 = _extract_section(approved_script, "SECTION 2")
    if not section_2:
        print("[ssml] no SECTION 2 found — returning original")
        return approved_script

    ssml = _build_ssml(section_2)
    if _validate_xml(ssml):
        return ssml

    # Retry once with cleaned input
    ssml_retry = _build_ssml(_clean_for_retry(section_2))
    if _validate_xml(ssml_retry):
        return ssml_retry

    print("[ssml] tagging failed twice — returning plain Section 2")
    return section_2


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not text:
        print("Usage: cat script.txt | python3 ssml_tagger.py")
        raise SystemExit(1)
    print(tag_script(text))
