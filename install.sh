#!/usr/bin/env bash
set -euo pipefail

# install.sh — Install this repo's skills, agents, and config into
# ~/.config/opencode/ as symlinks, so the repo stays the single source
# of truth. Run again after pulling updates — symlinks are idempotent.
#
# Layout created in ~/.config/opencode/:
#   skills/<name>   -> <repo>/skills/<name>       (every dir under skills/)
#   agents/<name>.md -> <repo>/agents/<name>.md   (every file under agents/)
#   AGENTS.md       -> <repo>/AGENTS.md
#   opencode.jsonc  -> <repo>/opencode.jsonc

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_DIR="$HOME/.config/opencode"
SKILLS_DIR="$CONFIG_DIR/skills"
AGENT_DIR="$CONFIG_DIR/agents"

TS="$(date +%Y%m%d-%H%M%S)"

echo "Installing opencode config from $SCRIPT_DIR"
echo ""

# link SOURCE TARGET — create TARGET as a symlink to SOURCE.
#   - existing symlink            -> replaced (idempotent)
#   - existing real file/dir      -> backed up to TARGET.bak-<timestamp>
link() {
    local source="$1"
    local target="$2"

    if [ -L "$target" ]; then
        rm "$target"
    elif [ -e "$target" ]; then
        echo "  Backing up existing $target -> $target.bak-$TS"
        mv "$target" "$target.bak-$TS"
    fi

    ln -s "$source" "$target"
    echo "  $target -> $source"
}

# --- Skills ---
mkdir -p "$SKILLS_DIR"
skill_count=0
for skill_path in "$SCRIPT_DIR"/skills/*/; do
    name="$(basename "$skill_path")"
    link "${skill_path%/}" "$SKILLS_DIR/$name"
    skill_count=$((skill_count + 1))
done

# --- Agents ---
mkdir -p "$AGENT_DIR"
agent_count=0
for agent_file in "$SCRIPT_DIR"/agents/*.md; do
    name="$(basename "$agent_file")"
    link "$agent_file" "$AGENT_DIR/$name"
    agent_count=$((agent_count + 1))
done

# --- Top-level config files ---
link "$SCRIPT_DIR/AGENTS.md"      "$CONFIG_DIR/AGENTS.md"
link "$SCRIPT_DIR/opencode.jsonc" "$CONFIG_DIR/opencode.jsonc"

echo ""
echo "Done. Installed:"
echo "  - $skill_count skills  -> $SKILLS_DIR/"
echo "  - $agent_count agents  -> $AGENT_DIR/"
echo "  - AGENTS.md, opencode.jsonc -> $CONFIG_DIR/"
echo ""
echo "Verify: restart OpenCode and check the available skills list."
