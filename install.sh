#!/usr/bin/env bash
set -euo pipefail

# install.sh — Install opencode-harness into ~/.config/opencode/
#
# Creates symlinks so the repo stays the source of truth.
# Run again after pulling updates — symlinks are idempotent.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKILL_TARGET="$HOME/.config/opencode/skills/create-harness"
AGENT_DIR="$HOME/.config/opencode/agent"

echo "Installing opencode-harness from $SCRIPT_DIR"
echo ""

# --- Skill ---
mkdir -p "$(dirname "$SKILL_TARGET")"

if [ -L "$SKILL_TARGET" ]; then
    echo "  Removing existing symlink: $SKILL_TARGET"
    rm "$SKILL_TARGET"
elif [ -d "$SKILL_TARGET" ]; then
    echo "  WARNING: $SKILL_TARGET exists and is not a symlink."
    echo "  Back it up and remove it, then re-run this script."
    echo "  Skipping skill installation."
    SKILL_TARGET=""
fi

if [ -n "$SKILL_TARGET" ]; then
    ln -s "$SCRIPT_DIR/skill" "$SKILL_TARGET"
    echo "  Skill: $SKILL_TARGET -> $SCRIPT_DIR/skill"
fi

# --- Agents ---
mkdir -p "$AGENT_DIR"

for agent_file in "$SCRIPT_DIR"/agents/harness-*.md; do
    name="$(basename "$agent_file")"
    target="$AGENT_DIR/$name"

    if [ -L "$target" ]; then
        rm "$target"
    elif [ -f "$target" ]; then
        echo "  WARNING: $target exists and is not a symlink. Skipping."
        continue
    fi

    ln -s "$agent_file" "$target"
    echo "  Agent: $target -> $agent_file"
done

echo ""
echo "Done. Installed:"
echo "  - 1 skill  (create-harness)"
echo "  - 6 agents (harness-research, harness-prompt, harness-impl,"
echo "              harness-debug, harness-test, harness-recovery)"
echo ""
echo "Verify: restart OpenCode and check that 'create-harness' appears"
echo "in the available skills list."
