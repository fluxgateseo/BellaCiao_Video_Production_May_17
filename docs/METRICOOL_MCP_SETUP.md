# Metricool MCP — setup

Lets this session schedule/publish Bella posts to Instagram, TikTok, YouTube,
Facebook (the accounts already linked inside Metricool).

The server is declared in the repo's `.mcp.json` (`mcp-metricool`, run via
`uvx`). It reads two **secrets from the environment** — they are NOT stored in
the repo:

| Env var | Where to get it (Metricool → Settings) |
| --- | --- |
| `METRICOOL_USER_TOKEN` | Account settings → API / access token (**Advanced tier required**) |
| `METRICOOL_USER_ID` | Account settings → user ID |

## Steps (Claude Code on the web)
1. In the **environment settings** for this repo, add two environment
   variables / secrets: `METRICOOL_USER_TOKEN` and `METRICOOL_USER_ID`.
   (Do not paste the token into chat or commit it.)
2. Make sure the environment's **network policy** allows outbound to PyPI
   (to fetch `mcp-metricool` via `uvx`) and to Metricool's API
   (`app.metricool.com` / `api.metricool.com`). If the policy is "no network"
   or a strict allowlist, add those hosts.
3. **Restart the session** so Claude Code loads `.mcp.json`. The Metricool
   tools (e.g. list brands, schedule post, best-time-to-post) then appear.

## Verify
Once restarted, the assistant can call the Metricool tools. Quick check:
ask it to "list my Metricool brands" — it should return the connected
IG/TikTok/YouTube/FB profiles.

## Notes
- Scheduling a Reel/TikTok/Short needs a **video file**; an IG feed/Story post
  can use an image. Have the media ready (or generated) before scheduling.
- Tokens are per-account and tier-gated; if tool calls fail with an auth error,
  re-check the token tier and that both env vars are set.
- Local Claude Code (not web): same `.mcp.json` works; set the two env vars in
  your shell or via `claude mcp` before launching.
