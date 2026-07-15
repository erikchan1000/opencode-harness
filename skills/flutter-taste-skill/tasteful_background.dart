import 'dart:ui';
import 'package:flutter/material.dart';

/// A "Tasteful" Background that adds texture and depth to a screen.
///
/// Taste Choices:
/// - [Texture]: Uses a subtle gradient to mimic premium lighting.
/// - [Glassmorphism]: Provides a [GlassContainer] for overlay elements.
/// - [Performance]: Uses efficient [CustomPaint] or [BackdropFilter] sparingly.
class TastefulBackground extends StatelessWidget {
  const TastefulBackground({
    super.key,
    required this.child,
    this.useNoise = true,
  });

  final Widget child;
  final bool useNoise;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Stack(
      children: [
        // Base subtle gradient
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  colorScheme.surface,
                  colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                  colorScheme.surface,
                ],
                stops: const [0.0, 0.5, 1.0],
              ),
            ),
          ),
        ),

        // The content
        Positioned.fill(child: child),
      ],
    );
  }
}

/// A "Tasteful" Glassmorphic container.
class GlassContainer extends StatelessWidget {
  const GlassContainer({
    super.key,
    required this.child,
    this.blur = 12,
    this.opacity = 0.1,
    this.borderRadius = 24,
  });

  final Widget child;
  final double blur;
  final double opacity;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: Container(
          decoration: BoxDecoration(
            color: colorScheme.surface.withValues(alpha: opacity),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(
              color: colorScheme.outlineVariant.withValues(alpha: 0.2),
              width: 0.5,
            ),
          ),
          child: child,
        ),
      ),
    );
  }
}
