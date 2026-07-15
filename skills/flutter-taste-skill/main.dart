import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_taste_skill/src/showcase/obsidian_core.dart';
import 'package:flutter_taste_skill/src/showcase/cloud_portal.dart';
import 'package:flutter_taste_skill/src/showcase/galactic_explorer.dart';
import 'package:flutter_taste_skill/src/showcase/mono_minimalist.dart';
import 'package:flutter_taste_skill/src/showcase/arabesque_atelier.dart';
import 'package:flutter_taste_skill/src/showcase/sorani_modern.dart';

void main() {
  runApp(const TasteShowcaseApp());
}

class TasteShowcaseApp extends StatelessWidget {
  const TasteShowcaseApp({super.key});

  @override
  Widget build(BuildContext context) {
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (context, state) => const ShowcaseSelector()),
        GoRoute(path: '/obsidian', builder: (context, state) => const ObsidianCoreScreen()),
        GoRoute(path: '/cloud', builder: (context, state) => const CloudPortalScreen()),
        GoRoute(path: '/galactic', builder: (context, state) => const GalacticExplorerScreen()),
        GoRoute(path: '/minimal', builder: (context, state) => const MonoMinimalistScreen()),
        GoRoute(path: '/arabic', builder: (context, state) => const ArabesqueAtelierScreen()),
        GoRoute(path: '/kurdish', builder: (context, state) => const SoraniModernScreen()),
      ],
    );

    return MaterialApp.router(
      title: 'Flutter Taste Skill',
      debugShowCheckedModeBanner: false,
      routerConfig: router,
    );
  }
}

class ShowcaseSelector extends StatelessWidget {
  const ShowcaseSelector({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Center(
        child: SingleChildScrollView(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('FLUTTER_TASTE_SKILL_V2', 
                style: GoogleFonts.spaceMono(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 4),
              ),
              const SizedBox(height: 48),
              _SelectorButton(label: 'OBSIDIAN_CORE', onTap: () => context.go('/obsidian'), color: Colors.cyanAccent),
              const SizedBox(height: 16),
              _SelectorButton(label: 'CLOUD_PORTAL', onTap: () => context.go('/cloud'), color: Colors.white70),
              const SizedBox(height: 16),
              _SelectorButton(label: 'GALACTIC_EXPLORER', onTap: () => context.go('/galactic'), color: Colors.pinkAccent),
              const SizedBox(height: 16),
              _SelectorButton(label: 'MONO_MINIMALIST', onTap: () => context.go('/minimal'), color: Colors.white),
              const SizedBox(height: 16),
              _SelectorButton(label: 'ARABESQUE_ATELIER', onTap: () => context.go('/arabic'), color: const Color(0xFFD4AF37)),
              const SizedBox(height: 16),
              _SelectorButton(label: 'SORANI_MODERN', onTap: () => context.go('/kurdish'), color: const Color(0xFFE0584F)),
            ],
          ),
        ),
      ),
    );
  }
}

class _SelectorButton extends StatelessWidget {
  const _SelectorButton({required this.label, required this.onTap, required this.color});
  final String label;
  final VoidCallback onTap;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        width: 260,
        padding: const EdgeInsets.symmetric(vertical: 20),
        decoration: BoxDecoration(
          border: Border.all(color: color.withValues(alpha: 0.3)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(label, 
          textAlign: TextAlign.center, 
          style: GoogleFonts.inter(color: color, fontWeight: FontWeight.bold, letterSpacing: 1),
        ),
      ),
    );
  }
}
