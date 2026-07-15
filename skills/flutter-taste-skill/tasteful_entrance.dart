import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

/// A "Tasteful" wrapper for staggered entrance animations.
///
/// Taste Choices:
/// - [Curve]: Uses [Curves.easeOutQuart] for a smooth, natural feel.
/// - [Motion]: Combines a subtle vertical slide with a fade-in.
/// - [Stagger]: Offsets animations by a specific [index] to create a "wave" effect.
class TastefulEntrance extends StatelessWidget {
  const TastefulEntrance({
    super.key,
    required this.child,
    this.index = 0,
    this.delay = 50,
  });

  final Widget child;
  final int index;
  final int delay;

  @override
  Widget build(BuildContext context) {
    return child
        .animate()
        .fadeIn(
          duration: 600.ms,
          curve: Curves.easeOutQuart,
          delay: (index * delay).ms,
        )
        .slideY(
          begin: 0.1,
          end: 0,
          duration: 600.ms,
          curve: Curves.easeOutQuart,
        );
  }
}

/// Extension to easily wrap widgets with [TastefulEntrance].
extension TastefulEntranceX on Widget {
  Widget animateEntrance({int index = 0, int delay = 50}) {
    return TastefulEntrance(
      index: index,
      delay: delay,
      child: this,
    );
  }
}
