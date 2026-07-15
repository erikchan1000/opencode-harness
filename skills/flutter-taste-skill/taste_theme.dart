import 'package:flutter/material.dart';

/// A utility to generate "Tasteful" themes for Flutter.
class TasteTheme {
  /// Generates a premium ColorScheme from a seed color with "Taste" adjustments.
  static ColorScheme createScheme(Color seed,
      {Brightness brightness = Brightness.light}) {
    return ColorScheme.fromSeed(
      seedColor: seed,
      brightness: brightness,
      // Taste Choices:
      // - [Surfaces]: We prefer slightly warmer/cooler surfaces than the default
      //   to avoid the "flat grey" look.
      surface: brightness == Brightness.light
          ? const Color(0xFFFDFDFD)
          : const Color(0xFF0F0F0F),
    );
  }

  /// The standard "Taste" theme data.
  static ThemeData createTheme(Color seed,
      {Brightness brightness = Brightness.light}) {
    final scheme = createScheme(seed, brightness: brightness);

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      // Taste Choice: [Typography]
      // Premium apps use slightly tighter tracking and specific weights.
      textTheme: const TextTheme(
        displayLarge:
            TextStyle(fontWeight: FontWeight.w700, letterSpacing: -1.0),
        titleLarge: TextStyle(fontWeight: FontWeight.w600, letterSpacing: -0.5),
        bodyLarge: TextStyle(height: 1.5),
      ),
      // Taste Choice: [CardTheme]
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        color: scheme.surfaceContainerLow,
      ),
      // Taste Choice: [ButtonTheme]
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
    );
  }
}
