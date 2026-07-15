---
name: quant-strategy-research
description: >-
  Quantitative trading-strategy research methodology for short-horizon /
  microstructure and prediction-market edges (e.g. Polymarket/Kalshi BTC
  up-down, order-book lead-lag, convergence/mean-reversion scalps). Use when
  designing or critiquing an ENTRY signal (fair-value-vs-quote basis,
  mispricing, lead-lag), an EXIT policy (optimal stopping, triple-barrier,
  Ornstein-Uhlenbeck mean reversion — NOT fixed-time), labeling/meta-labeling,
  position sizing, transaction-cost hurdles, or the anti-overfitting validation
  gate (purged walk-forward CV, untouched hold-out, multiple-testing
  correction, and live-vs-backtest reconciliation). References the
  awesome-quant library map. Trigger when the user mentions alpha/edge research,
  backtesting rigor, optimal execution/exit, stat-arb, or "go back to the
  drawing board" on a trading strategy.
---

# Quant Strategy Research

A methodology for finding, designing, and *honestly validating* short-horizon
trading edges. Built from hard-won lessons (incl. a convergence scalp that
backtested at +8.75c/share but went **net-negative live** — see "Live
reconciliation"). Bias toward **killing** ideas cheaply over confirming them.

## 0. First principle: state the cost hurdle before anything else

Every edge competes against a round-trip cost. Compute it explicitly and in the
same units as the edge, up front:

- Taker round-trip = `fee_in + fee_out + crossed_spread`. For Polymarket Crypto:
  `fee = 0.07·p·(1-p)` **per taker leg** (maker = 0). A buy-at-ask + sell-at-bid
  scalp pays **two** fees + the spread ≈ **~4.5c/share at p≈0.5**.
- The captured edge must clear the hurdle *out-of-sample, net, after realistic
  fills*. If the mean gross capture ≈ the hurdle, the strategy is null — stop.

## 1. Entry: trade a MEASURED mispricing, not raw momentum

A raw momentum trigger ("|return| > kσ") catches transient spikes that
mean-revert short-term (negative short-horizon autocorrelation) — directionally
right by settlement but adverse on the seconds path. Instead:

- **Define fair value** `p*` from a model (for binary digitals:
  `p* = G((x + μh)/(σ√h))`, x=log-moneyness, h=time-to-expiry, σ=vol forecast),
  then **calibrate** it (isotonic / adaptive-conformal, fit train-only).
- **Basis** = `p* − ask` (to buy) or `bid − p*` (to sell). Enter only when
  `basis > cost + margin`. Triggering on basis *magnitude* (not "first signal in
  a window") removes time-in-window clustering and fires where the quote is
  genuinely stalest.
- **Anti-adverse-selection filters** (the part that makes it work live):
  1. *Persistence*: require the basis to survive k seconds, or compute p* from a
     denoised price so a spike that reverts creates no phantom basis.
  2. *Transient-vs-persistent decomposition*: compare short vs longer return
     (e.g. ret_5s vs ret_30s); skip moves not confirmed by the slower trend.
  3. *Microstructure agreement*: require order-book imbalance / microprice to
     already lean toward fair value (the queue is starting to move).
  4. *Meta-labeling* (López de Prado): primary = "basis > cost"; a secondary
     model predicts P(capture ≥ cost | features) and you trade only when EV>0.

## 2. Exit: state-dependent optimal stopping (never fixed-time)

A fixed "+Ns" exit is the cardinal sin — it banks tiny winners and holds losers
the same N seconds. Two principled replacements:

- **Triple-barrier (López de Prado, AFML)** — practical, few knobs:
  - *Profit-take*: exit when `bid ≥ p* − ε` (quote has essentially converged —
    no edge left, only risk) or a fixed net-of-fee target.
  - *Stop / invalidation*: exit when the **basis flips** (`p* − bid < 0`: fair
    value moved against you, e.g. underlying reversed) — a fair-value stop is
    more principled than a price stop.
  - *Time barrier*: `min(entry + T_max, expiry − buffer)`. Critical for
    digitals: as h→0 the binary variance re-emerges, so the buffer must keep you
    out of the last ~15–30s or you re-import settlement risk.
- **Ornstein-Uhlenbeck mean-reversion** — parameterizes the barriers:
  - Model the gap `g_t = p* − bid_t` as `dg = −θ(g−ḡ)dt + σ_g dW`. Estimate the
    half-life `t½ = ln2/θ` (AR(1): `g_{t+1}=φg_t+ε`, `θ=−ln φ/dt`).
  - Hold while expected marginal capture `θ·(g_t−ḡ)·dt` exceeds marginal holding
    risk; exit at the boundary derived from (θ, σ_g, risk aversion, remaining
    time). Short t½ → exit fast after capture; t½ ≫ time-to-expiry → don't enter.
  - This yields *variable* holding times — the whole point.

## 3. Position sizing

Size by `min(depth_at_touch, notional_cap/price, share_cap)` and, for a
round-trip, also cap by **exit-side depth**. Optional Kelly/fractional-Kelly on
the *net* edge estimate, never the gross.

## 4. Validation gate (do not skip a single step)

1. **Purged walk-forward CV** with an embargo (day boundaries for independent
   events). Every fold tested OOS once. A real edge wins *consistently*; noise
   wins ~half the folds.
2. **Untouched hold-out**, opened exactly once at the end.
3. **Multiple-testing correction** (Benjamini-Hochberg + Bonferroni) across the
   whole parameter family you swept — not just the winner.
4. **Market-clustered bootstrap CI + one-sided p** (cluster by market/day; naive
   IID CIs lie when trades share an event).
5. **Honest nulls**: report what didn't work. Pre-register the config + horizons
   before opening the hold-out.
6. **LIVE-vs-BACKTEST RECONCILIATION** (the lesson that matters most): before
   trusting any backtest, confirm it **reproduces live paper P&L under the
   deployed rule**, simulating the *exact* live execution — real entry timing
   (first-qualifying-in-window, not idealized horizons), fill latency, and exit
   slippage. If the backtest can't reproduce a known live result, the harness is
   flawed (look-ahead / population mismatch) — fix that before believing any
   positive number. Then check the edge on the **most-recent** slice
   (microstructure lead-lag edges decay as others arb them).

## 5. KILL criteria (decide these in advance)

Kill the idea if any hold: (a) backtest can't reproduce live results under the
old rule; (b) edge is ≤0 or insignificant on the most-recent slice / live paper;
(c) net capture < ~1c/trade after realistic fees+slippage (no economic room);
(d) it never beats the simpler benchmark (e.g. hold-to-settlement) on
risk-adjusted return AND there's no capital-velocity / capacity / tail-risk
reason to prefer it. "More data" — not more model flexibility — is the honest
way to resolve a borderline edge.

## 6. awesome-quant library map (curated for this domain)

Source: https://github.com/wilsonfreitas/awesome-quant

- **Mean-reversion / cointegration / OU**: `statsmodels` (ADF, Johansen, OLS for
  half-life), `arch` (GARCH/EWMA vol). No OU simulator in the list — estimate via
  AR(1)/OLS yourself.
- **Labeling / optimal stopping**: `mlfinlab` (López de Prado triple-barrier &
  meta-labeling) — the reference implementation for the exit logic above.
- **Order-book / microstructure & HF backtest**: `hftbacktest` (tick-level,
  queue position, latency — realistic seconds-horizon fills), `nautilus_trader`
  (production-grade event-driven), `PyLOB` (LOB sim). Prefer these over bar-based
  engines (`vectorbt`, `backtrader`, `backtesting.py`, `zipline-reloaded`) for
  sub-minute strategies.
- **Time-series / vol**: `arch` + `statsmodels` cover ~95%. `functime` for
  large-panel feature extraction.
- **Calibration**: not in awesome-quant — use `scikit-learn` (isotonic, Platt),
  `mapie`/`nonconformist` (conformal). Prediction-market last-trade odds are
  ~already calibrated; recalibrate only a *model* p*.
- **Prediction-market access**: `pmxt` (CCXT-style unified Polymarket/Kalshi
  API) for live/paper execution.

Validate any third-party library's assumptions against your own cost model and
PIT discipline before trusting it.

## 7. Workflow checklist

1. Write the cost hurdle (§0). 2. Define fair value + calibrate (§1).
3. Define the basis entry + anti-spike filters (§1). 4. Design a state-dependent
exit (§2). 5. Build a PIT-safe extraction/replay; cache fair-value + price
trajectories. 6. Sweep a *small* parameter family; label with triple-barrier +
continuous capture. 7. Run the full validation gate incl. live reconciliation
(§4). 8. Apply KILL criteria honestly (§5). 9. Only then paper-trade A/B vs the
incumbent; reconcile again before real capital.
