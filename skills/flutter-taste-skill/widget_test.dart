// Widget tests for the Taste Skill showcase app.
//
// Note: the previous version of this file was the default Flutter counter
// smoke test. That was both broken (it referenced a non-existent `MyApp`)
// and a violation of the skill's own Boilerplate Ban. It now tests the real
// `TasteShowcaseApp` selector and its navigation.

import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_taste_skill/main.dart';

void main() {
  testWidgets('Showcase selector renders all four aesthetic variants',
      (WidgetTester tester) async {
    await tester.pumpWidget(const TasteShowcaseApp());
    await tester.pump();

    expect(find.text('FLUTTER_TASTE_SKILL_V2'), findsOneWidget);
    expect(find.text('OBSIDIAN_CORE'), findsOneWidget);
    expect(find.text('CLOUD_PORTAL'), findsOneWidget);
    expect(find.text('GALACTIC_EXPLORER'), findsOneWidget);
    expect(find.text('MONO_MINIMALIST'), findsOneWidget);
    expect(find.text('ARABESQUE_ATELIER'), findsOneWidget);
    expect(find.text('SORANI_MODERN'), findsOneWidget);
  });

  testWidgets('Tapping a variant navigates away from the selector',
      (WidgetTester tester) async {
    await tester.pumpWidget(const TasteShowcaseApp());
    await tester.pump();

    await tester.tap(find.text('OBSIDIAN_CORE'));
    // Avoid pumpAndSettle: some showcase screens run looping animations that
    // never settle. Advance time manually past the entrance animations.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 800));

    expect(find.text('FLUTTER_TASTE_SKILL_V2'), findsNothing);
  });
}
