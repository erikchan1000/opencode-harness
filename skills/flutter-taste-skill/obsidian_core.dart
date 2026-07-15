import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_taste_skill/flutter_taste_skill.dart';

/// --- THE OBSIDIAN CORE (Fintech / Crypto Pro) ---
class ObsidianCoreScreen extends StatelessWidget {
  const ObsidianCoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = TasteTheme.createTheme(const Color(0xFF0F172A), brightness: Brightness.dark);

    return Theme(
      data: theme,
      child: Scaffold(
        backgroundColor: const Color(0xFF020617),
        body: MeshGradientBackground(
          primaryColor: Colors.cyan.withValues(alpha: 0.08),
          secondaryColor: Colors.indigo.withValues(alpha: 0.12),
          child: SafeArea(
            bottom: false,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20.0),
              child: CustomScrollView(
                physics: const BouncingScrollPhysics(),
                slivers: [
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.only(top: 24, bottom: 32),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('PORTFOLIO_V2', 
                                style: GoogleFonts.spaceMono(
                                  fontSize: 12,
                                  letterSpacing: 2,
                                  color: Colors.cyanAccent.withValues(alpha: 0.6),
                                  fontWeight: FontWeight.bold,
                                ),
                              ).animateEntrance(index: 0),
                              const SizedBox(height: 4),
                              Text('Obsidian.', 
                                style: GoogleFonts.inter(
                                  fontSize: 32,
                                  fontWeight: FontWeight.w900,
                                  letterSpacing: -1,
                                ),
                              ).animateEntrance(index: 1),
                            ],
                          ),
                          const HighEndGlassCard(
                            borderRadius: 16,
                            opacity: 0.1,
                            child: Padding(
                              padding: EdgeInsets.all(12.0),
                              child: Icon(Icons.qr_code_scanner, size: 20),
                            ),
                          ).animateEntrance(index: 2),
                        ],
                      ),
                    ),
                  ),

                  SliverToBoxAdapter(
                    child: TastefulBentoGrid(
                      crossAxisCount: 4,
                      children: [
                        BentoItem(
                          columnSpan: 4,
                          height: 220,
                          child: HighEndGlassCard(
                            showGlow: true,
                            glowColor: Colors.cyanAccent,
                            child: Padding(
                              padding: const EdgeInsets.all(24.0),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      const Icon(Icons.wallet, size: 16, color: Colors.cyanAccent),
                                      const SizedBox(width: 8),
                                      Text('TOTAL BALANCE', 
                                        style: GoogleFonts.inter(
                                          fontSize: 10, 
                                          fontWeight: FontWeight.bold,
                                          letterSpacing: 1,
                                          color: Colors.white.withValues(alpha: 0.5),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const Spacer(),
                                  Text('\$482,910.55', 
                                    style: GoogleFonts.spaceMono(
                                      fontSize: 40,
                                      fontWeight: FontWeight.bold,
                                      letterSpacing: -2,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Row(
                                    children: [
                                      const Icon(Icons.trending_up, size: 14, color: Colors.greenAccent),
                                      const SizedBox(width: 4),
                                      Text('+12.4% THIS MONTH', 
                                        style: GoogleFonts.inter(
                                          fontSize: 10,
                                          fontWeight: FontWeight.w900,
                                          color: Colors.greenAccent,
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        
                        BentoItem(
                          columnSpan: 2,
                          height: 160,
                          child: HighEndGlassCard(
                            child: Padding(
                              padding: const EdgeInsets.all(20.0),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('MARKET', style: GoogleFonts.inter(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.white30)),
                                  const Spacer(),
                                  const Icon(Icons.bar_chart, color: Colors.cyanAccent),
                                  const SizedBox(height: 8),
                                  Text('BTC \$64K', style: GoogleFonts.spaceMono(fontWeight: FontWeight.bold)),
                                ],
                              ),
                            ),
                          ),
                        ),

                        BentoItem(
                          columnSpan: 2,
                          height: 160,
                          child: HighEndGlassCard(
                            child: Padding(
                              padding: const EdgeInsets.all(20.0),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('RISK', style: GoogleFonts.inter(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.white30)),
                                  const Spacer(),
                                  const Icon(Icons.security, color: Colors.orangeAccent),
                                  const SizedBox(height: 8),
                                  Text('LOW_VOL', style: GoogleFonts.spaceMono(fontWeight: FontWeight.bold)),
                                ],
                              ),
                            ),
                          ),
                        ),

                        const BentoItem(
                          columnSpan: 4,
                          height: 300,
                          child: HighEndGlassCard(
                            opacity: 0.05,
                            child: Column(
                              children: [
                                _AssetRow(icon: Icons.currency_bitcoin, name: 'Bitcoin', symbol: 'BTC', value: '\$32,100', change: '+2.4%'),
                                Divider(height: 1, color: Colors.white10),
                                _AssetRow(icon: Icons.api_outlined, name: 'Ethereum', symbol: 'ETH', value: '\$2,450', change: '-1.2%'),
                                Divider(height: 1, color: Colors.white10),
                                _AssetRow(icon: Icons.token_outlined, name: 'Solana', symbol: 'SOL', value: '\$145', change: '+14.8%'),
                                Divider(height: 1, color: Colors.white10),
                                _AssetRow(icon: Icons.diamond_outlined, name: 'Polkadot', symbol: 'DOT', value: '\$7.2', change: '+0.5%'),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ).animateEntrance(index: 3),
                  ),
                  
                  const SliverToBoxAdapter(child: SizedBox(height: 40)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AssetRow extends StatelessWidget {
  const _AssetRow({
    required this.icon,
    required this.name,
    required this.symbol,
    required this.value,
    required this.change,
  });

  final IconData icon;
  final String name;
  final String symbol;
  final String value;
  final String change;

  @override
  Widget build(BuildContext context) {
    final isPositive = change.startsWith('+');
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 20, color: Colors.white70),
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.bold, fontSize: 14)),
              Text(symbol, style: GoogleFonts.inter(fontSize: 10, color: Colors.white30)),
            ],
          ),
          const Spacer(),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(value, style: GoogleFonts.spaceMono(fontWeight: FontWeight.bold, fontSize: 14)),
              Text(change, 
                style: GoogleFonts.inter(
                  fontSize: 10, 
                  fontWeight: FontWeight.bold,
                  color: isPositive ? Colors.greenAccent : Colors.redAccent,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
