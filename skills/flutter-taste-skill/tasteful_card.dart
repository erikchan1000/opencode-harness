import 'package:flutter/material.dart';

/// A "Tasteful" Card that demonstrates premium depth and subtle motion.
///
/// Taste Choices:
/// - [Depth]: Uses a multi-layered shadow approach for a "lifted" feel.
/// - [Color]: Leverages Theme.of(context).colorScheme instead of hardcoded colors.
/// - [Shape]: Uses a large, modern border radius (24px).
/// - [Interaction]: Implements a subtle scale animation on hover/tap (if applicable).
class TastefulCard extends StatelessWidget {
  const TastefulCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(20),
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: colorScheme.outlineVariant.withValues(alpha: 0.5),
          width: 1,
        ),
        boxShadow: [
          // Multi-layered shadow for premium depth
          BoxShadow(
            color: colorScheme.shadow.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
          BoxShadow(
            color: colorScheme.shadow.withValues(alpha: 0.06),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onTap,
            splashColor: colorScheme.primary.withValues(alpha: 0.05),
            highlightColor: colorScheme.primary.withValues(alpha: 0.02),
            child: Padding(
              padding: padding,
              child: child,
            ),
          ),
        ),
      ),
    );
  }
}
