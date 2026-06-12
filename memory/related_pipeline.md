---
name: Downstream video creation tool
description: Pointer to the separate (planned) video creation tool that consumes script_engine output, and how the handoff works
type: reference
---

The downstream video creation tool is a **separate sibling project**, not part of script_engine. It consumes approved scripts from `Scripts/Day N/{episode_id}.json` and produces video files. As of 2026-04-10 it is still being designed.

Capabilities that belong there (NOT in script_engine):

| Capability | Notes |
|---|---|
| ElevenLabs TTS + alignment | uses `video_script_ssml` from the job file |
| Audio QA gate | |
| Model-agnostic video clip generation | 5-10s clips, stitched into the final video; engine choice is per-day |
| Captions, lip sync, transitions | |
| Multimodal video QA | |

**Out of scope for the entire ecosystem** (not just script_engine, not just the video tool):

- Publishing of any kind (Instagram, YouTube, TikTok, anywhere)
- Messaging-bot / approval-gate workflows of any kind

**Handoff contract:** the script_engine writes one JSON per approved script to `Scripts/Day N/{episode_id}.json`. The video tool reads from there. No other coupling.
