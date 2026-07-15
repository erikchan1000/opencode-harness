import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_taste_skill/flutter_taste_skill.dart';

/// --- THE ARABESQUE ATELIER (Arabic / Heritage) ---
///
/// Design Read:
/// - Industry: Arabic cultural / heritage collection.
/// - Audience: readers of Arabic; appreciators of Islamic art.
/// - Aesthetic: traditional ornament. Cream + emerald + gold, an 8-point-star
///   (khatam) geometric field, calligraphic display (Aref Ruqaa), geometric
///   Kufi labels (Reem Kufi), and a Naskh-style body (Cairo). Right-to-left.
/// - Dials: Variance(6), Motion(4), Density(3).
class ArabesqueAtelierScreen extends StatelessWidget {
  const ArabesqueAtelierScreen({super.key});

  static const _cream = Color(0xFFF6EEDD);
  static const _emerald = Color(0xFF0B3D2E);
  static const _gold = Color(0xFFB8902F);

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: _cream,
        body: Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(
                painter: _KhatamField(_gold.withValues(alpha: 0.06)),
              ),
            ),
            SafeArea(
              child: CustomScrollView(
                physics: const BouncingScrollPhysics(),
                slivers: [
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(24, 36, 24, 8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'المجموعة',
                            style: GoogleFonts.reemKufi(
                              color: _gold,
                              fontSize: 14,
                              letterSpacing: 2,
                              fontWeight: FontWeight.w600,
                            ),
                          ).animateEntrance(index: 0),
                          const SizedBox(height: 4),
                          Text(
                            'فنُّ الزَّخرفة',
                            style: GoogleFonts.arefRuqaa(
                              color: _emerald,
                              fontSize: 52,
                              fontWeight: FontWeight.w700,
                              height: 1.1,
                            ),
                          ).animateEntrance(index: 1),
                        ],
                      ),
                    ),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
                    sliver: SliverToBoxAdapter(
                      child: const _HeroPlate(gold: _gold, emerald: _emerald)
                          .animateEntrance(index: 2),
                    ),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    sliver: SliverToBoxAdapter(
                      child: _Frieze(color: _gold.withValues(alpha: 0.5)),
                    ),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(24, 20, 24, 40),
                    sliver: SliverToBoxAdapter(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'الأنماط',
                            style: GoogleFonts.reemKufi(
                              color: _emerald.withValues(alpha: 0.7),
                              fontSize: 13,
                              letterSpacing: 2,
                            ),
                          ),
                          const SizedBox(height: 12),
                          const _PatternRow(
                              name: 'النجمة الثمانية',
                              era: 'القرن ٨',
                              gold: _gold,
                              emerald: _emerald),
                          _GoldDivider(color: _gold.withValues(alpha: 0.3)),
                          const _PatternRow(
                              name: 'التوريق',
                              era: 'القرن ١٠',
                              gold: _gold,
                              emerald: _emerald),
                          _GoldDivider(color: _gold.withValues(alpha: 0.3)),
                          const _PatternRow(
                              name: 'المقرنص',
                              era: 'القرن ١٢',
                              gold: _gold,
                              emerald: _emerald),
                        ],
                      ).animateEntrance(index: 3),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HeroPlate extends StatelessWidget {
  const _HeroPlate({required this.gold, required this.emerald});
  final Color gold;
  final Color emerald;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: gold, width: 2),
        boxShadow: [
          BoxShadow(
            color: emerald.withValues(alpha: 0.15),
            blurRadius: 30,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: Stack(
          children: [
            SizedBox(
              height: 280,
              width: double.infinity,
              child: CustomPaint(
                // A generated khatam (8-point-star) tessellation. The screen's
                // subject IS ornament, so the hero is drawn, not photographed.
                painter: _KhatamHero(gold: gold, emerald: emerald),
              ),
            ),
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.transparent,
                      emerald.withValues(alpha: 0.85),
                    ],
                    stops: const [0.45, 1.0],
                  ),
                ),
              ),
            ),
            Positioned(
              right: 20,
              bottom: 20,
              left: 20,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'زخرفة هندسية',
                    style: GoogleFonts.reemKufi(
                      color: gold,
                      fontSize: 13,
                      letterSpacing: 1.5,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'خاتم سليمان',
                    style: GoogleFonts.arefRuqaa(
                      color: Colors.white,
                      fontSize: 30,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    'الأندلس · ٧٧٦ هـ',
                    style: GoogleFonts.cairo(
                      color: Colors.white.withValues(alpha: 0.85),
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PatternRow extends StatelessWidget {
  const _PatternRow(
      {required this.name,
      required this.era,
      required this.gold,
      required this.emerald});
  final String name;
  final String era;
  final Color gold;
  final Color emerald;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 26,
          height: 26,
          child: CustomPaint(painter: _StarMark(gold)),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Text(
            name,
            style: GoogleFonts.cairo(
                color: emerald, fontSize: 20, fontWeight: FontWeight.w600),
          ),
        ),
        Text(
          era,
          style: GoogleFonts.cairo(
              color: emerald.withValues(alpha: 0.5), fontSize: 13),
        ),
      ],
    );
  }
}

class _GoldDivider extends StatelessWidget {
  const _GoldDivider({required this.color});
  final Color color;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 18),
      child: Divider(height: 1, color: color));
}

class _Frieze extends StatelessWidget {
  const _Frieze({required this.color});
  final Color color;
  @override
  Widget build(BuildContext context) => SizedBox(
      height: 24,
      child: CustomPaint(size: Size.infinite, painter: _FriezePainter(color)));
}

/// Returns an 8-point star (khatam) path centered at [c] with outer radius [r].
Path _eightPointStar(Offset c, double r) {
  final path = Path();
  const points = 8;
  final inner = r * 0.41;
  for (var i = 0; i < points * 2; i++) {
    final radius = i.isEven ? r : inner;
    final angle = (math.pi / points) * i - math.pi / 2;
    final p = Offset(
        c.dx + radius * math.cos(angle), c.dy + radius * math.sin(angle));
    i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
  }
  return path..close();
}

/// A rich emerald hero panel filled with a gold khatam tessellation.
class _KhatamHero extends CustomPainter {
  _KhatamHero({required this.gold, required this.emerald});
  final Color gold;
  final Color emerald;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..color = emerald);
    // Soft central glow so the panel is not flat.
    canvas.drawRect(
      rect,
      Paint()
        ..shader = RadialGradient(
          colors: [gold.withValues(alpha: 0.20), emerald],
          radius: 0.9,
        ).createShader(rect),
    );
    final stroke = Paint()
      ..color = gold.withValues(alpha: 0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    final fill = Paint()..color = gold.withValues(alpha: 0.12);
    const step = 56.0;
    for (var y = 0.0; y <= size.height + step; y += step) {
      for (var x = 0.0; x <= size.width + step; x += step) {
        final star = _eightPointStar(Offset(x, y), 26);
        canvas.drawPath(star, fill);
        canvas.drawPath(star, stroke);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _KhatamHero oldDelegate) =>
      oldDelegate.gold != gold || oldDelegate.emerald != emerald;
}

/// Faint tiled field of khatam stars behind the screen.
class _KhatamField extends CustomPainter {
  _KhatamField(this.color);
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    const step = 64.0;
    for (var y = 0.0; y < size.height + step; y += step) {
      for (var x = 0.0; x < size.width + step; x += step) {
        canvas.drawPath(_eightPointStar(Offset(x, y), 22), paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _KhatamField oldDelegate) =>
      oldDelegate.color != color;
}

/// A single filled star used as a list marker.
class _StarMark extends CustomPainter {
  _StarMark(this.color);
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawPath(
      _eightPointStar(size.center(Offset.zero), size.width / 2),
      Paint()..color = color,
    );
  }

  @override
  bool shouldRepaint(covariant _StarMark oldDelegate) =>
      oldDelegate.color != color;
}

/// A horizontal frieze of linked stars used as an ornamental divider.
class _FriezePainter extends CustomPainter {
  _FriezePainter(this.color);
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    const r = 9.0;
    final y = size.height / 2;
    for (var x = r; x < size.width; x += r * 2.4) {
      canvas.drawPath(_eightPointStar(Offset(x, y), r), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _FriezePainter oldDelegate) =>
      oldDelegate.color != color;
}
