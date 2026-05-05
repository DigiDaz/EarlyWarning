# Severity disagreement map — 2026-05-05

Diagnostic snapshot of how the dashboard's render surfaces classify
each commodity's severity. Captured by importing `dashboard.py` via
a streamlit-mock harness and reading the live `intel_cards`,
`commodity_cards`, `threshold_rows_html`, and `equity_changes`
module-level state. No code changes here — this is a problem
description, not a fix proposal.

## Captured module state at audit time

- `helium_exhausted()` → `True`
- `helium_severity_tier()` → `"warning"` (post-commit-1)
- `CO2_BYPRODUCT_BREACH` → `True` (EU ammonia at 35%, threshold 40%)
- `OECD_INVENTORY_BREACH` → `True`
- `malacca_shadow_active(intel_data)` → `False`
- Equity proxy 1-day moves (`equity_changes`):
  - `CF` (urea / fertilizer): +1.80% — NOMINAL
  - `DOW` (PE / PP resins): +1.37% — NOMINAL
  - `APD` (helium / industrial gas): +1.39% — NOMINAL
  - `JETS` (aviation / jet fuel): +2.01% — NOMINAL
  - `WDC` (AI storage / HDD): +7.20% — WARNING
  - `STX` (AI storage / HDD): +4.32% — NOMINAL

## Per-commodity surface matrix

| Commodity | Tile | Threshold Monitor | Equity proxy | Notes |
| --- | --- | --- | --- | --- |
| **Helium** | WARNING (amber, FORCE MAJEURE ACTIVE) | WARNING ✓ (FORCE MAJEURE) | APD NOMINAL (+1.39%) | Tile + threshold aligned by today's commit 1. Equity proxy disagrees — smart-money cross-check candidate. |
| **CO2 byproduct (EU ammonia)** | BREACH (red) | BREACHED (CO2 EXHAUSTED) | APD NOMINAL (+1.39%, same proxy as helium — covers industrial gas) | Tile + threshold aligned. Equity proxy disagrees with both — smart-money cross-check candidate. |
| **OECD oil inventory** | BREACH (red, < 842MB) | BREACHED (CRITICAL) | n/a (no direct equity) | Both red, agreement. |
| **Brent crude** | BREACH (red) | NOMINAL × 2 (`> $130` and `> $115` both NOMINAL) | n/a | **Disagreement.** Tile severity is forced by the `OECD_INVENTORY_BREACH` rule, not by a Brent threshold being tripped. The breach "comes from somewhere else" and is invisible at the threshold-row level. |
| **Hormuz** | BREACH (red, ~4 ships/day) | BREACHED × 2 (`< 30/day`, `< 20/day`) | n/a | Both red, agreement. |
| **Urea** | WARNING (amber) | Mixed: `> $600/t` BREACHED, `> $800/t` NOMINAL | CF NOMINAL (+1.80%) | **Three-way disagreement.** Tile WARNING, lower threshold BREACHED, upper threshold NOMINAL, equity NOMINAL. Internally consistent (it is between the two thresholds), but no single surface captures that nuance. |
| **Diesel crack** | BREACH (red) | BREACHED (`> $50/bbl`) | JETS NOMINAL (+2.01%, indirect) | Tile + threshold aligned. JETS is jet-fuel-aviation rather than diesel directly, so not a clean cross-check. |
| **Gold** | WARNING (amber, technical $4571 support) | NOMINAL (`> $4600`) | n/a | **Disagreement.** Tile WARNING is driven by the editorial override anchoring on the $4,571 technical level after the $4,660 ceiling break. Threshold `> $4600` reads NOMINAL because the live spot is below it. The threshold doesn't know about technical support levels. |
| **Silver** | WARNING (amber) | NOMINAL (`> $75`) | n/a | **Disagreement.** Same pattern as gold — tile WARNING from a price-action context the simple threshold doesn't capture. |
| **TTF gas** | NOMINAL | NOMINAL × 2 | n/a | Agreement. |
| **Panama (Neopanamax)** | NOMINAL | NOMINAL × 2 (`> $2.5M`, `> $4.0M`) | n/a | Agreement on the visible state, but the tile value is being filled by the EDITORIAL_FACTS Panama fallback ($385K) — not a "live nominal" reading. The threshold isn't picking that up because $385K is well below both tripwires. |
| **EU gas storage** | STALE (data unavailable) | NOMINAL (`< 20%`) | n/a | **Data-quality disagreement.** Tile says STALE because AGSI+ live read came back None; threshold defaults to NOMINAL because the breach flag is False without live data. Same fact rendered as two incompatible labels. |
| **PE / PP resin spike** | STALE (Asia PP) | NOMINAL (`> 40% spike`) | DOW NOMINAL (+1.37%) | Same data-quality pattern as EU gas storage. |
| **Jet fuel** | NOMINAL | NOMINAL × 2 (`> $1500/t`, `> 55% spike`) | JETS NOMINAL (+2.01%) | Agreement across all three surfaces. |
| **Malacca** | NOMINAL (Free Passage) | NOMINAL (`malacca severity`) | n/a | Agreement; both anchored by the FM Sugiono Apr 28 editorial. |
| **India rice policy** | NOMINAL (LIBERALIZED) | NOMINAL (`india rice ban`) | n/a | Agreement; both anchored by the DGFT 07/2026-27 editorial. |
| **AI storage / HDD** | (no dedicated tile rendered) | n/a | WDC WARNING (+7.20%), STX NOMINAL (+4.32%) | **Within-equity disagreement.** Two HDD makers, same sector, divergent one-day moves. No third surface to triangulate against. |

## Findings

### 1. Commodities with ≥2 disagreeing surfaces

- **Helium** — tile + threshold now aligned; equity (APD) disagrees.
- **CO2 byproduct** — tile + threshold aligned; equity (APD) disagrees.
- **Brent** — tile vs threshold (the breach is rule-derived from OECD, not threshold-tripped).
- **Urea** — tile vs lower threshold vs upper threshold vs equity.
- **Gold** — tile vs threshold (editorial technical-level anchoring vs price tripwire).
- **Silver** — tile vs threshold (same pattern as gold).
- **EU gas storage** — tile (STALE) vs threshold (NOMINAL).
- **PE / PP resin** — tile (STALE) vs threshold (NOMINAL).
- **AI storage** — WDC vs STX within the equity radar.

### 2. Which surface is the dashboard's own claimed leading indicator?

The dashboard names the **equity proxy radar** as its leading indicator
in the radar caption: *"smart money pricing in shortages before they
reach the public news cycle."* By the dashboard's own framing, when
equity disagrees with editorial, **equity is the upstream signal** and
editorial is the lagging news-cycle read.

For commodities where the threshold is mechanical (Brent > $115) and
the tile is editorial (anchored on a brief or a technical level), the
**threshold is the live mechanical truth** and the **tile is a
narrative overlay**. Disagreement here means the editorial framing has
moved ahead of the live tripwire — or behind it, if the tripwire fires
on a number the tile editorial hasn't caught up to.

### 3. Smart-money cross-check overlay candidates

The candidates for the queued `grs_compute()` smart-money cross-check
overlay (where equity NOMINAL and editorial CRITICAL / WARNING) are:

- **Helium** — tile + threshold WARNING; APD NOMINAL (+1.39%). Editorial
  framing already concedes this in its body text: *"APD ticker NOMINAL
  — leading signal, watch for inflection."* The cross-check would
  formalise that concession in the GRS Buffers cluster math, raising
  the helium contribution when APD is nominal and dropping it when APD
  breaches.
- **CO2 byproduct** — tile + threshold BREACH; APD NOMINAL (+1.39%).
  Same equity proxy as helium (APD covers all industrial-gas exposure).
  Same overlay logic would apply: BREACH framing in the absence of
  smart-money confirmation should not pull the GRS Buffers cluster to
  zero on its own.

The non-candidates:

- **Brent / OECD** disagreement is structural (rule-derived breach vs
  mechanical threshold) and isn't an equity-vs-editorial issue.
- **Urea** has CF NOMINAL but the tile WARNING already reflects the
  middle-tier reading correctly — no smart-money inversion here.
- **Gold / Silver** have no equity proxy mapped; cross-check not
  applicable.
- **EU gas storage / resin STALE** are data-quality issues, not
  smart-money disagreements.

### 4. Surfaces that are "agreement-shaped" but lying about it

Three cases where the surfaces *appear* to agree but the underlying
signal is unreliable:

- **Panama Neopanamax** — tile and threshold both NOMINAL, but the tile
  value is the EDITORIAL_FACTS Panama fallback ($385K) firing because
  ACP didn't publish a live read this session. Both surfaces are
  reading the same fallback, not a live agreement.
- **EU gas storage** and **PE / PP resin spike** — STALE tiles with
  NOMINAL thresholds. The threshold is not "agreeing"; it's defaulting
  to NOMINAL in the absence of live data. A breach engine that treats
  None as NOMINAL silently misclassifies data outages as good news.

These aren't smart-money overlay candidates — they're data-pipeline
items, separate from the GRS overlay design.
