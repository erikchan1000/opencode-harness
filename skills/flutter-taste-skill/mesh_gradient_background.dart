import 'package:flutter/material.dart';

/// A "Mesh Gradient" background created with overlapping radial gradients.
///
/// Taste Choices:
/// - [Organic Texture]: Avoids linear gradients in favor of flowing colors.
/// - [Dynamic]: Can be animated or adjusted for specific moods.
class MeshGradientBackground extends StatelessWidget {
  const MeshGradientBackground({
    super.key,
    required this.child,
    this.primaryColor,
    this.secondaryColor,
    this.tertiaryColor,
  });

  final Widget child;
  final Color? primaryColor;
  final Color? secondaryColor;
  final Color? tertiaryColor;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final pColor = primaryColor ?? colorScheme.primary.withValues(alpha: 0.15);
    final sColor = secondaryColor ?? colorScheme.secondary.withValues(alpha: 0.1);
    final tColor = tertiaryColor ?? colorScheme.tertiary.withValues(alpha: 0.05);

    return Stack(
      children: [
        // Base dark surface
        Positioned.fill(child: Container(color: colorScheme.surface)),

        // Mesh layers
        Positioned.fill(
          child: CustomPaint(
            painter: _MeshPainter(pColor, sColor, tColor),
          ),
        ),

        // Content
        Positioned.fill(child: child),
      ],
    );
  }
}

class _MeshPainter extends CustomPainter {
  _MeshPainter(this.p, this.s, this.t);
  final Color p, s, t;

  @override
  void paint(Canvas canvas, Size size) {
    final paintP = Paint()
      ..shader = RadialGradient(
        colors: [p, Colors.transparent],
        radius: 1.2,
      ).createShader(Rect.fromLTWH(
          -size.width * 0.2, -size.height * 0.2, size.width, size.height));

    final paintS = Paint()
      ..shader = RadialGradient(
        colors: [s, Colors.transparent],
        radius: 1.0,
      ).createShader(Rect.fromLTWH(
          size.width * 0.5, size.height * 0.5, size.width, size.height));

    final paintT = Paint()
      ..shader = RadialGradient(
        colors: [t, Colors.transparent],
        radius: 0.8,
      ).createShader(Rect.fromLTWH(
          size.width * 0.2, size.height * 0.8, size.width, size.height));

    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paintP);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paintS);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paintT);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
