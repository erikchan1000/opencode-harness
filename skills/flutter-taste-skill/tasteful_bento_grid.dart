import 'package:flutter/material.dart';
import 'package:flutter_staggered_grid_view/flutter_staggered_grid_view.dart';

/// A "Tasteful" Bento-style grid layout.
///
/// Taste Choices:
/// - [Layout]: A true staggered grid (not a uniform `GridView`). Cells declare
///   a [BentoItem.columnSpan] and either a fixed [BentoItem.height] or a
///   [BentoItem.rowSpan], so a tall hero can sit beside two stacked cells.
/// - [Spacing]: Consistent, premium 16px gutters.
/// - [Composition]: Built on `StaggeredGrid` (the pattern this skill
///   prescribes) rather than a hand-rolled `Wrap`, so packing is real.
///
/// Place inside a scroll view (e.g. a `SliverToBoxAdapter`); the grid itself
/// does not scroll, it lays out to its content height.
class TastefulBentoGrid extends StatelessWidget {
  const TastefulBentoGrid({
    super.key,
    required this.children,
    this.crossAxisCount = 4,
    this.mainAxisSpacing = 16,
    this.crossAxisSpacing = 16,
  });

  /// The bento cells.
  final List<BentoItem> children;

  /// Number of columns the grid is divided into.
  final int crossAxisCount;

  /// Vertical gutter between cells.
  final double mainAxisSpacing;

  /// Horizontal gutter between cells.
  final double crossAxisSpacing;

  @override
  Widget build(BuildContext context) {
    return StaggeredGrid.count(
      crossAxisCount: crossAxisCount,
      mainAxisSpacing: mainAxisSpacing,
      crossAxisSpacing: crossAxisSpacing,
      children: [
        for (final item in children) item._toTile(),
      ],
    );
  }
}

/// A single cell in a [TastefulBentoGrid].
///
/// Provide a fixed [height] for an exact pixel extent, or a [rowSpan] to size
/// the cell as a multiple of the column width (square-ish bento cells). If
/// neither is given the cell falls back to a 150px extent.
class BentoItem {
  const BentoItem({
    required this.child,
    this.columnSpan = 1,
    this.height,
    this.rowSpan,
  }) : assert(columnSpan >= 1, 'columnSpan must be at least 1');

  final Widget child;

  /// How many columns this cell occupies.
  final int columnSpan;

  /// Fixed pixel height for the cell. Takes precedence over [rowSpan].
  final double? height;

  /// Height expressed as a number of grid cells (used when [height] is null).
  final int? rowSpan;

  StaggeredGridTile _toTile() {
    if (height != null) {
      return StaggeredGridTile.extent(
        crossAxisCellCount: columnSpan,
        mainAxisExtent: height!,
        child: child,
      );
    }
    return StaggeredGridTile.count(
      crossAxisCellCount: columnSpan,
      mainAxisCellCount: rowSpan ?? 1,
      child: child,
    );
  }
}
