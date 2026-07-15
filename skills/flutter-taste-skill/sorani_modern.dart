import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_taste_skill/flutter_taste_skill.dart';

/// --- THE SORANI MODERN (Kurdish / Contemporary) ---
///
/// Design Read:
/// - Industry: Kurdish (Sorani) culture / reading app.
/// - Audience: Sorani readers in Iraq / Kurdistan.
/// - Aesthetic: warm modern editorial. Sand canvas, charcoal text, a Kurdish
///   sun-ray motif in gold, a single deep-red accent. Vazirmatn throughout
///   (full Sorani glyph coverage; Estedad or Lalezar are drop-in swaps).
///   Right-to-left.
/// - Dials: Variance(5), Motion(4), Density(3).
class SoraniModernScreen extends StatelessWidget {
  const SoraniModernScreen({super.key});

  static const _sand = Color(0xFFF8F4ED);
  static const _ink = Color(0xFF1F2421);
  static const _red = Color(0xFFB3261E);
  static const _gold = Color(0xFFD9A521);

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: _sand,
        body: Stack(
          children: [
            Positioned(
              top: -120,
              left: -120,
              child: CustomPaint(
                size: const Size(360, 360),
                painter: _SunRays(_gold.withValues(alpha: 0.12)),
              ),
            ),
            SafeArea(
              child: CustomScrollView(
                physics: const BouncingScrollPhysics(),
                slivers: [
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'ناوەندی ڕۆشنبیری',
                            style: GoogleFonts.vazirmatn(
                              color: _red,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ).animateEntrance(index: 0),
                          const SizedBox(height: 6),
                          Text(
                            'بەخێربێیتەوە',
                            style: GoogleFonts.vazirmatn(
                              color: _ink,
                              fontSize: 40,
                              fontWeight: FontWeight.w800,
                              height: 1.1,
                            ),
                          ).animateEntrance(index: 1),
                        ],
                      ),
                    ),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    sliver: SliverToBoxAdapter(
                      child:
                          const _FeatureCard(ink: _ink, red: _red, gold: _gold)
                              .animateEntrance(index: 2),
                    ),
                  ),
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(24, 28, 24, 12),
                      child: Text(
                        'بابەتەکان',
                        style: GoogleFonts.vazirmatn(
                          color: _ink.withValues(alpha: 0.6),
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                  SliverToBoxAdapter(
                    child: SizedBox(
                      height: 132,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        reverse: true,
                        padding: const EdgeInsets.symmetric(horizontal: 24),
                        children: const [
                          _TopicCard(
                              label: 'هۆنراوە',
                              count: '٢٤',
                              ink: _ink,
                              accent: _red),
                          SizedBox(width: 14),
                          _TopicCard(
                              label: 'مێژوو',
                              count: '١٨',
                              ink: _ink,
                              accent: _gold),
                          SizedBox(width: 14),
                          _TopicCard(
                              label: 'زمان',
                              count: '٣١',
                              ink: _ink,
                              accent: _ink),
                        ],
                      ).animateEntrance(index: 3),
                    ),
                  ),
                  const SliverToBoxAdapter(child: SizedBox(height: 40)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FeatureCard extends StatelessWidget {
  const _FeatureCard(
      {required this.ink, required this.red, required this.gold});
  final Color ink;
  final Color red;
  final Color gold;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: ink.withValues(alpha: 0.08),
            blurRadius: 30,
            offset: const Offset(0, 16),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
            child: Stack(
              children: [
                SizedBox(
                  height: 220,
                  width: double.infinity,
                  child: Image.network(
                    // Misty mountains (Unsplash): stands in for Hawraman.
                    'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800&q=80',
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stack) =>
                        Container(color: ink),
                  ),
                ),
                Positioned(
                  right: 16,
                  bottom: 14,
                  left: 16,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('هەورامان',
                          style: GoogleFonts.vazirmatn(
                              color: gold,
                              fontSize: 13,
                              fontWeight: FontWeight.w600)),
                      Text('چیاکانی کوردستان',
                          style: GoogleFonts.vazirmatn(
                              color: Colors.white,
                              fontSize: 24,
                              fontWeight: FontWeight.w700,
                              shadows: const [
                                Shadow(color: Colors.black54, blurRadius: 12)
                              ])),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('پێشنیارکراو',
                    style: GoogleFonts.vazirmatn(
                        color: red, fontSize: 12, fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                Text('مێژووی هۆنراوەی کوردی',
                    style: GoogleFonts.vazirmatn(
                        color: ink, fontSize: 22, fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Text('١٥ خولەک خوێندنەوە',
                    style: GoogleFonts.vazirmatn(
                        color: ink.withValues(alpha: 0.5), fontSize: 14)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TopicCard extends StatelessWidget {
  const _TopicCard(
      {required this.label,
      required this.count,
      required this.ink,
      required this.accent});
  final String label;
  final String count;
  final Color ink;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 150,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: ink.withValues(alpha: 0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
              width: 30,
              height: 4,
              decoration: BoxDecoration(
                  color: accent, borderRadius: BorderRadius.circular(2))),
          const Spacer(),
          Text(label,
              style: GoogleFonts.vazirmatn(
                  color: ink, fontSize: 20, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text('$count بابەت',
              style: GoogleFonts.vazirmatn(
                  color: ink.withValues(alpha: 0.45), fontSize: 13)),
        ],
      ),
    );
  }
}

/// Faint radiating sun rays, a nod to the Kurdish sun, anchored off-canvas.
class _SunRays extends CustomPainter {
  _SunRays(this.color);
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width, size.height);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;
    const rays = 21;
    final radius = size.width;
    for (var i = 0; i < rays; i++) {
      final a = (math.pi / 2) * (i / (rays - 1)); // sweep one quadrant
      const w = 0.018;
      final path = Path()
        ..moveTo(center.dx, center.dy)
        ..lineTo(center.dx - radius * math.cos(a - w),
            center.dy - radius * math.sin(a - w))
        ..lineTo(center.dx - radius * math.cos(a + w),
            center.dy - radius * math.sin(a + w))
        ..close();
      if (i.isEven) canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _SunRays oldDelegate) =>
      oldDelegate.color != color;
}
