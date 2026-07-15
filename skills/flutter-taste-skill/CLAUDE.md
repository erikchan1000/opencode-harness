# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A dual-purpose project. It is **both**:

1. **An "Agent Skill"** — a portable design-taste instruction set for AI coding agents. The canonical content lives in [SKILL.md](SKILL.md) (full protocol) and [GEMINI.md](GEMINI.md) (Gemini-CLI-specific subset). These are not docs *about* the code; they are the product. Edits to design philosophy belong here.
2. **A reference Flutter package + showcase app** — `lib/` proves the skill's principles with real, lint-clean widgets and four full demo screens.

When asked to "improve the skill" or "change the design rules," edit `SKILL.md`/`GEMINI.md`. When asked to build or fix widgets, edit `lib/` — and the code must itself obey `SKILL.md`.

## Generating any UI in this repo — follow SKILL.md

This is the load-bearing instruction. Any Flutter UI written here (or anywhere this skill is active) must comply with [SKILL.md](SKILL.md). Non-negotiables:

- **Design Read first.** Before writing widgets, state industry/audience, an aesthetic variant (Obsidian / Cloud / Brutalist / custom), and confirm the three dials.
- **Three Dials** parametrize every layout: `FLUTTER_LAYOUT_VARIANCE`, `FLUTTER_MOTION`, `FLUTTER_DENSITY` (1–10 each).
- **Anti-Slop Ban List:** no em-dashes (`—`/`–`) anywhere in output; no boilerplate (counters, "Hello World", "Sample Item"); no AI-purple (`#7C3AED` / generic indigo→purple gradients); never use a default un-styled `Scaffold`.
- **Color through theme only.** Every color comes from `Theme.of(context).colorScheme`, not hardcoded literals (the showcase screens predate this rule in places — match the rule, not those exceptions).
- **Glass cards** carry a 1px inner stroke (`Colors.white.withValues(alpha: 0.1)`); animations stagger via `index * delay`.

## Architecture

`lib/flutter_taste_skill.dart` is the package barrel — it exports `src/components/*` and `src/theme/`. The showcase app (`lib/main.dart`) imports `src/showcase/*` directly, not through the barrel.

- **`src/theme/taste_theme.dart`** — `TasteTheme.createTheme(seed, brightness:)` / `createScheme(...)`. The single source for Material 3 palettes; encodes "taste choices" (warmer/cooler surfaces, tighter typography tracking, elevation-0 cards). Showcase screens build their own `TasteTheme` and wrap content in a local `Theme(...)`.
- **`src/components/`** — reusable primitives the skill prescribes: `HighEndGlassCard`, `MeshGradientBackground`, `TastefulBackground`, `TastefulBentoGrid`, `TastefulCard`, `TastefulEntrance` (staggered-animation wrapper). These are the "correct" implementations of the SKILL.md standards.
- **`src/showcase/`** — four standalone demo screens (`ObsidianCoreScreen`, `CloudPortalScreen`, `GalacticExplorerScreen`, `MonoMinimalistScreen`), each a different aesthetic variant. Wired via `go_router` in `main.dart` (`/obsidian`, `/cloud`, `/galactic`, `/minimal`) behind a `ShowcaseSelector` landing screen.

Key deps: `flutter_animate` (staggered entrances/micro-interactions), `google_fonts` (Space Mono / Inter), `go_router` (showcase nav), `flutter_staggered_grid_view` (real bento packing in `TastefulBentoGrid`).

## Commands

```bash
flutter pub get                 # install deps
flutter analyze                 # lint; deprecated_member_use is escalated to ERROR
bash tool/anti_slop_check.sh    # enforces the Ban List rules analyze can't see
flutter test                    # run widget tests
flutter test test/widget_test.dart --plain-name 'name'   # single test
flutter build web               # build without running (preferred — see below)
```

Per the global rule: **do not run the app** (`flutter run`) unless explicitly asked. Build/analyze/test instead.

## Enforcement (the Ban List is now machinery, not prose)

The skill's "MUST"/"NEVER" rules are enforced by the toolchain so they cannot silently regress:

- **`analysis_options.yaml`** escalates `deprecated_member_use` to an **error**, so `withOpacity` (banned in favor of `withValues(alpha:)`) breaks `flutter analyze`.
- **`tool/anti_slop_check.sh`** is a grep gate for what the Dart analyzer can't see: em-dashes in `lib/`/`test/`, AI-purple (`#7C3AED` / `deepPurple` / `purple`), and boilerplate (`Counter` / `MyApp` / `Hello World`). Exits non-zero on violation; wire it into CI/pre-commit.

Both pass clean as of this writing, and the two widget tests in `test/widget_test.dart` (selector render + navigation) pass.

**What the gate does NOT catch:** contextual misjudgment. A screen can clear every token-level ban and still be wrong for its users (e.g. dark glassmorphism for an elder-care med list). The skill's Design Standards (glass, neon, bento) are genre-specific but written as mandatory, and the "Design Read" that should override them is only advisory. When generating off-genre (utility, accessibility-first, light-mode), treat the glass/neon/bento standards as optional and let the Design Read win.
