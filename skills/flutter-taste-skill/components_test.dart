import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_taste_skill/flutter_taste_skill.dart';

/// Pumps [child] inside a minimal themed app so components have a
/// [Directionality], [MediaQuery], and a [Theme] to read from.
Future<void> pumpInApp(WidgetTester tester, Widget child) {
  return tester.pumpWidget(
    MaterialApp(
      theme: TasteTheme.createTheme(const Color(0xFF0B6E4F)),
      home: Scaffold(body: child),
    ),
  );
}

void main() {
  group('TasteTheme', () {
    test('dark scheme uses the tasteful dark surface', () {
      final scheme = TasteTheme.createScheme(const Color(0xFF0F172A),
          brightness: Brightness.dark);
      expect(scheme.brightness, Brightness.dark);
      expect(scheme.surface, const Color(0xFF0F0F0F));
    });

    test('light scheme uses the tasteful light surface', () {
      final scheme = TasteTheme.createScheme(const Color(0xFF0F172A));
      expect(scheme.brightness, Brightness.light);
      expect(scheme.surface, const Color(0xFFFDFDFD));
    });

    test('theme is Material 3 with elevation-0 cards', () {
      final theme = TasteTheme.createTheme(const Color(0xFF0B6E4F));
      expect(theme.useMaterial3, isTrue);
      expect(theme.cardTheme.elevation, 0);
    });
  });

  group('TastefulBentoGrid', () {
    testWidgets('renders every cell', (tester) async {
      await pumpInApp(
        tester,
        const TastefulBentoGrid(
          children: [
            BentoItem(columnSpan: 4, height: 120, child: Text('hero')),
            BentoItem(columnSpan: 2, height: 80, child: Text('left')),
            BentoItem(columnSpan: 2, height: 80, child: Text('right')),
          ],
        ),
      );
      expect(find.text('hero'), findsOneWidget);
      expect(find.text('left'), findsOneWidget);
      expect(find.text('right'), findsOneWidget);
    });

    testWidgets('a wider cell spans more horizontal space than a narrow one',
        (tester) async {
      await pumpInApp(
        tester,
        const TastefulBentoGrid(
          crossAxisCount: 4,
          children: [
            BentoItem(columnSpan: 4, height: 100, child: SizedBox.expand()),
            BentoItem(columnSpan: 1, height: 100, child: SizedBox.expand()),
          ],
        ),
      );
      final wide = tester.getSize(find.byType(SizedBox).at(0)).width;
      final narrow = tester.getSize(find.byType(SizedBox).at(1)).width;
      expect(wide, greaterThan(narrow));
    });

    test('BentoItem rejects a columnSpan below 1', () {
      expect(() => BentoItem(columnSpan: 0, child: const SizedBox()),
          throwsAssertionError);
    });
  });

  group('components build without error', () {
    testWidgets('HighEndGlassCard', (tester) async {
      await pumpInApp(
          tester, const HighEndGlassCard(child: SizedBox(width: 50, height: 50)));
      expect(find.byType(HighEndGlassCard), findsOneWidget);
    });

    testWidgets('TastefulCard responds to tap', (tester) async {
      var tapped = false;
      await pumpInApp(
        tester,
        TastefulCard(onTap: () => tapped = true, child: const Text('tap me')),
      );
      await tester.tap(find.text('tap me'));
      expect(tapped, isTrue);
    });

    testWidgets('GlassContainer', (tester) async {
      await pumpInApp(
          tester, const GlassContainer(child: SizedBox(width: 50, height: 50)));
      expect(find.byType(GlassContainer), findsOneWidget);
    });

    testWidgets('MeshGradientBackground and TastefulBackground', (tester) async {
      await pumpInApp(
          tester, const MeshGradientBackground(child: SizedBox.expand()));
      expect(find.byType(MeshGradientBackground), findsOneWidget);
      await pumpInApp(
          tester, const TastefulBackground(child: SizedBox.expand()));
      expect(find.byType(TastefulBackground), findsOneWidget);
    });

    testWidgets('animateEntrance wraps its child', (tester) async {
      await pumpInApp(tester, const Text('fade in').animateEntrance(index: 2));
      expect(find.byType(TastefulEntrance), findsOneWidget);
      expect(find.text('fade in'), findsOneWidget);
      // Let the one-shot entrance animation finish so no timer outlives the test.
      await tester.pumpAndSettle();
    });
  });
}
