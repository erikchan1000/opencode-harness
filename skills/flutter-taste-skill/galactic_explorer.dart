import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_taste_skill/flutter_taste_skill.dart';

/// --- THE GALACTIC EXPLORER (Sci-Fi / Space) ---
///
/// Design Read:
/// - Industry: Space Exploration / Futuristic Data
/// - Aesthetic: Galactic (Nebula-Core)
/// - Dials: Variance(10), Motion(10), Density(3)
class GalacticExplorerScreen extends StatelessWidget {
  const GalacticExplorerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    // Wrap in a dark Theme so MeshGradientBackground's base surface resolves to
    // a dark color. Without this it falls back to the app's default LIGHT
    // ColorScheme and the whole "deep space" screen renders washed-out white.
    return Theme(
      data: TasteTheme.createTheme(const Color(0xFF0B3D5C),
          brightness: Brightness.dark),
      child: Scaffold(
        backgroundColor: const Color(0xFF020205),
        body: MeshGradientBackground(
          // Nebula palette: teal + deep blue + magenta. No lazy indigo-purple.
          primaryColor: Colors.cyan.withValues(alpha: 0.16),
          secondaryColor: Colors.blue.withValues(alpha: 0.15),
          tertiaryColor: Colors.pinkAccent.withValues(alpha: 0.12),
          child: Stack(
            children: [
              // Floating Star Particles (Simplified for showcase)
              ...List.generate(20, (i) => _PositionedStar(index: i)),

              SafeArea(
                child: CustomScrollView(
                  slivers: [
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 24.0, vertical: 40),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'SYSTEM_STATUS: ACTIVE',
                              style: TextStyle(
                                color: Colors.cyanAccent,
                                fontSize: 12,
                                letterSpacing: 4,
                              ),
                            ).animate().fadeIn().slideX(begin: -0.2),
                            const SizedBox(height: 12),
                            const Text(
                              'Discovery.',
                              style: TextStyle(
                                fontSize: 48,
                                fontWeight: FontWeight.w900,
                                color: Colors.white,
                                letterSpacing: -2,
                              ),
                            )
                                .animate()
                                .fadeIn(delay: 200.ms)
                                .scale(begin: const Offset(0.9, 0.9)),
                          ],
                        ),
                      ),
                    ),
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      sliver: SliverToBoxAdapter(
                        child: TastefulBentoGrid(
                          children: [
                            BentoItem(
                              columnSpan: 4,
                              height: 260,
                              child: HighEndGlassCard(
                                showGlow: true,
                                glowColor: Colors.blueAccent,
                                child: Stack(
                                  children: [
                                    // Faint Earth-from-space photo behind the
                                    // sector readout. Low opacity keeps the
                                    // white text legible; vanishes if offline.
                                    Positioned.fill(
                                      child: Opacity(
                                        opacity: 0.35,
                                        child: Image.network(
                                          'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80',
                                          fit: BoxFit.cover,
                                          errorBuilder:
                                              (context, error, stack) =>
                                                  const SizedBox.shrink(),
                                        ),
                                      ),
                                    ),
                                    Positioned(
                                      right: -30,
                                      bottom: -30,
                                      child: Icon(Icons.public,
                                          size: 200,
                                          color: Colors.white
                                              .withValues(alpha: 0.03)),
                                    ),
                                    const Padding(
                                      padding: EdgeInsets.all(32.0),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text('CURRENT_SECTOR',
                                              style: TextStyle(
                                                  color: Colors.white38)),
                                          Spacer(),
                                          Text('Sector 7-G',
                                              style: TextStyle(
                                                  fontSize: 28,
                                                  fontWeight: FontWeight.bold,
                                                  color: Colors.white)),
                                          SizedBox(height: 8),
                                          Text('Coordinates: 42.001 / -102.99',
                                              style: TextStyle(
                                                  color: Colors.cyanAccent)),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            const BentoItem(
                              columnSpan: 2,
                              height: 180,
                              child: HighEndGlassCard(
                                child: Center(
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(Icons.rocket_launch,
                                          color: Colors.orangeAccent, size: 32),
                                      SizedBox(height: 12),
                                      Text('LAUNCH',
                                          style: TextStyle(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 12,
                                              color: Colors.white)),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                            const BentoItem(
                              columnSpan: 2,
                              height: 180,
                              child: HighEndGlassCard(
                                child: Center(
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(Icons.radar,
                                          color: Colors.greenAccent, size: 32),
                                      SizedBox(height: 12),
                                      Text('SCAN',
                                          style: TextStyle(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 12,
                                              color: Colors.white)),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ).animateEntrance(index: 2),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PositionedStar extends StatelessWidget {
  const _PositionedStar({required this.index});
  final int index;

  @override
  Widget build(BuildContext context) {
    final random = (index * 739) % 1000 / 1000;
    final left = (index * 137) % 100 / 100;
    final top = (index * 241) % 100 / 100;

    return Positioned(
      left: left * 400,
      top: top * 800,
      child: Container(
        width: 2,
        height: 2,
        decoration:
            const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
      )
          .animate(onPlay: (controller) => controller.repeat())
          .fadeIn(duration: (1000 + random * 2000).ms)
          .fadeOut(delay: (1000 + random * 1000).ms),
    );
  }
}
