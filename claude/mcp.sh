#!/usr/bin/env bash
# Register the MCP servers from opencode.jsonc (user scope: every project) and
# from ai-scribe's personal, gitignored opencode.json (local scope: the
# ai-scribe main checkout only, the same reach that file had) with Claude Code.
#
# Idempotent: a server that already exists is skipped, because re-adding one
# would drop its OAuth login. To change a server: claude mcp remove -s <scope>
# <name>, then re-run this script.
#
# No secret is written to ~/.claude.json:
#   - brave-search reads its key at launch from the chmod-600 file opencode
#     uses (~/.config/opencode/brave-api-key)
#   - figma expands ${FIGMA_API_KEY}, exported in ~/.zshenv
#   - telnyx reads TELNYX_API_KEY from ai-scribe's gitignored backend/.env
#   - google-sheets' OAuth client secret goes to Claude Code's credential
#     store (macOS Keychain) via MCP_CLIENT_SECRET, read from the opencode file
#   - every other remote server uses OAuth with dynamic client registration:
#     run /mcp in Claude Code and pick the server to sign in
#
# Not migrated: per-agent MCP allow/deny (Claude Code defers MCP tool schemas
# until used, which was the point of that scoping), and ai-scribe's disabled
# codebase-memory-mcp entry (it is not configured anywhere in Claude Code).
set -euo pipefail

OPENCODE_DIR="$HOME/.config/opencode"
AI_SCRIBE="$HOME/Documents/code/ai-scribe"

# add SCOPE NAME JSON [extra claude mcp add-json args...]
add() {
  local scope="$1" name="$2" json="$3"
  shift 3
  if claude mcp get "$name" >/dev/null 2>&1; then
    echo "  exists, skipped: $name"
    return 0
  fi
  claude mcp add-json --scope "$scope" "$name" "$json" "$@" >/dev/null
  echo "  added ($scope): $name"
}

echo "User scope (all projects):"
add user cloudflare       '{"type":"http","url":"https://mcp.cloudflare.com/mcp"}'
add user mobbin           '{"type":"http","url":"https://api.mobbin.com/mcp"}'
add user figma            '{"type":"stdio","command":"npx","args":["-y","figma-developer-mcp","--stdio"],"env":{"FIGMA_API_KEY":"${FIGMA_API_KEY}"}}'
add user context7         '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}'
add user supermemory-docs '{"type":"http","url":"https://supermemory.ai/docs/mcp"}'
add user linear           '{"type":"http","url":"https://mcp.linear.app/mcp"}'
add user paper            '{"type":"http","url":"http://127.0.0.1:29979/mcp"}'
add user brave-search     '{"type":"stdio","command":"sh","args":["-c","BRAVE_API_KEY=\"$(cat \"$HOME/.config/opencode/brave-api-key\")\" exec npx -y @brave/brave-search-mcp-server"]}'
add user comfy-cloud      '{"type":"http","url":"https://cloud.comfy.org/mcp"}'
add user cbinsights       '{"type":"http","url":"https://mcp.cbinsights.com"}'

# Pre-registered Google OAuth client (no dynamic registration). Its allowed
# redirect URI must include Claude Code's callback on this fixed port:
# http://localhost:19876/callback (opencode's is .../mcp/oauth/callback).
MCP_CLIENT_SECRET="$(cat "$OPENCODE_DIR/google-sheets-mcp-client-secret")" \
  add user google-sheets "$(printf '{"type":"http","url":"https://sheetsmcp.googleapis.com/mcp/v1","oauth":{"clientId":"%s","callbackPort":19876,"scopes":"https://www.googleapis.com/auth/spreadsheets"}}' \
    "$(tr -d '[:space:]' <"$OPENCODE_DIR/google-sheets-mcp-client-id")")" --client-secret

echo "Local scope ($AI_SCRIBE only):"
cd "$AI_SCRIBE"
# codegraph is deliberately not registered for Claude Code (decided
# 2026-10-08): the opencode pilot showed no token savings (3% of sessions used
# it, ~5.9k tokens per call, no fewer reads), and Claude Code already defers
# tool schemas and offloads search to Explore. It stays opencode-only.
add local playwright      '{"type":"stdio","command":"npx","args":["-y","@playwright/mcp@latest"]}'
add local chrome-devtools '{"type":"stdio","command":"npx","args":["-y","chrome-devtools-mcp@latest"]}'
add local dart            '{"type":"stdio","command":"dart","args":["mcp-server"]}'
# ADR 0176 §8: sign in with the Stripe TEST/sandbox account only.
add local stripe          '{"type":"http","url":"https://mcp.stripe.com"}'
# Provisioning-only --tools allowlist and pinned commit, verbatim from
# ai-scribe/opencode.json (ADR 0176 §8: never widen to send/dial tools).
add local telnyx          '{"type":"stdio","command":"sh","args":["-c","if [ -z \"$TELNYX_API_KEY\" ] && [ -f backend/.env ]; then export $(grep -E '"'"'^TELNYX_API_KEY=.'"'"' backend/.env); fi; exec uvx --from git+https://github.com/team-telnyx/telnyx-mcp-server@3f6a1173fec2b5bf3db4338384a9f7b00b8eaec8 telnyx-mcp-server --tools list_phone_numbers,get_phone_number,update_phone_number,list_available_phone_numbers,initiate_phone_number_order,update_phone_number_messaging_settings,list_messaging_profiles,create_messaging_profile,get_messaging_profile,update_messaging_profile,list_connections,get_connection"]}'

echo
echo "Next: start claude, run /mcp, and sign in to each OAuth server."
