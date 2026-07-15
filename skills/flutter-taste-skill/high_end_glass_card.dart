import 'dart:ui';
import 'package:flutter/material.dart';

/// A "High-End" Glassmorphic Card inspired by Dribbble trends.
class HighEndGlassCard extends StatelessWidget {
  const HighEndGlassCard({
    super.key,
    required this.child,
    this.borderRadius = 24,
    this.blur = 15,
    this.opacity = 0.08,
    this.showGlow = false,
    this.glowColor,
    this.onTap,
  });

  final Widget child;
  final double borderRadius;
  final double blur;
  final double opacity;
  final bool showGlow;
  final Color? glowColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: [
          // Ambient shadow
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
          if (showGlow && glowColor != null)
            BoxShadow(
              color: glowColor!.withValues(alpha: 0.15),
              blurRadius: 40,
              spreadRadius: 5,
            ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(borderRadius),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(borderRadius),
              child: Container(
                decoration: BoxDecoration(
                  color: colorScheme.surface.withValues(alpha: opacity),
                  borderRadius: BorderRadius.circular(borderRadius),
                  // The "High-End" Secret: 1px inner stroke
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.12),
                    width: 1,
                  ),
                ),
                child: child,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
