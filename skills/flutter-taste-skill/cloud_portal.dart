import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_taste_skill/flutter_taste_skill.dart';

/// --- THE CLOUD PORTAL (Wellness / Lifestyle) ---
class CloudPortalScreen extends StatelessWidget {
  const CloudPortalScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = TasteTheme.createTheme(const Color(0xFFF1F5F9),
        brightness: Brightness.light);
    final colorScheme = theme.colorScheme;

    return Theme(
      data: theme,
      child: Scaffold(
        backgroundColor: const Color(0xFFF8FAFC),
        body: TastefulBackground(
          child: SafeArea(
            bottom: false,
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                // --- Premium Header ---
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 24.0, vertical: 40),
                    child: Column(
                      children: [
                        Text(
                          'SUNDAY, MAY 24',
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 2,
                            color: colorScheme.outline,
                          ),
                        ).animateEntrance(index: 0),
                        const SizedBox(height: 12),
                        Text(
                          'Good Morning,\nBreathe.',
                          textAlign: TextAlign.center,
                          style: GoogleFonts.newsreader(
                            fontSize: 48,
                            fontStyle: FontStyle.italic,
                            fontWeight: FontWeight.w300,
                            height: 1.0,
                          ),
                        ).animateEntrance(index: 1),
                      ],
                    ),
                  ),
                ),

                // --- Main Featured Section ---
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  sliver: SliverToBoxAdapter(
                    child: TastefulCard(
                      padding: EdgeInsets.zero,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(
                            height: 240,
                            width: double.infinity,
                            child: Image.network(
                              // Calm ocean mist (Unsplash). Sets a serene tone
                              // for the wellness hero.
                              'https://images.unsplash.com/photo-1499209974431-9dddcece7f88?w=800&q=80',
                              fit: BoxFit.cover,
                              // Degrade gracefully to the original gradient if
                              // the network image cannot load (offline build).
                              errorBuilder: (context, error, stack) =>
                                  Container(
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    colors: [
                                      colorScheme.primaryContainer,
                                      colorScheme.secondaryContainer,
                                    ],
                                    begin: Alignment.topLeft,
                                    end: Alignment.bottomRight,
                                  ),
                                ),
                                child: Center(
                                  child: Icon(Icons.wb_sunny_outlined,
                                      size: 80,
                                      color: colorScheme.primary
                                          .withValues(alpha: 0.2)),
                                ),
                              ),
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.all(24.0),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'RECOMMENDED FOR YOU',
                                  style: GoogleFonts.inter(
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                      letterSpacing: 1,
                                      color: colorScheme.primary),
                                ),
                                const SizedBox(height: 8),
                                Text('Deep Focus Meditation',
                                    style: theme.textTheme.titleLarge),
                                const SizedBox(height: 4),
                                Text('15 Minutes • Mindful Flow',
                                    style: theme.textTheme.bodyMedium
                                        ?.copyWith(color: colorScheme.outline)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ).animateEntrance(index: 2),
                  ),
                ),

                // --- Horizontal Cards ---
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 32, bottom: 40),
                    child: SizedBox(
                      height: 180,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(horizontal: 24),
                        children: [
                          _SmallCloudCard(
                              title: 'Morning Yoga',
                              icon: Icons.self_improvement,
                              color: Colors.blue.shade50),
                          const SizedBox(width: 16),
                          _SmallCloudCard(
                              title: 'Sleep Soundly',
                              icon: Icons.nightlight_round,
                              color: Colors.indigo.shade50),
                          const SizedBox(width: 16),
                          _SmallCloudCard(
                              title: 'Breath Work',
                              icon: Icons.air,
                              color: Colors.teal.shade50),
                        ],
                      ).animateEntrance(index: 3),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SmallCloudCard extends StatelessWidget {
  const _SmallCloudCard(
      {required this.title, required this.icon, required this.color});
  final String title;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 140,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(32),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: Colors.black54),
          const Spacer(),
          Text(title,
              style: GoogleFonts.inter(
                  fontWeight: FontWeight.bold, fontSize: 14, height: 1.2)),
        ],
      ),
    );
  }
}
