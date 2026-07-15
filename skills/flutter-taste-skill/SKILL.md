---
name: flutter-taste-skill
description: Give AI-generated Flutter UI good taste. Encodes high-end mobile design DNA (bento grids, glassmorphism, mesh gradients, parametric "dials" for variance/motion/density, and a strict anti-slop ban list) into a portable Agent Skill. Use when building or restyling Flutter/Dart screens, when the user wants premium, Apple-like, or Dribbble-quality mobile UI, or wants to avoid generic Material "slop".
license: MIT
metadata:
  tags: [flutter, dart, ui, design, mobile, design-system, glassmorphism]
  homepage: https://github.com/hooshyar/flutter-taste-skill
---

# Flutter Taste Skill v2 (High-End Edition) 🦋

Elevate your Flutter AI generations from "Material Slop" to "Luxury Digital Products." This skill encodes the visual DNA of top-tier Dribbble designs (bento grids, neon depth, and glassmorphism) into a portable instruction set.

## 0️⃣ The "Design Read" (Phase Zero)
Before writing a single widget, you MUST "read the room."
- **Audit:** Identify the industry (e.g., Fintech, Health, Creative).
- **Aesthetic Direction:** Declare a specific variant (Obsidian, Cloud, Brutalist) or a custom "Design Language."
- **Dial Setting:** Confirm the provided parameters (Variance, Motion, Density).

## 🎛️ The Three Dials (Parametric Design)
Adjust intensity on a scale of 1-10. Each band maps to **specific widget
decisions**, not a vibe. Pick a number, then build what the band says.

### `FLUTTER_LAYOUT_VARIANCE` (how the widget tree is shaped)
- `1-3`: One `ListView`/`Column`. Uniform full-width cards. One column, equal padding.
- `4-6`: One full-width hero, then a 2-up `Row` of `Expanded` cells. Mixed cell widths, asymmetric padding.
- `7-9`: `CustomScrollView` + slivers. Bento where one cell spans 2 columns; a `Stack` with an overlapping accent (offset icon/number); a horizontal `ListView` for secondary content.
- `10`: Multi-span bento via `StaggeredGrid` or a custom `MultiChildLayoutDelegate`; `Transform` perspective on the hero; non-linear navigation.

### `FLUTTER_MOTION` (what animates, and how)
- `1-3`: `AnimatedOpacity` or `Hero` only. 200-300ms fades. No entrance choreography.
- `4-6`: `flutter_animate` staggered entrance keyed on `index * 50ms`; press feedback (`scale` to 0.97 on tap down).
- `7-9`: Scroll-driven effects (`SliverAppBar` stretch, opacity/parallax tied to scroll offset); shared-axis page transitions.
- `10`: Rive state machines; physics or magnetic interactions; layout morphs between states.

### `FLUTTER_DENSITY` (spacing and information per screen)
- `1-3`: 32-48px section padding, `height: 1.5` line spacing, body 18-24px, ONE primary action per view. Editorial.
- `4-6`: 16-20px padding, body 14-16px, a few grouped actions. Standard mobile.
- `7-9`: 8-12px gaps, labels 12-13px, compact rows and data tables, multiple live values. Dashboard.

### Worked example: a profile screen at two settings
Same content, two dial sets, two different builds:

- **`VARIANCE:2, MOTION:2, DENSITY:2`** → a `ListView` with a centered avatar, a name, then full-width `TastefulCard`s stacked vertically with 32px gaps; a single fade-in on load.
- **`VARIANCE:8, MOTION:6, DENSITY:5`** → a `CustomScrollView`: a `SliverAppBar` with a stretchy header image, then a bento where the avatar+name cell spans 2 columns and stat cells sit 2-up beside it, an overlapping badge via `Stack`, and cards that stagger in on `index * 60ms` and dip to `scale: 0.97` on press.

If two screens at different dial settings look the same, the dials were ignored.

## 💎 Design Standards (The "High-End" Look)

### 1. Bento Grids & Layout
- NEVER use standard `ListTile` for primary content.
- Use `StaggeredGrid` (or custom `Wrap`/`Row`/`Column` combos) to create modular "cells."
- Every cell should have a distinct visual priority.

### 2. Sophisticated Depth (Glassmorphism)
- **Inner Borders:** Cards MUST have a subtle 1px inner stroke (`Colors.white.withValues(alpha: 0.1)`) to define edges.
- **Backdrop Blur:** Use `BackdropFilter` with `sigma: 10-20` for frosted effects.
- **Layered Shadows:** Combine a soft ambient shadow with a sharp "rim" light.

### 3. Neon Glows & Texture
- Use **Mesh Gradients** (multiple overlapping radial gradients) for organic backgrounds.
- Add a subtle **Noise Texture** (using a shader or a low-opacity PNG) to backgrounds for a tactile feel.
- Accent colors should "glow" using `BoxShadow(spreadRadius: 5, blurRadius: 40)`.

### 4. Direction & Script (RTL / multilingual)
- For Arabic and Sorani Kurdish, wrap the screen in `Directionality(textDirection: TextDirection.rtl, ...)` and let `Row`/`Column`/`start` alignments mirror; never hardcode `left`/`right`.
- Pick fonts that actually cover the script. Arabic: `Amiri` or `Aref Ruqaa` (display), `Reem Kufi` (geometric labels), `Cairo`/`Tajawal` (body). Sorani: `Vazirmatn` (full Sorani glyphs); `Lalezar` lacks some Sorani letters (`ێ ۆ ڵ`) so use it only for display text that avoids them.
- Use the locale's numerals (Eastern Arabic `٠١٢٣٤٥٦٧٨٩`) and reach for native ornament (an 8-point-star khatam field beats a stock photo) over generic "global" decoration.
- Always RENDER and read RTL output before declaring it done: confirm joining, direction, and that no glyph falls back to tofu.

## 🚫 Anti-Slop Ban List (CRITICAL)
1. **EM-DASH BAN:** Physically impossible to type `—` or `–`.
2. **Boilerplate Ban:** No "Hello World," "Counter," or "Sample Item."
3. **AI-Purple Ban:** Ban `#7C3AED` and generic indigo-to-purple gradients.
4. **Scaffold Default Ban:** Never use the default `Scaffold` background/appBar without custom styling.

## 🏁 Hard Pre-flight Check
Before outputting code, verify:
- [ ] Is there a `Design Read` block at the top?
- [ ] Is the `EM-DASH BAN` enforced?
- [ ] Do cards have the "1px inner stroke"?
- [ ] Are animations staggered using `index * delay`?
- [ ] Is `Theme.of(context).colorScheme` used for EVERY color?

---
*Created with Taste. Inspired by Leonxlnx and UI/UX Pro Max. 🦋*
