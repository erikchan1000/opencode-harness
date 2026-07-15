#!/usr/bin/env bash
# Anti-Slop gate for Flutter Taste Skill.
#
# Enforces the SKILL.md Ban List rules that the Dart analyzer cannot see.
# (The `withOpacity` -> `withValues` rule is enforced separately by
# analysis_options.yaml as a `deprecated_member_use: error`.)
#
# Exits non-zero on any violation so it can run in CI / pre-commit.
# Usage: bash tool/anti_slop_check.sh
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2

fail=0
SCAN_DART="lib test"           # generated/product Dart code

report() {
  # $1 = human label, $2 = matches (may be empty)
  if [ -n "$2" ]; then
    echo "✗ BAN VIOLATED: $1"
    echo "$2" | sed 's/^/    /'
    fail=1
  else
    echo "✓ $1"
  fi
}

# 1. EM-DASH BAN — em dash / en dash in generated/product code (comments and
#    user-facing strings). Scoped to Dart only: the ban is about generated
#    OUTPUT, so the doc files that DEFINE the rule are allowed to name the glyph.
hits=$(grep -rn $'—\|–' $SCAN_DART 2>/dev/null)
report "EM-DASH BAN (no — or – in lib/ test/)" "$hits"

# 2. AI-PURPLE BAN — the canonical AI-slop purple and lazy named purples.
hits=$(grep -rni '7C3AED\|Colors\.deepPurple\|Colors\.purple\b' $SCAN_DART 2>/dev/null)
report "AI-PURPLE BAN (no #7C3AED / deepPurple / purple)" "$hits"

# 3. BOILERPLATE BAN — counters, hello world, sample items, default MyApp.
hits=$(grep -rni 'Hello World\|Sample Item\|class MyApp\b\|Counter increments' $SCAN_DART 2>/dev/null)
report "BOILERPLATE BAN (no Counter / MyApp / Hello World)" "$hits"

echo
if [ "$fail" -ne 0 ]; then
  echo "Anti-Slop gate FAILED."
  exit 1
fi
echo "Anti-Slop gate passed."
