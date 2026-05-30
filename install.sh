#!/usr/bin/env bash
set -euo pipefail

# install.sh — Install opencode-harness into ~/.config/opencode/
#
# Creates symlinks so the repo stays the source of truth.
# Run again after pulling updates — symlinks are idempotent.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKILLS_DIR="$HOME/.config/opencode/skills"
AGENT_DIR="$HOME/.config/opencode/agent"

echo "Installing opencode-harness from $SCRIPT_DIR"
echo ""

# --- Skills ---
mkdir -p "$SKILLS_DIR"

# create-harness skill
_install_skill() {
    local name="$1"
    local source="$2"
    local target="$SKILLS_DIR/$name"

    if [ -L "$target" ]; then
        echo "  Removing existing symlink: $target"
        rm "$target"
    elif [ -d "$target" ]; then
        echo "  WARNING: $target exists and is not a symlink."
        echo "  Back it up and remove it, then re-run this script."
        echo "  Skipping $name skill installation."
        return
    fi

    ln -s "$source" "$target"
    echo "  Skill: $target -> $source"
}

_install_skill "create-harness" "$SCRIPT_DIR/skill"
_install_skill "pr-review"      "$SCRIPT_DIR/pr-review"

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
echo "  - 2 skills (create-harness, pr-review)"
echo "  - 7 agents (harness-research, harness-prompt, harness-impl,"
echo "              harness-review, harness-debug, harness-test,"
echo "              harness-recovery)"
echo ""
echo "Verify: restart OpenCode and check that 'create-harness' and"
echo "'pr-review' appear in the available skills list."
