"""
publishers/ — direct platform publishing routines for Bella content.

Isolated from the script engine on purpose: the engine generates scripts;
this package takes finished media + metadata and publishes/schedules it on
external platforms. Credentials come from the environment only — never the repo.

Implemented:
  - youtube_publisher : upload + natively-scheduled release (YouTube Data API)
  - youtube_auth      : one-time OAuth refresh-token minting helper
  - publish_queue     : run a data/publish_queue.json queue against the platforms
"""
