import 'package:flutter/material.dart';
import 'package:flutter_taste_skill/flutter_taste_skill.dart';

/// --- THE MONO-MINIMALIST (Architecture / High-End Gallery) ---
///
/// Design Read:
/// - Industry: Luxury Real Estate / High-End Architecture
/// - Audience: High-Net-Worth Individuals
/// - Aesthetic: Mono-Luxury (Minimalist Serif)
/// - Dials: Variance(7), Motion(4), Density(1)
class MonoMinimalistScreen extends StatelessWidget {
  const MonoMinimalistScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: CustomScrollView(
          physics: const BouncingScrollPhysics(),
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 32.0, vertical: 60),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'EST. 1994',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 3,
                        color: Colors.black26,
                      ),
                    ).animateEntrance(index: 0),
                    const SizedBox(height: 24),
                    const Text(
                      'Simplicity is the\nultimate sophistication.',
                      style: TextStyle(
                        fontSize: 42,
                        fontWeight: FontWeight.w400,
                        height: 1.1,
                        fontStyle: FontStyle.italic,
                      ),
                    ).animateEntrance(index: 1),
                  ],
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              sliver: SliverToBoxAdapter(
                child: ColorFiltered(
                  // Desaturate to keep the strict mono / editorial aesthetic.
                  colorFilter: const ColorFilter.matrix(<double>[
                    0.2126,
                    0.7152,
                    0.0722,
                    0,
                    0,
                    0.2126,
                    0.7152,
                    0.0722,
                    0,
                    0,
                    0.2126,
                    0.7152,
                    0.0722,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1,
                    0,
                  ]),
                  child: SizedBox(
                    height: 400,
                    width: double.infinity,
                    child: Image.network(
                      // Architectural facade (Unsplash).
                      'https://images.unsplash.com/photo-1486718448742-163732cd1544?w=800&q=80',
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stack) => Container(
                        color: const Color(0xFFF5F5F5),
                        child: Center(
                          child: Icon(Icons.architecture,
                              size: 100,
                              color: Colors.black.withValues(alpha: 0.05)),
                        ),
                      ),
                    ),
                  ),
                ).animateEntrance(index: 2),
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(32.0),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('THE ARCHIVE',
                        style: TextStyle(
                            fontWeight: FontWeight.bold,
                            letterSpacing: 2,
                            fontSize: 12)),
                    SizedBox(height: 32),
                    _MinimalItem(title: 'Structure 01', year: '2023'),
                    Divider(height: 40, color: Colors.black12),
                    _MinimalItem(title: 'Structure 02', year: '2024'),
                    Divider(height: 40, color: Colors.black12),
                    _MinimalItem(title: 'Structure 03', year: '2025'),
                  ],
                ).animateEntrance(index: 3),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MinimalItem extends StatelessWidget {
  const _MinimalItem({required this.title, required this.year});
  final String title;
  final String year;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(title,
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w500)),
        Text(year, style: const TextStyle(color: Colors.black38, fontSize: 12)),
      ],
    );
  }
}
