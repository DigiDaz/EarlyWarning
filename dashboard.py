import html
import json
import re
from datetime import date, datetime

import requests
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Global Supply Chain Contagion HUD",
    page_icon="\U0001F6E1",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    .stApp {
        background-color: #0a0e14;
        color: #d1d5db;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    section[data-testid="stSidebar"] {
        background-color: #070a0f;
        border-right: 1px solid #1f2937;
    }
    section[data-testid="stSidebar"] * {
        font-family: 'Courier New', monospace;
    }
    h1, h2, h3, h4 {
        color: #e5e7eb;
        font-family: 'Courier New', monospace;
        letter-spacing: 1px;
    }
    .hud-title {
        color: #00ffd1;
        font-family: 'Courier New', monospace;
        text-transform: uppercase;
        letter-spacing: 4px;
        border-bottom: 1px solid #1f2937;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }
    .panel {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }
    /* Unified responsive card grid — used for both Commodity Telemetry
       and Logistics & Inputs Intel. auto-fit + minmax means cards keep
       a 240px floor and wrap to a new row on smaller screens instead of
       squishing. Every card uses the same .intel-card class so heights
       and widths match exactly across the whole dashboard. */
    .intel-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .intel-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        /* Bumped from 140 to 160 so equity cards comfortably fit the
           new "why it matters" context footer without other sections
           visually disagreeing on row height. */
        min-height: 160px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        box-sizing: border-box;
    }
    .intel-card-label {
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.7rem;
        line-height: 1.3;
        overflow: hidden;
        /* Allow up to 2 lines so longer descriptive labels like
           "FERTILIZER & FOOD SECURITY (CF)" don't get clipped at
           240px column width. */
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        text-overflow: ellipsis;
        margin-bottom: 0.5rem;
    }
    .intel-card-value {
        color: #e5e7eb;
        font-size: 1.5rem;
        line-height: 1.2;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        margin-bottom: 0.4rem;
    }
    .intel-card-unavail {
        color: #6b7280 !important;
        font-size: 1rem !important;
        letter-spacing: 1px;
    }
    .intel-card-delta {
        font-size: 0.78rem;
        color: #9ca3af;
        margin-top: auto;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        line-height: 1.4;
    }
    /* Pill treatment kicks in only when a directional class is present.
       Bare .intel-card-delta (e.g., empty/baseline rows) stays plain. */
    .intel-card-delta.delta-bear,
    .intel-card-delta.delta-bull {
        align-self: flex-start;
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        border: 1px solid transparent;
        max-width: 100%;
        box-sizing: border-box;
    }
    .intel-card-detail {
        font-size: 0.75rem;
        color: #9ca3af;
        line-height: 1.35;
        margin-top: auto;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
        max-height: 4.05em;
    }
    .delta-bear {
        background: rgba(239, 68, 68, 0.15);
        border-color: rgba(239, 68, 68, 0.40) !important;
        color: #ef4444;
    }
    .delta-bull {
        background: rgba(34, 197, 94, 0.15);
        border-color: rgba(34, 197, 94, 0.40) !important;
        color: #22c55e;
    }
    .delta-flat { color: #9ca3af; }
    /* High-Alert: any card whose underlying metric is currently in a
       BREACHED / WARNING / CRITICAL state in the Threshold Monitor.
       Red border + soft red glow makes it impossible to miss. */
    .intel-card-breached {
        border-color: rgba(255, 50, 50, 0.80) !important;
        box-shadow: 0 0 12px rgba(255, 50, 50, 0.25),
                    inset 0 0 1px rgba(255, 50, 50, 0.40);
    }
    /* Equity Proxy Radar: small explainer paragraph rendered between
       the section header and the card grid. Flat block, low-key. */
    .radar-explainer {
        background-color: #0d1218;
        border-left: 2px solid #1f2937;
        color: #9ca3af;
        font-family: 'Courier New', monospace;
        font-size: 0.78rem;
        line-height: 1.55;
        padding: 0.65rem 0.9rem;
        margin-bottom: 1rem;
        letter-spacing: 0.3px;
    }
    /* "Why it matters" footer line on each equity card. Shows below
       the delta pill, separated by a faint divider. Stays small and
       subtle so it doesn't compete with price + tier readout. */
    .intel-card-context {
        font-size: 0.7rem;
        color: #6b7280;
        font-style: italic;
        line-height: 1.35;
        letter-spacing: 0.2px;
        margin-top: 0.6rem;
        padding-top: 0.5rem;
        border-top: 1px solid rgba(255, 255, 255, 0.04);
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        text-overflow: ellipsis;
    }
    /* Strategic Outlook narrative card. The accent color is injected
       per-render via inline styles on border-left, title, prob badge,
       bullet markers, and a soft diagonal background wash. */
    .scenario-narrative {
        border: 1px solid #1f2937;
        border-left-width: 4px;
        border-radius: 6px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        font-family: 'Courier New', monospace;
        position: relative;
        overflow: hidden;
    }
    .scenario-narrative-header {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .scenario-narrative-tag {
        font-size: 0.7rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 3px;
    }
    .scenario-narrative-title {
        font-size: 1.5rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 600;
    }
    .scenario-narrative-prob {
        margin-left: auto;
        font-size: 0.85rem;
        padding: 4px 12px;
        border-radius: 4px;
        border: 1px solid;
        letter-spacing: 1px;
    }
    .scenario-narrative-bullets {
        list-style: none;
        padding-left: 0;
        margin: 0;
    }
    .scenario-narrative-bullets li {
        padding: 8px 0 8px 28px;
        position: relative;
        color: #d1d5db;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .scenario-narrative-bullets li + li {
        border-top: 1px solid rgba(255,255,255,0.04);
    }
    .scenario-narrative-bullets li::before {
        content: "▸";
        position: absolute;
        left: 4px;
        top: 8px;
        font-weight: bold;
        font-size: 1rem;
        color: var(--accent, #9ca3af);
    }
    /* Subtle indicator shown when a card or threshold row is sitting on
       the hardcoded peace-time baseline because Perplexity returned
       0/null/missing. The number renders normally; the tag tells the
       user they are looking at the baseline, not a live read. */
    .baseline-tag {
        font-size: 0.65rem;
        color: #6b7280;
        font-style: italic;
        letter-spacing: 0.5px;
        margin-left: 6px;
        text-transform: lowercase;
        white-space: nowrap;
    }
    .intel-card-baseline-note {
        font-size: 0.78rem;
        color: #6b7280;
        font-style: italic;
        margin-top: auto;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        letter-spacing: 0.5px;
    }
    .prob-bar-container {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 4px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }
    .prob-label {
        font-family: 'Courier New', monospace;
        color: #9ca3af;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        display: flex;
        justify-content: space-between;
    }
    .prob-bar {
        height: 8px;
        border-radius: 2px;
        margin-top: 6px;
        background-color: #1f2937;
        overflow: hidden;
    }
    .prob-fill {
        height: 100%;
        transition: width 0.4s ease;
    }
    .status-strip {
        background-color: #111827;
        border-left: 3px solid #00ffd1;
        padding: 0.5rem 1rem;
        margin-bottom: 1.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #9ca3af;
    }
    .alert-critical {
        background-color: rgba(220, 38, 38, 0.12);
        border-left: 3px solid #dc2626;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        font-family: 'Courier New', monospace;
        color: #fca5a5;
    }
    .alert-warn {
        background-color: rgba(234, 179, 8, 0.12);
        border-left: 3px solid #eab308;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        font-family: 'Courier New', monospace;
        color: #fde68a;
    }
    .alert-ok {
        background-color: rgba(16, 185, 129, 0.10);
        border-left: 3px solid #10b981;
        padding: 0.75rem 1rem;
        font-family: 'Courier New', monospace;
        color: #6ee7b7;
    }
    .intel-tag {
        display: inline-block;
        font-family: 'Courier New', monospace;
        font-size: 0.65rem;
        letter-spacing: 1px;
        color: #0a0e14;
        background-color: #00ffd1;
        padding: 1px 6px;
        border-radius: 2px;
        margin-left: 6px;
        vertical-align: middle;
    }
    /* v12.1 — HDD Stockout Countdown panel. Lives inside the AI Storage
       block in column 1. The numeric day count is the dominant element;
       the contextual alert below explains the structural lockout. */
    .hdd-countdown {
        background: linear-gradient(135deg, rgba(220,38,38,0.08) 0%,
                    rgba(17,24,39,0.0) 70%), #111827;
        border: 1px solid #1f2937;
        border-left: 4px solid #dc2626;
        border-radius: 6px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1rem;
        font-family: 'Courier New', monospace;
    }
    .hdd-countdown-label {
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-size: 0.72rem;
        margin-bottom: 0.55rem;
    }
    .hdd-countdown-value {
        color: #fca5a5;
        font-size: 2.1rem;
        font-weight: 600;
        line-height: 1.1;
        letter-spacing: 1px;
    }
    .hdd-countdown-value .hdd-unit {
        font-size: 1rem;
        color: #9ca3af;
        margin-left: 0.4rem;
        letter-spacing: 2px;
    }
    .hdd-countdown-target {
        color: #6b7280;
        font-size: 0.72rem;
        margin-top: 0.35rem;
        letter-spacing: 0.5px;
    }
    .hdd-countdown-alert {
        margin-top: 0.85rem;
        padding-top: 0.75rem;
        border-top: 1px solid rgba(255,255,255,0.06);
        color: #fde68a;
        font-size: 0.78rem;
        line-height: 1.5;
        font-style: italic;
    }
    /* v12.1 — Systemic Cascade flow diagram. Renders the
       Energy → Ammonia → CO2 → Meat/Medical chain as styled boxes
       connected by arrows. Downstream nodes flip RED when EU ammonia
       capacity < 40%. */
    .cascade-container {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
        font-family: 'Courier New', monospace;
    }
    .cascade-flow {
        display: flex;
        flex-wrap: wrap;
        align-items: stretch;
        gap: 0.5rem;
        margin-top: 0.6rem;
    }
    .cascade-node {
        flex: 1 1 0;
        min-width: 0;
        background-color: #0d1218;
        border: 1px solid #1f2937;
        border-left: 3px solid #6b7280;
        border-radius: 4px;
        padding: 0.6rem 0.7rem;
        color: #d1d5db;
        font-size: 0.72rem;
        line-height: 1.3;
    }
    .cascade-node-title {
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.62rem;
        margin-bottom: 0.25rem;
    }
    .cascade-node.cascade-source {
        border-left-color: #3b82f6;
    }
    .cascade-node.cascade-mid {
        border-left-color: #eab308;
    }
    .cascade-node.cascade-mid.cascade-red,
    .cascade-node.cascade-sink.cascade-red {
        border-left-color: #dc2626;
        background-color: rgba(220,38,38,0.10);
        color: #fca5a5;
        box-shadow: 0 0 8px rgba(220,38,38,0.15);
    }
    .cascade-node.cascade-mid.cascade-red .cascade-node-title,
    .cascade-node.cascade-sink.cascade-red .cascade-node-title {
        color: #fca5a5;
    }
    .cascade-arrow {
        align-self: center;
        color: #4b5563;
        font-size: 1.1rem;
        padding: 0 0.15rem;
    }
    .cascade-trigger-note {
        margin-top: 0.85rem;
        padding-top: 0.75rem;
        border-top: 1px solid rgba(255,255,255,0.06);
        font-size: 0.74rem;
        color: #9ca3af;
        line-height: 1.5;
    }
    .cascade-trigger-note.cascade-active {
        color: #fca5a5;
    }
    /* v12.1 — Threshold Monitor row using <details>/<summary> so the
       Intelligence Insight expander stays inline with the row card.
       Clicking the row toggles the explanatory paragraph. */
    .threshold-row {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 4px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
    }
    .threshold-row.threshold-breached {
        border-left: 3px solid #dc2626;
    }
    .threshold-row.threshold-warning {
        border-left: 3px solid #eab308;
    }
    .threshold-row[open] {
        background-color: #0d1218;
    }
    .threshold-summary {
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
        list-style: none;
        gap: 0.5rem;
    }
    .threshold-summary::-webkit-details-marker { display: none; }
    .threshold-summary::marker { content: ""; }
    .threshold-summary .t-name { color: #9ca3af; flex: 1; }
    .threshold-summary .t-live { color: #9ca3af; }
    .threshold-summary .t-status { white-space: nowrap; }
    .threshold-insight {
        margin-top: 0.6rem;
        padding: 0.7rem 0.85rem;
        background-color: rgba(220,38,38,0.06);
        border-left: 2px solid #dc2626;
        border-radius: 3px;
        color: #fde68a;
        font-size: 0.76rem;
        line-height: 1.55;
        font-style: italic;
    }
    .threshold-insight.insight-warn {
        background-color: rgba(234,179,8,0.06);
        border-left-color: #eab308;
    }
    .threshold-insight strong {
        color: #fca5a5;
        font-style: normal;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.68rem;
        display: block;
        margin-bottom: 0.3rem;
    }
    .threshold-insight.insight-warn strong { color: #fde68a; }
    /* v12.1 — Section sub-titles inside each of the 3 columns. Slightly
       smaller than the main hud-title to keep the column hierarchy
       clean. */
    .col-section-title {
        color: #00ffd1;
        font-family: 'Courier New', monospace;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-size: 0.85rem;
        border-bottom: 1px solid #1f2937;
        padding-bottom: 0.4rem;
        margin: 0.4rem 0 0.85rem 0;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

BASELINE = {
    "Brent": 100.0,
    "TTF": 52.0,
    "Gold": 2300.0,
    "Silver": 28.0,
}

TICKERS = {
    "Brent": "BZ=F",
    "TTF": "TTF=F",
    "Gold": "GC=F",
    "Silver": "SI=F",
}

# Equity Proxy Radar — equities whose daily move serves as a real-time
# proxy for the corresponding intel input. A large absolute spike on
# any of these is taken as an early-warning signal even if the
# underlying physical-market data has not been updated yet.
EQUITY_TICKERS = {
    "CF":   "CF",     # CF Industries Holdings (fertilizer / ammonia)
    "DOW":  "DOW",    # Dow Inc. (commodity petrochemicals / PE-PP)
    "APD":  "APD",    # Air Products & Chemicals (industrial gases)
    "JETS": "JETS",   # U.S. Global Jets ETF (airlines / jet fuel)
    "WDC":  "WDC",    # Western Digital (AI storage / HDD bottleneck)
    "STX":  "STX",    # Seagate Technology (AI storage / HDD bottleneck)
}

EQUITY_PROXY_META = {
    "CF":   {"name": "FERTILIZER & FOOD SECURITY (CF)",
             "proxy_for": "urea / fertilizer",
             "audit": "fertilizer and urea supply chain — food-cost "
                      "pass-through window opening",
             "why_it_matters":
                 "Leading indicator for Spring 2027 food harvest yields."},
    "DOW":  {"name": "RESINS & MEDICAL PLASTICS (DOW)",
             "proxy_for": "PE/PP resins",
             "audit": "petrochemical and base-resin supply chain — "
                      "packaging and medical device exposure",
             "why_it_matters":
                 "Tracks PE/PP feedstock availability for sterile "
                 "medical supplies."},
    "APD":  {"name": "AI HARDWARE & HELIUM (APD)",
             "proxy_for": "helium / industrial gas",
             "audit": "helium supply chain — semiconductor, MRI and "
                      "cryogenic exposure",
             "why_it_matters":
                 "Critical proxy for semiconductor yields and MRI "
                 "coolant stocks."},
    "JETS": {"name": "AIR-FREIGHT & JET FUEL (JETS)",
             "proxy_for": "aviation / jet fuel",
             "audit": "aviation and jet-fuel exposure — air-freight cost "
                      "and travel-budget pressure",
             "why_it_matters":
                 "Signals cargo payload displacement and aviation fuel "
                 "rationing."},
    "WDC":  {"name": "AI STORAGE / HDD BOTTLENECK (WDC)",
             "proxy_for": "AI storage / HDD",
             "audit": "AI storage and helium-sealed HDD supply — "
                      "hyperscaler buildout pipeline",
             "why_it_matters":
                 "95% of 2026 output locked to hyperscalers; "
                 "hardware freeze for broader market."},
    "STX":  {"name": "AI STORAGE / HDD BOTTLENECK (STX)",
             "proxy_for": "AI storage / HDD",
             "audit": "AI storage and helium-sealed HDD supply — "
                      "hyperscaler buildout pipeline",
             "why_it_matters":
                 "Strict allocation for 2026 builds; physically "
                 "constrained by helium-sealed drive shortage."},
}

# v11 Intelligence Brief — physical-logic gates layered on top of the
# Perplexity / yfinance feeds.
QATAR_HELIUM_FORCE_MAJEURE_DATE = date(2026, 3, 2)
HELIUM_BOIL_OFF_DAYS = 48              # liquid helium boil-off threshold
OECD_INVENTORY_OPERATIONAL_MIN_MB = 842
OECD_INVENTORY_BREACH = True           # v11 confirmed below operational minimum
JET_FUEL_SPIKE_THRESHOLD_PCT = 55      # "Payload Displacement Warning" gate

# Industrial CO2 byproduct: European ammonia plants closed → food-grade
# CO2 byproduct exhausted. Threshold is 40% capacity utilisation; v11
# brief confirms current capacity is well below.
EUROPEAN_AMMONIA_CAPACITY_PCT = 35.0
EUROPEAN_AMMONIA_THRESHOLD_PCT = 40.0
CO2_BYPRODUCT_BREACH = (
    EUROPEAN_AMMONIA_CAPACITY_PCT < EUROPEAN_AMMONIA_THRESHOLD_PCT
)

# v12.1 Structural Break — predictive intelligence layer.
#
# HDD Stockout Countdown: 95% of WDC/STX 2026 enterprise HDD output is
# locked to hyperscaler contracts. Standard enterprise channels enter a
# physical hardware freeze running through the end of 2026. Countdown
# is days remaining from "today" (currently April 30 2026) to Dec 31.
HDD_STOCKOUT_TARGET_DATE = date(2026, 12, 31)

# Malacca Shadow Indicator — congestion_delta is "ships waiting" beyond
# the peace-time daily transit baseline. >15% above baseline triggers
# CONGESTION SHADOW. The brief: 48-72h lead time before total global
# manufacturing collapse fires as the Tail Risk trigger.
MALACCA_BASELINE_SHIPS = 80
MALACCA_SHADOW_THRESHOLD_PCT = 15.0

# v12.1 — Intelligence Insight copy for breached/critical Threshold
# Monitor rows. Each row maps a stable key to the explanatory text that
# unfolds when the user expands the row. Phrasing is sourced from the
# v11/v12.1 intelligence brief — second-order consequences and tail
# linkages, not just the breach itself.
INTELLIGENCE_INSIGHTS = {
    "brent": (
        "Sustained Brent above $115-130 forces transport-cost "
        "pass-through into food, freight, and household energy "
        "budgets within 6-8 weeks. Combined with the OECD inventory "
        "breach, price is now the rationing mechanism — not supply."
    ),
    "ttf": (
        "European industrial gas above EUR 65-80/MWh suppresses "
        "ammonia, glass, and ceramic output and accelerates fertilizer "
        "shutdowns. Cascades directly into food-grade CO2, urea, and "
        "the Spring 2027 harvest input window."
    ),
    "gold": (
        "Gold above $4600 confirms safe-haven flight and monetary-regime "
        "stress. Pressure-test cash reserves and FX-hedge ratios; "
        "USD-denominated receivables are exposed to a regime-shift "
        "repricing window."
    ),
    "silver": (
        "Silver above $75 reflects industrial-precious correlation "
        "breakdown. Solar and electronics BOMs face direct cost pressure; "
        "lock 90-day futures for any silver-linked capex pipeline."
    ),
    "urea": (
        "Urea spot above $600-800/t propagates through grain, dairy, "
        "and meat shelf prices in 2-3 quarters. Spring 2027 harvest "
        "yields will reflect input-cost rationing today — leading "
        "indicator for the food-cost pass-through window."
    ),
    "hormuz": (
        "Hormuz transit below 30/day cuts global crude/LNG flow by "
        "20%+. Activate Cape and pipeline routing assumptions; expect "
        "pump-price shocks within 3-6 weeks and war-risk insurance "
        "premia to spike materially within 48h."
    ),
    "panama": (
        "Panama Neopanamax slots above $2.5-4.0M force Asia-USEC "
        "freight onto Suez or USWC+rail. Holiday-season consumer "
        "goods carry 6-10% shipping cost pass-through; FAK rate spike "
        "follows by 30-45 days."
    ),
    "helium": (
        "Reserves are physically exhausted. Expect semiconductor fab "
        "yield degradation and high-end electronics launch delays. "
        "MRI cryogenic refills are at risk; diagnostic-imaging service "
        "windows will lengthen across hospital networks."
    ),
    "co2": (
        "This signifies more than just gas loss; it is a shelf-life "
        "crisis for fresh meat/poultry and a superconducting hazard "
        "for MRI magnets. Beverage carbonation, dry-ice cold chain, "
        "and elective-procedure medical gas all degrade in parallel."
    ),
    "resin": (
        "PE/PP resin above 40% spike degrades medical device, sterile "
        "packaging, and consumer goods BOMs. Pull forward 60-day POs; "
        "qualified alternate-grade suppliers are the only viable hedge "
        "before retail COGS pass-through."
    ),
    "jet": (
        "Jet fuel above $1,500/t triggers payload displacement: "
        "airlines trade revenue weight for fuel weight. Air-freight "
        "rates spike 30-50%; shift time-tolerant cargo to ocean and "
        "lock seasonal travel before airfare repricing completes."
    ),
    "rice": (
        "Sovereign food-policy shock: rice shelf prices climb 20-50% "
        "within weeks across import-dependent markets. Expect "
        "second-order moves in wheat, noodles, and animal feed; Asian "
        "and MENA geographies are most exposed."
    ),
    "malacca_critical": (
        "A critical Malacca event collapses the probability matrix to "
        "Tail Risk MAX. Force majeure exposure, war-risk premia, and "
        "60-90 day inventory pre-positioning for any China-EU or "
        "Gulf-Asia lane SKU all activate simultaneously."
    ),
    "malacca_shadow": (
        "Malacca congestion provides 48-72 hours of lead time before "
        "total global manufacturing collapse (Tail Risk Trigger). "
        "Ships-waiting >15% above the 80/day baseline is the leading "
        "indicator — pre-position contingency routing now."
    ),
    "oecd": (
        "OECD commercial inventories below the 842 MB operational "
        "minimum mean physical buffer is gone. Brent is forced "
        "CRITICAL irrespective of spot — assume sustained $130+ and "
        "stress-test transport-heavy COGS at +50%."
    ),
    "jet_displacement": (
        "Payload Displacement Warning: aviation arithmetic breaking. "
        "Cargo and passenger capacity contract simultaneously as fuel "
        "weight crowds out revenue weight. Re-quote air-freight; "
        "expect 30-50% rate spike within the lead-time window."
    ),
    "helium_boiloff": (
        "Past the 48-day liquid-helium boil-off threshold from the "
        "Qatar force majeure. Fab and MRI stockpiles are physically "
        "depleted — this is a shelf-life event, not a price event. "
        "Activate alternate-source contracts now."
    ),
    "equity_critical": (
        "An equity-proxy spike of >=12% on a single session is the "
        "market pricing in physical stress before the underlying feed "
        "updates. Treat as a 24-72h leading indicator for the linked "
        "supply chain; brief procurement, finance, and legal."
    ),
}

# Severity tiers for absolute daily % move on the proxy. Symmetric so
# a large drop (e.g., JETS down 14%) flags the same way as a large
# rise on a fertilizer name (e.g., CF up 14%).
EQUITY_THRESHOLDS = {
    "warning":  5.0,
    "critical": 12.0,
}

# Pre-crisis "peace-time" baselines. These are used for two things:
# (1) delta math when live data is present, and (2) display fallback when
# Perplexity returns 0/null/missing. A fallback NEVER feeds the
# probability engine — adjust_probabilities() / evaluate_playbook()
# continue to receive None upstream so the math is unchanged.
INTEL_BASELINE = {
    "panama_canal_neopanamax_price": 1_500_000.0,
    "urea_spot_price_ton": 320.0,
    "hormuz_daily_transit_count": 80.0,
    "helium_spot_price_mcf": 400.0,
    "asian_pe_pp_resin_spike": 0.0,
    "jet_fuel_price_ton": 850.0,
}

# Qualitative peace-time defaults (no numeric baseline applies).
MALACCA_BASELINE_SEVERITY = "nominal"
MALACCA_BASELINE_STATUS = (
    "Peace-time baseline — no active maritime disruption flagged."
)
RICE_BAN_BASELINE = "INACTIVE"

# BASE_PROBS reset for the post-April-29 extended-blockade scenario.
# US rejected the April 27th Iranian offer in favor of an extended
# Hormuz blockade — Best Case is no longer viable, weight collapses
# into Base Case + Tail Risk. Engine adjustments (equity tiers,
# Malacca override, helium exhaustion, etc.) still apply on top.
BASE_PROBS = {
    "Best Case": 0.0,
    "Slow Normalization": 0.0,
    "Base Case": 60.0,
    "Tail Risk": 40.0,
}

PROB_COLORS = {
    "Best Case": "#10b981",
    "Slow Normalization": "#3b82f6",
    "Base Case": "#eab308",
    "Tail Risk": "#dc2626",
}

# Display names — used for the Strategic Outlook card title and the
# Probability Matrix bars. Internal dict keys are kept short for the
# engine; the user-facing labels can carry the structural framing.
SCENARIO_DISPLAY_NAMES = {
    "Best Case": "Best Case",
    "Slow Normalization": "Slow Normalization",
    "Base Case": "Base Case: Structural Shift",
    "Tail Risk": "Tail Risk",
}

# Strategic Outlook bullets for each scenario. The card under the
# Probability Matrix renders the narrative for whichever scenario
# currently has the highest probability. Color theming is reused from
# PROB_COLORS so the outlook card matches its bar in the matrix.
# Narrative content sourced from the v11 Intelligence Brief (Slide 36).
# Dict keys must stay as the existing scenario IDs ("Slow Normalization"
# in American spelling) because they're shared with BASE_PROBS,
# PROB_COLORS, and the adjust_probabilities engine; the bullets
# themselves are reproduced verbatim from the v11 brief.
SCENARIO_NARRATIVES = {
    "Best Case": [
        "Hormuz reopens by Q3 2026; Phased ceasefire.",
        "Brent retraces to $75–85.",
        "EU LNG storage refills by Oct 2026.",
        "Asian manufacturing recovers within Q4.",
        "Helium normalises 6-9 months post-flow.",
    ],
    "Slow Normalization": [
        "Partial Hormuz reopening end-2026; Iran retains harassment "
        "capability.",
        "Brent $90–105 sustained.",
        "Asian factories at 70-80% throughout 2026.",
        "Helium rationing through 2027; Sticky 5% inflation.",
    ],
    "Base Case": [
        "Hormuz contested through 2027.",
        "Ras Laffan offline 3+ years.",
        "Major HBM/GPU launch slips.",
        "Global food-export bans cascade.",
    ],
    "Tail Risk": [
        "Cascading breakdown (Malacca/subsea cable attacks); Asian "
        "manufacturing collapse.",
        "Brent $130–160+; Multiple state energy emergencies.",
        "Hospital supply rationing; Recession in EU and US.",
        "AI capex pushed to 2028; Sub-Saharan food crisis.",
    ],
}

SEVERITY_COLORS = {
    "nominal": "#10b981",
    "elevated": "#eab308",
    "critical": "#dc2626",
}

PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"

PERPLEXITY_SYSTEM_PROMPT = (
    "You are a commodities and logistics intelligence analyst. "
    "You return ONLY a single raw JSON dictionary. "
    "Do not include markdown fences (no ```json, no ```), no commentary, "
    "no preface, no trailing text, no citations. "
    "Output exactly one JSON object on a single line, nothing else. "
    "Numeric values must be plain numbers (no currency symbols, no commas, "
    "no units, no quotes). "
    "If you cannot find exact live data for a numeric field, provide the "
    "most recently available closing price or count from the last 7 days. "
    "DO NOT OUTPUT 0. Never use 0 or a negative number as a placeholder; "
    "if a real number truly cannot be sourced, omit that key entirely. "
    "Required keys: "
    "panama_canal_neopanamax_price (USD, number), "
    "urea_spot_price_ton (USD per metric ton, number), "
    "hormuz_daily_transit_count (integer ships per day), "
    "malacca_status (short factual string, max 140 chars, summarizing "
    "current Strait of Malacca congestion / vessel backlog / breaking "
    "maritime incidents), "
    "malacca_severity (string, EXACTLY one of: \"nominal\", \"elevated\", "
    "\"critical\"; use \"critical\" only for active blockade, closure, "
    "collision-induced channel obstruction, or major security incident "
    "actively disrupting transit), "
    "malacca_ships_waiting (integer, number of ships currently "
    "queued/waiting at the Strait of Malacca anchorage or backlog; "
    "peace-time baseline is approximately 80; if a precise number "
    "cannot be sourced, return your best estimate from the most recent "
    "7 days of maritime traffic reporting and DO NOT return 0), "
    "helium_spot_price_mcf (USD per Mcf, number), "
    "asian_pe_pp_resin_spike (percentage as plain number, e.g. 25 means "
    "25% — current estimated price spike / percentage increase for Asian "
    "PE/PP base resins versus a stable baseline; if there is genuinely no "
    "spike, return a small positive number rather than 0), "
    "jet_fuel_price_ton (USD per metric ton, number, current global "
    "average jet fuel price), "
    "india_rice_ban_status (string, EXACTLY \"ACTIVE\" or \"INACTIVE\"; "
    "ACTIVE means an Indian government export ban on any rice category — "
    "non-basmati white, broken, or parboiled — is currently in force)."
)

PERPLEXITY_USER_PROMPT = (
    "Find the latest April 2026 data for: "
    "1. Panama Canal average auction price for Neopanamax slots. "
    "2. Global Urea spot price per ton. "
    "3. Current Strait of Hormuz daily ship transit counts. "
    "4. Current Strait of Malacca maritime congestion status, vessel "
    "backlog delays, or breaking maritime incidents. "
    "4b. Current number of ships waiting/queued at the Strait of "
    "Malacca anchorage (peace-time baseline ~80). "
    "5. Current global spot price for Helium per Mcf. "
    "6. Current estimated price spike / percentage increase for Asian "
    "PE/PP base resins. "
    "7. Current global average jet fuel price per ton. "
    "8. Whether an Indian rice export ban is currently in place "
    "(output exactly \"ACTIVE\" or \"INACTIVE\"). "
    "If you cannot find the exact live data for today, provide the most "
    "recently available closing price or count from the last 7 days. "
    "Do not output 0. "
    "Return a single raw JSON object with exactly these keys: "
    "panama_canal_neopanamax_price, urea_spot_price_ton, "
    "hormuz_daily_transit_count, malacca_status, malacca_severity, "
    "malacca_ships_waiting, helium_spot_price_mcf, "
    "asian_pe_pp_resin_spike, jet_fuel_price_ton, "
    "india_rice_ban_status. "
    "Numeric values only for the numeric keys. No markdown, no prose."
)


@st.cache_data(ttl=14400)
def fetch_price(ticker: str) -> float | None:
    """
    Pull raw close price directly from yfinance. No multipliers, no
    transforms, no synthetic data — whatever Yahoo returns is what
    the dashboard displays.

    Cached for 4h (14400s) so the dashboard refreshes in step with
    major market sessions (Asia → Europe → US) instead of locking
    everyone to a single daily snapshot.
    """
    try:
        data = yf.Ticker(ticker).history(period="2d", interval="1d")
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception:
        return None


@st.cache_data(ttl=14400)
def fetch_equity_snapshot(ticker: str) -> dict:
    """Return {"price": last close, "pct_change": daily % vs prior close}.
    Either field can be None if the data is unavailable. period=5d
    guarantees we get at least two trading-day closes even after a
    long weekend or holiday. Cached 4h alongside fetch_price so the
    Equity Proxy Radar refreshes with each major market session."""
    out = {"price": None, "pct_change": None}
    try:
        data = yf.Ticker(ticker).history(period="5d", interval="1d")
        if data.empty:
            return out
        out["price"] = float(data["Close"].iloc[-1])
        if len(data) < 2:
            return out
        prior = float(data["Close"].iloc[-2])
        if prior == 0:
            return out
        out["pct_change"] = ((out["price"] - prior) / prior) * 100.0
    except Exception:
        return out
    return out


def equity_severity(pct_change):
    """Tier on absolute daily move:
        |chg| >= 12% → 'critical'
        |chg| >=  5% → 'warning'
        otherwise    → 'nominal'
    Returns None if pct_change is None."""
    if pct_change is None:
        return None
    abs_change = abs(pct_change)
    if abs_change >= EQUITY_THRESHOLDS["critical"]:
        return "critical"
    if abs_change >= EQUITY_THRESHOLDS["warning"]:
        return "warning"
    return "nominal"


def helium_days_elapsed():
    """Calendar days since the March 2, 2026 Qatar helium force majeure."""
    return (date.today() - QATAR_HELIUM_FORCE_MAJEURE_DATE).days


def helium_exhausted():
    """True once elapsed days meet/exceed the 48-day liquid-helium
    boil-off threshold. v11 brief: at >= 48 days, fab and MRI
    stockpiles drained — semiconductor yield collapse is imminent."""
    return helium_days_elapsed() >= HELIUM_BOIL_OFF_DAYS


def jet_spike_pct(jet_value):
    """Jet fuel price as % above the peace-time baseline. None-safe."""
    if jet_value is None:
        return None
    base = INTEL_BASELINE["jet_fuel_price_ton"]
    if not base:
        return None
    return (jet_value - base) / base * 100.0


def hdd_stockout_days_remaining():
    """Calendar days from today to the December 31, 2026 HDD stockout
    target — the structural enterprise-channel hardware freeze window.
    Clamped to >= 0 so the countdown reads zero on/after the target
    rather than going negative."""
    delta = (HDD_STOCKOUT_TARGET_DATE - date.today()).days
    return max(delta, 0)


def malacca_congestion_delta_pct(intel):
    """Compute % above the 80-ship/day baseline for the Malacca queue.
    Returns None if Perplexity did not return a usable ships_waiting
    value (the engine should not assert a shadow without live data)."""
    if not intel:
        return None
    ships = intel.get("malacca_ships_waiting")
    if ships is None:
        return None
    if not MALACCA_BASELINE_SHIPS:
        return None
    return (ships - MALACCA_BASELINE_SHIPS) / MALACCA_BASELINE_SHIPS * 100.0


def malacca_shadow_active(intel):
    """True when the Malacca ships-waiting queue is more than 15% above
    the 80/day baseline. This is the v12.1 leading-indicator trigger:
    48-72h lead time before total global manufacturing collapse fires
    as the Tail Risk trigger."""
    pct = malacca_congestion_delta_pct(intel)
    if pct is None:
        return False
    return pct > MALACCA_SHADOW_THRESHOLD_PCT


def _coerce_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-]", "", value)
        if cleaned in ("", "-", ".", "-."):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _positive_or_none(value):
    """Treat 0 and negatives as 'data unavailable' — Perplexity sometimes
    returns 0 as a placeholder when it can't source a real number.
    Applied uniformly to every numeric intel field."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v


def _normalize_severity(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    if cleaned in ("nominal", "elevated", "critical"):
        return cleaned
    return None


def _normalize_status(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 240:
        cleaned = cleaned[:237] + "..."
    return cleaned


def _normalize_ban_status(value):
    """Rice ban must be exactly 'ACTIVE' or 'INACTIVE'. Anything else
    (None, empty, 'unknown', misspellings, prose) → None → DATA UNAVAILABLE."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip().upper()
    if cleaned in ("ACTIVE", "INACTIVE"):
        return cleaned
    return None


def _extract_json_object(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


@st.cache_data(ttl=14400, show_spinner=False)
def fetch_perplexity_intel(api_key: str) -> dict:
    result = {
        "data": None,
        "raw": None,
        "error": None,
        "fetched_at": None,
    }
    if not api_key:
        result["error"] = "No API key provided."
        return result

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": PERPLEXITY_SYSTEM_PROMPT},
            {"role": "user", "content": PERPLEXITY_USER_PROMPT},
        ],
        "temperature": 0.0,
    }

    try:
        response = requests.post(
            PERPLEXITY_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        result["error"] = f"Network error: {e}"
        return result

    if response.status_code != 200:
        result["error"] = (
            f"Perplexity API returned HTTP {response.status_code}: "
            f"{response.text[:200]}"
        )
        return result

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as e:
        result["error"] = f"Malformed Perplexity response: {e}"
        return result

    result["raw"] = content
    parsed = _extract_json_object(content)
    if parsed is None:
        result["error"] = "Could not parse JSON from Perplexity response."
        return result

    cleaned = {}
    numeric_keys = (
        "panama_canal_neopanamax_price",
        "urea_spot_price_ton",
        "hormuz_daily_transit_count",
        "malacca_ships_waiting",
        "helium_spot_price_mcf",
        "asian_pe_pp_resin_spike",
        "jet_fuel_price_ton",
    )
    for key in numeric_keys:
        cleaned[key] = _positive_or_none(_coerce_number(parsed.get(key)))

    cleaned["malacca_status"] = _normalize_status(parsed.get("malacca_status"))
    cleaned["malacca_severity"] = _normalize_severity(
        parsed.get("malacca_severity")
    )
    cleaned["india_rice_ban_status"] = _normalize_ban_status(
        parsed.get("india_rice_ban_status")
    )

    result["data"] = cleaned
    result["fetched_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return result


def adjust_probabilities(prices: dict, intel: dict | None = None,
                         equity_changes: dict | None = None) -> dict:
    intel = intel or {}
    equity_changes = equity_changes or {}

    # Hard override: a critical Malacca event collapses the matrix to
    # max Tail Risk. Skip every other adjustment.
    if intel.get("malacca_severity") == "critical":
        return {
            "Best Case": 0.0,
            "Slow Normalization": 0.0,
            "Base Case": 0.0,
            "Tail Risk": 100.0,
        }

    probs = dict(BASE_PROBS)

    brent = prices.get("Brent")
    ttf = prices.get("TTF")

    if brent is not None and brent > 130:
        probs["Tail Risk"] += 10
        probs["Base Case"] -= 10
    elif brent is not None and brent > 115:
        probs["Tail Risk"] += 5
        probs["Base Case"] -= 5
    elif brent is not None and brent < 90:
        probs["Best Case"] += 5
        probs["Tail Risk"] -= 5

    if ttf is not None and ttf > 80:
        probs["Tail Risk"] += 8
        probs["Slow Normalization"] -= 4
        probs["Base Case"] -= 4
    elif ttf is not None and ttf > 65:
        probs["Tail Risk"] += 4
        probs["Base Case"] -= 4

    urea = intel.get("urea_spot_price_ton")
    if urea is not None and urea > 800:
        probs["Tail Risk"] += 6
        probs["Base Case"] -= 4
        probs["Best Case"] -= 2
    elif urea is not None and urea > 600:
        probs["Tail Risk"] += 3
        probs["Base Case"] -= 3

    hormuz = intel.get("hormuz_daily_transit_count")
    if hormuz is not None and hormuz < 20:
        probs["Tail Risk"] += 12
        probs["Base Case"] -= 8
        probs["Best Case"] -= 4
    elif hormuz is not None and hormuz < 30:
        probs["Tail Risk"] += 5
        probs["Base Case"] += 3
        probs["Best Case"] -= 4
        probs["Slow Normalization"] -= 4

    panama = intel.get("panama_canal_neopanamax_price")
    if panama is not None and panama > 4_000_000:
        probs["Tail Risk"] += 5
        probs["Base Case"] -= 3
        probs["Best Case"] -= 2
    elif panama is not None and panama > 2_500_000:
        probs["Tail Risk"] += 2
        probs["Base Case"] -= 2

    if intel.get("malacca_severity") == "elevated":
        probs["Tail Risk"] += 8
        probs["Base Case"] -= 4
        probs["Slow Normalization"] -= 4

    # v12.1 Shadow Indicator — congestion >15% above baseline. Fires
    # even when Perplexity has not flagged severity, because the
    # ships-waiting queue is the 48-72h leading indicator.
    if (
        malacca_shadow_active(intel)
        and intel.get("malacca_severity") not in ("elevated", "critical")
    ):
        probs["Tail Risk"] += 6
        probs["Base Case"] += 2
        probs["Best Case"] -= 4
        probs["Slow Normalization"] -= 4

    # New tripwires (helium, resins, jet fuel, india rice ban).
    helium = intel.get("helium_spot_price_mcf")
    if helium is not None and helium > 2000:
        probs["Tail Risk"] += 4
        probs["Base Case"] += 4
        probs["Best Case"] -= 4
        probs["Slow Normalization"] -= 4

    resin = intel.get("asian_pe_pp_resin_spike")
    if resin is not None and resin > 40:
        probs["Base Case"] += 5
        probs["Best Case"] -= 3
        probs["Slow Normalization"] -= 2

    jet = intel.get("jet_fuel_price_ton")
    if jet is not None and jet > 1500:
        probs["Base Case"] += 4
        probs["Best Case"] -= 2
        probs["Slow Normalization"] -= 2

    if intel.get("india_rice_ban_status") == "ACTIVE":
        probs["Tail Risk"] += 18
        probs["Base Case"] -= 8
        probs["Best Case"] -= 5
        probs["Slow Normalization"] -= 5

    # v11 physical-logic gates — fire regardless of Perplexity intel
    # because the underlying conditions are confirmed by the brief.
    if helium_exhausted():
        probs["Tail Risk"] += 8
        probs["Base Case"] -= 4
        probs["Slow Normalization"] -= 4

    if OECD_INVENTORY_BREACH:
        probs["Tail Risk"] += 8
        probs["Base Case"] -= 4
        probs["Slow Normalization"] -= 4

    if CO2_BYPRODUCT_BREACH:
        probs["Tail Risk"] += 6
        probs["Base Case"] -= 3
        probs["Slow Normalization"] -= 3

    jet_pct = jet_spike_pct(intel.get("jet_fuel_price_ton"))
    if jet_pct is not None and jet_pct > JET_FUEL_SPIKE_THRESHOLD_PCT:
        probs["Base Case"] += 4
        probs["Best Case"] -= 2
        probs["Slow Normalization"] -= 2

    # Equity Proxy Radar: every WARNING tier nudges Base Case up
    # slightly (uncertainty rising); every CRITICAL tier pushes Tail
    # Risk meaningfully. Effects accumulate across the four proxies so
    # broad-based equity stress is scored more aggressively than a
    # single isolated mover.
    warning_count = 0
    critical_count = 0
    for ticker_key in EQUITY_TICKERS:
        sev = equity_severity(equity_changes.get(ticker_key))
        if sev == "warning":
            warning_count += 1
        elif sev == "critical":
            critical_count += 1

    if warning_count > 0:
        probs["Base Case"] += 2 * warning_count
        probs["Best Case"] -= 1 * warning_count
        probs["Slow Normalization"] -= 1 * warning_count

    if critical_count > 0:
        probs["Tail Risk"] += 8 * critical_count
        probs["Base Case"] -= 3 * critical_count
        probs["Best Case"] -= 3 * critical_count
        probs["Slow Normalization"] -= 2 * critical_count

    for k in probs:
        probs[k] = max(0.0, probs[k])
    total = sum(probs.values())
    if total > 0:
        for k in probs:
            probs[k] = round(probs[k] / total * 100, 1)
    return probs


def evaluate_playbook(prices: dict, intel: dict | None = None,
                      equity_changes: dict | None = None) -> list[dict]:
    actions = []
    intel = intel or {}
    equity_changes = equity_changes or {}
    brent = prices.get("Brent")
    ttf = prices.get("TTF")
    gold = prices.get("Gold")
    silver = prices.get("Silver")
    urea = intel.get("urea_spot_price_ton")
    hormuz = intel.get("hormuz_daily_transit_count")
    panama = intel.get("panama_canal_neopanamax_price")
    helium = intel.get("helium_spot_price_mcf")
    resin = intel.get("asian_pe_pp_resin_spike")
    jet = intel.get("jet_fuel_price_ton")
    malacca_sev = intel.get("malacca_severity")
    malacca_status = intel.get("malacca_status") or "no detail returned"
    rice_ban = intel.get("india_rice_ban_status")

    # ----- v11 Intelligence Brief — physical-logic gates -----
    if helium_exhausted():
        days = helium_days_elapsed()
        actions.append({
            "level": "critical",
            "trigger": (
                f"HELIUM EXHAUSTED — day {days} since QA force "
                f"majeure (>{HELIUM_BOIL_OFF_DAYS}-day boil-off threshold)"
            ),
            "business":
                "Semiconductor yield collapse imminent; fab "
                "stockpiles depleted. Audit any product BOM that "
                "touches helium-sealed drives, MRI cryogenics, or "
                "fab leak-test. Activate alternate-source contracts "
                "immediately. Escalate to executive committee.",
            "household":
                "Expect tech-product price spikes (storage, GPUs, "
                "MRI service) within 1-2 quarters. Defer "
                "non-essential electronics purchases.",
        })

    if CO2_BYPRODUCT_BREACH:
        actions.append({
            "level": "critical",
            "trigger": (
                f"INDUSTRIAL CO2 BYPRODUCT EXHAUSTED — "
                f"EU ammonia capacity at {EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}% "
                f"(< {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}% threshold)"
            ),
            "business":
                "Ammonia plants closed; byproduct food-grade CO2 "
                "exhausted. Audit exposure across meat processing, "
                "beverage carbonation, dry-ice cold chain, and "
                "medical gas supply. Activate alternate-source CO2 "
                "contracts immediately; pre-position 60-day inventory "
                "for any SKU dependent on food-grade CO2.",
            "household":
                "Expect tightening supply and price spikes on "
                "carbonated beverages, packaged meats, and select "
                "frozen goods over the next 4-8 weeks. Anticipate "
                "elective-procedure delays where medical CO2 is "
                "required.",
        })

    if OECD_INVENTORY_BREACH:
        actions.append({
            "level": "critical",
            "trigger": (
                f"OECD COMMERCIAL INVENTORIES "
                f"< {OECD_INVENTORY_OPERATIONAL_MIN_MB} MB "
                "operational minimum — Brent forced CRITICAL"
            ),
            "business":
                "Price is now the primary rationing mechanism. "
                "Lock fuel hedges immediately; assume Brent ≥ $130 "
                "sustained. Stress-test all transport-heavy COGS at "
                "+50%. Activate strategic-reserve coordination "
                "where applicable.",
            "household":
                "Anticipate sustained pump prices and 6-12 month "
                "inflation pass-through. Lock fixed-rate financing "
                "where possible; prioritize energy efficiency.",
        })

    jet_v_for_pct = intel.get("jet_fuel_price_ton")
    jet_pct_pb = jet_spike_pct(jet_v_for_pct)
    if jet_pct_pb is not None and jet_pct_pb > JET_FUEL_SPIKE_THRESHOLD_PCT:
        actions.append({
            "level": "critical",
            "trigger": (
                f"PAYLOAD DISPLACEMENT WARNING — "
                f"jet fuel +{jet_pct_pb:.1f}% vs baseline "
                f"(threshold {JET_FUEL_SPIKE_THRESHOLD_PCT}%)"
            ),
            "business":
                "Aviation arithmetic breaking. Cargo payload "
                "displacement begins as airlines trade revenue "
                "weight for fuel weight. Re-quote all air-freight "
                "contracts; expect 30-50% rate spikes; shift "
                "time-tolerant cargo to ocean immediately.",
            "household":
                "Air travel costs to spike substantially. Lock "
                "holiday and family-visit travel now; expect "
                "20-40% airfare increases over 4-8 weeks.",
        })

    if malacca_sev == "critical":
        actions.append({
            "level": "critical",
            "trigger": f"Strait of Malacca CRITICAL — {malacca_status}",
            "business": "Activate full Malacca-bypass contingency. Reroute "
                        "Asia-EU and intra-Asia container/tanker traffic via "
                        "Lombok / Sunda or longer-form alternatives. Declare "
                        "force majeure exposure to legal. Pre-position 60-90 "
                        "day inventory for any SKU dependent on China-EU or "
                        "Gulf-Asia lanes. Expect war-risk insurance premia "
                        "to spike materially within 48h.",
            "household": "Severe consumer-goods supply shock window opening. "
                         "Defer discretionary import-heavy purchases; "
                         "consider 2-3 month pantry of imported staples. "
                         "Anticipate fuel-price upside as Asia crude flows "
                         "are also impacted.",
        })
    elif malacca_sev == "elevated":
        actions.append({
            "level": "warn",
            "trigger": f"Strait of Malacca ELEVATED — {malacca_status}",
            "business": "Brief logistics on alternative routings. Watch "
                        "tanker and container freight indices for spread "
                        "widening over the next 72h.",
            "household": "Monitor situation; no immediate household action "
                         "required, but tighten discretionary import-goods "
                         "spend until status normalizes.",
        })
    elif malacca_shadow_active(intel):
        # v12.1 Shadow tier — fired by ships-waiting > 15% above 80-baseline,
        # even when Perplexity rates severity below "elevated".
        ships = intel.get("malacca_ships_waiting")
        delta_pct = malacca_congestion_delta_pct(intel)
        actions.append({
            "level": "warn",
            "trigger": (
                f"Strait of Malacca CONGESTION SHADOW — "
                f"{ships:.0f} ships waiting "
                f"(+{delta_pct:.1f}% vs 80/day baseline)"
            ),
            "business":
                "Lead-time window opening. Malacca congestion provides "
                "48-72 hours of warning before total global manufacturing "
                "collapse can fire as the Tail Risk trigger. Pre-position "
                "Lombok / Sunda contingency routing now; pull forward "
                "any in-flight Asia-EU container bookings; brief war-risk "
                "underwriters.",
            "household":
                "Early-warning signal active. Defer discretionary "
                "import-heavy purchases over the next 72h; lock fuel "
                "while pump-pricing is still pre-shock.",
        })

    if rice_ban == "ACTIVE":
        actions.append({
            "level": "critical",
            "trigger": "India rice export ban ACTIVE — sovereign food "
                       "policy shock in effect",
            "business": "Audit all rice-dependent SKUs (food service, "
                        "ready-meal, brewing/distillation, ethanol blend). "
                        "Lock alternate-origin supply (Thailand, Vietnam, "
                        "Pakistan) before secondary suppliers raise prices. "
                        "Brief ESG/communications on staple-food cost "
                        "pass-through. Stress-test margin on Asian and MENA "
                        "geographies which are most exposed.",
            "household": "Expect rice shelf prices to climb 20-50% within "
                         "weeks across import-dependent markets. Buy a "
                         "60-90 day supply of preferred rice variety now if "
                         "storage allows. Watch for second-order price "
                         "moves in wheat, noodles, and animal feed.",
        })

    if ttf is not None and ttf > 80:
        actions.append({
            "level": "critical",
            "trigger": f"TTF Gas > EUR 80 (live: EUR {ttf:.2f})",
            "business": "Activate gas hedging tier 2. Lock Q3 industrial demand "
                        "at fixed price. Defer non-essential heat-intensive "
                        "production runs (glass, ceramics, fertilizer).",
            "household": "Top up domestic gas storage now. Pre-pay winter "
                         "tariffs while suppliers still offer fixed rates. "
                         "Audit insulation; budget +25% on Q4 utility bills.",
        })
    elif ttf is not None and ttf > 65:
        actions.append({
            "level": "warn",
            "trigger": f"TTF Gas > EUR 65 (live: EUR {ttf:.2f})",
            "business": "Review forward gas curve. Begin tier-1 hedge "
                        "evaluation. Notify procurement of widening basis risk.",
            "household": "Review fixed-rate energy tariff offers. Consider "
                         "locking 12-month contract before year-end.",
        })

    if brent is not None and brent > 130:
        actions.append({
            "level": "critical",
            "trigger": f"Brent > USD 130 (live: USD {brent:.2f})",
            "business": "Trigger fuel surcharge clauses on logistics contracts. "
                        "Reroute freight via rail where feasible. Increase "
                        "diesel inventory buffer to 45 days.",
            "household": "Expect food and freight inflation pass-through within "
                         "6-8 weeks. Consolidate non-urgent travel. Review "
                         "discretionary budget for fuel exposure.",
        })
    elif brent is not None and brent > 115:
        actions.append({
            "level": "warn",
            "trigger": f"Brent > USD 115 (live: USD {brent:.2f})",
            "business": "Stress-test margin assumptions on transport-heavy "
                        "SKUs. Renegotiate fuel-pass-through with key clients.",
            "household": "Anticipate pump price increase within 2 weeks. Plan "
                         "fuel-efficient routing for routine commutes.",
        })

    if gold is not None and gold > 4600:
        actions.append({
            "level": "warn",
            "trigger": f"Gold > USD 4600 (live: USD {gold:.2f})",
            "business": "Confirm safe-haven flows and FX hedge ratios. Review "
                        "USD-denominated receivables exposure. Monetary-regime "
                        "stress signal active — pressure-test cash reserves.",
            "household": "Defensive positioning signal active. Avoid "
                         "concentrated equity additions; maintain cash buffer.",
        })

    if silver is not None and silver > 75:
        actions.append({
            "level": "warn",
            "trigger": f"Silver > USD 75 (live: USD {silver:.2f})",
            "business": "Industrial demand stress on solar/electronics BOM. "
                        "Lock 90-day silver futures for capex pipeline.",
            "household": "Industrial-precious correlation breakdown. Review "
                         "any silver-linked holdings for rebalancing.",
        })

    # Numeric intel: only fire if value is real (None means data
    # unavailable or 0/negative placeholder filtered out upstream).
    if urea is not None and urea > 800:
        actions.append({
            "level": "critical",
            "trigger": f"Urea spot > USD 800/t (live: USD {urea:.0f})",
            "business": "Lock 6-month urea forward for ag and industrial DEF "
                        "demand. Audit ammonia exposure in chemical inputs. "
                        "Expect food-price pass-through to grain via "
                        "fertilizer cost.",
            "household": "Anticipate grocery basket inflation in 2-3 quarters "
                         "(grains, dairy, meat). Prioritize bulk-staple "
                         "purchases before pass-through completes.",
        })
    elif urea is not None and urea > 600:
        actions.append({
            "level": "warn",
            "trigger": f"Urea spot > USD 600/t (live: USD {urea:.0f})",
            "business": "Notify ag procurement of margin pressure on N-heavy "
                        "crops. Begin scenario plan for Q3 fertilizer hedge.",
            "household": "Watch cereal and meat shelf prices for early "
                         "fertilizer-cost pass-through.",
        })

    if hormuz is not None and hormuz < 20:
        actions.append({
            "level": "critical",
            "trigger": f"Hormuz transit < 20/day (live: {hormuz:.0f})",
            "business": "Activate alternate routing assumptions (Cape, "
                        "pipeline). Stress-test 20% crude/LNG supply shock. "
                        "Pre-position 60-day fuel inventory for critical ops.",
            "household": "Expect pump-price spike within 3-6 weeks. Top up "
                         "fuel; defer optional long-haul travel; review "
                         "household emergency cash buffer.",
        })
    elif hormuz is not None and hormuz < 30:
        actions.append({
            "level": "warn",
            "trigger": f"Hormuz transit < 30/day (live: {hormuz:.0f})",
            "business": "Monitor tanker rates and insurance war-risk premia. "
                        "Pre-brief logistics on contingency routing.",
            "household": "Mild fuel-price upside risk into next month. Keep "
                         "tank above half.",
        })

    if panama is not None and panama > 4_000_000:
        actions.append({
            "level": "critical",
            "trigger": f"Panama Neopanamax slot > USD 4.0M "
                       f"(live: USD {panama:,.0f})",
            "business": "Reroute non-time-sensitive Asia-USEC freight via "
                        "Suez or USWC+rail. Re-quote container contracts; "
                        "expect FAK rate spike.",
            "household": "Holiday-season consumer goods may see 6-10% "
                         "shipping cost pass-through. Consider front-loading "
                         "large-ticket import purchases.",
        })
    elif panama is not None and panama > 2_500_000:
        actions.append({
            "level": "warn",
            "trigger": f"Panama Neopanamax slot > USD 2.5M "
                       f"(live: USD {panama:,.0f})",
            "business": "Flag canal-cost inflation to logistics finance. "
                        "Review which lanes can flex to alternative routings.",
            "household": "Modest goods-price upside risk into Q3.",
        })

    if helium is not None and helium > 2000:
        actions.append({
            "level": "warn",
            "trigger": f"Helium > USD 2000/Mcf (live: USD {helium:,.0f})",
            "business": "Tech / semiconductor / cryogenic exposure: confirm "
                        "helium contract continuity, prioritize allocations to "
                        "MRI and fab clients, defer non-critical lab/leak-test "
                        "uses, evaluate recapture systems where economics "
                        "now flip.",
            "household": "Expect indirect cost-of-care pressure (MRI / "
                         "diagnostic imaging) and modest electronics-pricing "
                         "upside. No direct household action.",
        })

    if resin is not None and resin > 40:
        actions.append({
            "level": "warn",
            "trigger": f"Asian PE/PP resin spike > 40% (live: {resin:.1f}%)",
            "business": "Medical device, packaging, and consumer goods: "
                        "audit resin BOM exposure, switch to qualified "
                        "alternate-grade suppliers, pull forward 60-day "
                        "purchase orders, model COGS pass-through to retail.",
            "household": "Expect packaged-goods price creep over the next "
                         "1-2 quarters; bulk-buy long-shelf-life staples.",
        })

    if jet is not None and jet > 1500:
        actions.append({
            "level": "warn",
            "trigger": f"Jet fuel > USD 1500/t (live: USD {jet:,.0f})",
            "business": "Aviation-exposed supply chains: re-quote air freight "
                        "contracts, shift time-tolerant cargo back to ocean, "
                        "verify fuel surcharge clauses are activated, review "
                        "T&E budgets for sales/field teams.",
            "household": "Expect airfare to climb 5-15% within 4-8 weeks. "
                         "Lock summer/holiday travel now if possible.",
        })

    # Equity Proxy Radar: a CRITICAL tier (|daily move| >= 12%) on any
    # proxy fires its own [CRITICAL] action with explicit advice to
    # audit the corresponding supply chain.
    for ticker_key in EQUITY_TICKERS:
        change = equity_changes.get(ticker_key)
        if equity_severity(change) != "critical":
            continue
        meta = EQUITY_PROXY_META[ticker_key]
        direction = "+" if change >= 0 else ""
        actions.append({
            "level": "critical",
            "trigger": (
                f"{ticker_key} spike detected — {meta['name']} "
                f"({meta['proxy_for']}) {direction}{change:.1f}% on the day"
            ),
            "business": (
                f"Audit {meta['audit']} immediately. The market is "
                f"pricing in stress on this input ahead of the physical "
                f"feed. Brief procurement, finance, and legal; tighten "
                f"the next 72h decision window."
            ),
            "household": (
                "Equity-market early-warning signal active for this "
                "input. Anticipate downstream consumer-price effects "
                "in the linked goods category over the next 4-8 weeks."
            ),
        })

    return actions


def render_strategic_outlook(adjusted: dict) -> str:
    """Pick the highest-probability scenario from `adjusted` and return
    a single self-contained HTML card with its narrative bullets.

    Color theming is sourced from PROB_COLORS so the outlook always
    matches the matrix bar above. The accent color is injected via the
    --accent CSS variable so bullet glyphs pick it up without each
    <li> needing its own inline style."""
    if not adjusted:
        return ""
    lead = max(adjusted, key=adjusted.get)
    pct = adjusted[lead]
    color = PROB_COLORS.get(lead, "#9ca3af")
    bullets = SCENARIO_NARRATIVES.get(lead, [])
    display_name = SCENARIO_DISPLAY_NAMES.get(lead, lead)

    bullets_html = "".join(
        f"<li>{html.escape(b)}</li>" for b in bullets
    )
    # Soft diagonal wash of the accent color for a "lit-up" feel.
    bg = (
        f"linear-gradient(135deg, {color}1F 0%, "
        f"rgba(17,24,39,0.0) 70%), #111827"
    )
    return (
        f'<div class="scenario-narrative" '
        f'style="--accent: {color}; '
        f'border-left-color: {color}; '
        f'background: {bg};">'
        f'<div class="scenario-narrative-header">'
        f'<span class="scenario-narrative-tag">LEAD SCENARIO</span>'
        f'<span class="scenario-narrative-title" '
        f'style="color: {color};">{html.escape(display_name)}</span>'
        f'<span class="scenario-narrative-prob" '
        f'style="color: {color}; border-color: {color}; '
        f'background: {color}1A;">{pct:.1f}% probability</span>'
        f'</div>'
        f'<ul class="scenario-narrative-bullets">{bullets_html}</ul>'
        f'</div>'
    )


def render_prob_bar(label: str, pct: float, base_pct: float):
    color = PROB_COLORS.get(label, "#9ca3af")
    delta = pct - base_pct
    delta_str = f"{delta:+.1f}" if abs(delta) >= 0.05 else "  0.0"
    st.markdown(
        f"""
        <div class="prob-bar-container">
            <div class="prob-label">
                <span>{label}</span>
                <span style="color: {color};">{pct:.1f}%  ({delta_str})</span>
            </div>
            <div class="prob-bar">
                <div class="prob-fill" style="width: {pct}%; background-color: {color};"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_numeric_html(label, value, baseline, currency, bearish_on_rise,
                      fmt="{:,.0f}", suffix="", delta_decimals=0,
                      use_baseline_fallback=True, breach=False):
    """Numeric card returning a single HTML string for the .intel-grid
    wrapper.

    Display rules:
      - If `value` is a real number, show it with the live delta vs
        baseline.
      - If `value` is None (Perplexity returned 0/null/missing) and
        `use_baseline_fallback` is True (default for intel cards), show
        the hardcoded peace-time baseline value with a subtle
        "(baseline)" tag in place of the delta.
      - If `value` is None and fallback is disabled (e.g., yfinance
        ticker fetch failure), fall through to DATA UNAVAILABLE.

    The probability engine never sees the baseline — it operates on the
    raw `intel_data` dict where missing values are still None. Fallback
    is presentation-only.

    `breach=True` adds the .intel-card-breached class for the High-Alert
    border + glow. Baseline-fallback and DATA UNAVAILABLE never show as
    breached because we cannot honestly assert a breach without live
    data."""
    label_safe = html.escape(label)
    card_class = (
        "intel-card intel-card-breached" if breach else "intel-card"
    )

    if value is None and use_baseline_fallback and baseline is not None:
        value_display = f"{currency}{fmt.format(baseline)}{suffix}"
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value">{html.escape(value_display)}'
            f'<span class="baseline-tag">(baseline)</span></div>'
            f'<div class="intel-card-baseline-note">'
            f'peace-time baseline · no live read</div>'
            f'</div>'
        )

    if value is None:
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value intel-card-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="intel-card-delta">&nbsp;</div>'
            f'</div>'
        )

    delta = value - baseline
    delta_fmt = f"{{:+,.{delta_decimals}f}}"
    delta_part = delta_fmt.format(delta)
    if baseline:
        delta_pct = (delta / baseline) * 100
        delta_str = f"{delta_part}{suffix} ({delta_pct:+.1f}%)"
    else:
        delta_str = f"{delta_part}{suffix} (vs 0 baseline)"
    # Pill color follows the Threshold Monitor verdict, NOT the daily
    # delta direction. This kills the "false green" bug: e.g., Gold has
    # bearish_on_rise=False (haven-flow framing) but its threshold is
    # `> $4600`, so a $5000 reading USED to render a green pill (delta
    # vs baseline is positive in the "good" direction) while the card
    # border was red (breached). With this rule:
    #   breach=True  → red pill, regardless of which way the day moved
    #   breach=False → green pill (only NOMINAL gets green)
    # `bearish_on_rise` is now informational only — kept on the
    # signature for compatibility but no longer drives pill color.
    delta_class = "delta-bear" if breach else "delta-bull"
    value_display = f"{currency}{fmt.format(value)}{suffix}"
    return (
        f'<div class="{card_class}">'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'<div class="intel-card-value">{html.escape(value_display)}</div>'
        f'<div class="intel-card-delta {delta_class}">'
        f'{html.escape(delta_str)}</div>'
        f'</div>'
    )


def card_status_html(label, value_text, value_color, detail,
                     is_baseline=False, breach=False):
    """Qualitative card returning a single HTML string. value_text=None
    → DATA UNAVAILABLE (used only when no peace-time baseline applies).

    When `is_baseline` is True, a small italic "(baseline)" tag is
    appended to the value and the detail line is rendered in muted
    grey. The card otherwise looks like a live nominal reading. The
    detail string can contain Perplexity-sourced text and is
    HTML-escaped to defend against payload tampering.

    `breach=True` adds the .intel-card-breached High-Alert class on top
    of the existing severity-colored border (e.g., Malacca elevated /
    critical, India rice ban ACTIVE)."""
    label_safe = html.escape(label)
    detail_safe = html.escape(detail) if detail else "&nbsp;"
    base_class = (
        "intel-card intel-card-breached" if breach else "intel-card"
    )
    if value_text is None:
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value intel-card-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="intel-card-detail">{detail_safe}</div>'
            f'</div>'
        )
    color = html.escape(value_color or "#9ca3af")
    baseline_tag = (
        '<span class="baseline-tag">(baseline)</span>' if is_baseline else ""
    )
    detail_class = (
        "intel-card-baseline-note" if is_baseline else "intel-card-detail"
    )
    return (
        f'<div class="{base_class}" style="border-color: {color};">'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'<div class="intel-card-value" style="color: {color};">'
        f'● {html.escape(value_text)}{baseline_tag}</div>'
        f'<div class="{detail_class}">{detail_safe}</div>'
        f'</div>'
    )


# ---------- API KEY: load from Streamlit secrets (read-only deploy) ----------
# The dashboard is public and read-only. The Perplexity key lives in
# Streamlit secrets (.streamlit/secrets.toml on Cloud / "Secrets" panel
# on Community Cloud), never in user input.
try:
    api_key = st.secrets["PERPLEXITY_API_KEY"]
except Exception:
    api_key = None

# ---------- SIDEBAR: read-only feed status ----------
with st.sidebar:
    st.markdown(
        '<h3 class="hud-title" style="font-size:0.95rem;">◆ FEED STATUS</h3>',
        unsafe_allow_html=True,
    )
    if api_key:
        st.markdown(
            '<div style="font-size:0.75rem;color:#9ca3af;'
            'font-family:Courier New,monospace;line-height:1.6;">'
            'Mode: <span style="color:#00ffd1;">PUBLIC / READ-ONLY</span><br>'
            'Intel: <span style="color:#00ffd1;">ARMED</span><br>'
            'Refresh: <span style="color:#9ca3af;">auto, 4h cache</span><br>'
            'Sources: yfinance + perplexity sonar-pro'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.error(
            "PERPLEXITY_API_KEY is missing from Streamlit secrets. "
            "Add it to .streamlit/secrets.toml (or the Streamlit Cloud "
            "Secrets panel) to enable the logistics & inputs intel feed. "
            "The commodity ticker feed will continue without it.",
            icon="🔐",
        )


# ---------- MAIN HEADER ----------
st.markdown('<h1 class="hud-title">■ Global Supply Chain Contagion HUD</h1>',
            unsafe_allow_html=True)

now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
intel_status = (
    '<span style="color:#00ffd1;">ARMED</span>'
    if api_key
    else '<span style="color:#eab308;">STANDBY (no key)</span>'
)
st.markdown(
    f'<div class="status-strip">FEED: yfinance + perplexity '
    f'&nbsp;|&nbsp; SAMPLE: {now} &nbsp;|&nbsp; '
    f'BASELINE: April 2026 (post-blockade) &nbsp;|&nbsp; '
    f'INTEL: {intel_status}</div>',
    unsafe_allow_html=True,
)

# v11 blockade banner — reflects the April 27 Iranian-offer rejection
# and the resulting extended Hormuz blockade.
st.markdown(
    '<div class="status-strip" '
    'style="border-left-color:#dc2626;color:#fca5a5;'
    'background:rgba(220,38,38,0.08);">'
    '◆ EXTENDED BLOCKADE CONFIRMED &nbsp;|&nbsp; '
    'US rejected the Apr 27 Iranian offer &nbsp;|&nbsp; '
    'Best Case probability collapsed to 0% — weight redistributed to '
    'Base Case (60%) and Tail Risk (40%).</div>',
    unsafe_allow_html=True,
)

# ---------- DATA FETCH (consolidated; runs before any rendering) ----------
# All upstream data is fetched once here so the Strategic Outlook,
# Commodity Telemetry, Equity Proxy Radar, Logistics & Inputs Intel,
# Probability Matrix, and Threshold Monitor all read from the same
# 4-hour-cached snapshot. Caching is on each individual fetch
# function (@st.cache_data ttl=14400), so subsequent reruns are free.
with st.spinner("Pulling live commodity feed..."):
    prices = {name: fetch_price(tk) for name, tk in TICKERS.items()}

with st.spinner("Pulling equity proxy snapshots..."):
    equity_snapshots = {
        key: fetch_equity_snapshot(tk) for key, tk in EQUITY_TICKERS.items()
    }
equity_changes = {
    key: snap.get("pct_change") for key, snap in equity_snapshots.items()
}

intel_data = {}
intel_meta = {"fetched_at": None, "error": None, "raw": None}
if api_key:
    with st.spinner("Querying Perplexity sonar-pro for logistics intel..."):
        intel_result = fetch_perplexity_intel(api_key)
    intel_meta["fetched_at"] = intel_result.get("fetched_at")
    intel_meta["error"] = intel_result.get("error")
    intel_meta["raw"] = intel_result.get("raw")
    intel_data = intel_result.get("data") or {}
else:
    intel_meta["error"] = "Perplexity intel paused — no API key."

# Compute scenario probabilities from the consolidated snapshot.
adjusted = adjust_probabilities(prices, intel_data, equity_changes)

# ---------- STRATEGIC OUTLOOK (lead scenario, top of page) ----------
st.markdown(
    '<h3 class="hud-title">◆ Strategic Outlook</h3>',
    unsafe_allow_html=True,
)
st.markdown(render_strategic_outlook(adjusted), unsafe_allow_html=True)
st.markdown("&nbsp;", unsafe_allow_html=True)

# ---------- v12.1 STRUCTURAL BREAK: 3-COLUMN LAYOUT ----------
# Column 1: Commodity Telemetry + Equity Proxy Radar + AI Storage HDD Countdown
# Column 2: Logistics & Inputs Intel + Systemic Cascade Map
# Column 3: Scenario Probability Matrix + Threshold Monitor
#
# All three columns read from the same 4-hour cached snapshot
# (`prices`, `equity_snapshots`, `equity_changes`, `intel_data`,
# `adjusted`) computed in the consolidated DATA FETCH block above.
# st.secrets-loaded api_key remains unchanged.

# ----- Module-scope helpers shared across columns -----
EQUITY_TIER_COLORS = {
    "nominal": "#10b981",
    "warning": "#eab308",
    "critical": "#dc2626",
}
EQUITY_TIER_GLYPH = {
    "nominal": "🟢",
    "warning": "🟡",
    "critical": "🔴",
}


def card_equity_html(ticker_key, snapshot):
    """Equity proxy card. WARNING and CRITICAL tiers (|daily move| >= 5%
    and >= 12%) both raise the High-Alert breach state — red border,
    soft red glow, red delta pill. NOMINAL stays plain.

    Each card carries a small italic 'why it matters' footer sourced
    from EQUITY_PROXY_META, explaining the strategic linkage between
    the equity move and the underlying physical-commodity risk."""
    meta = EQUITY_PROXY_META[ticker_key]
    label_safe = html.escape(meta["name"])
    proxy_safe = html.escape(meta["proxy_for"])
    context_safe = html.escape(meta.get("why_it_matters", ""))
    context_html = (
        f'<div class="intel-card-context">{context_safe}</div>'
        if context_safe
        else ""
    )
    price = snapshot.get("price")
    change = snapshot.get("pct_change")
    sev = equity_severity(change)

    if price is None and change is None:
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value intel-card-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="intel-card-delta">proxy: {proxy_safe}</div>'
            f'{context_html}'
            f'</div>'
        )

    is_breach = sev in ("warning", "critical")
    card_class = (
        "intel-card intel-card-breached" if is_breach else "intel-card"
    )
    glyph = EQUITY_TIER_GLYPH.get(sev or "nominal", "●")
    tier_label = (sev or "nominal").upper()
    price_str = f"${price:,.2f}" if price is not None else "—"

    if change is None:
        delta_html = (
            f'<div class="intel-card-delta">'
            f'proxy: {proxy_safe} · daily Δ unavailable</div>'
        )
    else:
        change_str = f"{'+' if change >= 0 else ''}{change:.2f}%"
        delta_class = "delta-bear" if is_breach else "delta-flat"
        delta_html = (
            f'<div class="intel-card-delta {delta_class}">'
            f'{glyph} {tier_label} &nbsp;·&nbsp; {change_str} '
            f'&nbsp;·&nbsp; {proxy_safe}</div>'
        )
    return (
        f'<div class="{card_class}">'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'<div class="intel-card-value">{price_str}</div>'
        f'{delta_html}'
        f'{context_html}'
        f'</div>'
    )


def render_threshold_row_html(name, live_html, status_html,
                              insight_key=None, breached=False,
                              warning=False):
    """v12.1 — Threshold Monitor row builder.

    When `breached` (or `warning`) is True and an `insight_key` is
    provided, the row renders as an inline <details>/<summary> expander
    with an "Intelligence Insight" block sourced from
    INTELLIGENCE_INSIGHTS[insight_key]. Click toggles the explanation.

    Otherwise the row renders as a plain non-interactive div with the
    same visual layout. `live_html` is interpolated as-is (it can carry
    the baseline-tag span); `name` is HTML-escaped here."""
    name_safe = html.escape(name)
    insight_text = (
        INTELLIGENCE_INSIGHTS.get(insight_key)
        if insight_key and (breached or warning)
        else None
    )

    row_class = "threshold-row"
    if breached:
        row_class += " threshold-breached"
    elif warning:
        row_class += " threshold-warning"

    summary_inner = (
        f'<span class="t-name">{name_safe}</span>'
        f'<span class="t-live">live: {live_html}</span>'
        f'<span class="t-status">{status_html}</span>'
    )

    if insight_text:
        insight_class = "threshold-insight"
        if warning and not breached:
            insight_class += " insight-warn"
        return (
            f'<details class="{row_class}">'
            f'<summary class="threshold-summary">{summary_inner}</summary>'
            f'<div class="{insight_class}">'
            f'<strong>Intelligence Insight</strong>'
            f'{html.escape(insight_text)}'
            f'</div>'
            f'</details>'
        )
    return (
        f'<div class="{row_class}">'
        f'<div class="threshold-summary">{summary_inner}</div>'
        f'</div>'
    )


# ----- Per-metric values + breach flags computed once for re-use -----
brent_v = prices["Brent"]
ttf_v = prices["TTF"]
gold_v = prices["Gold"]
silver_v = prices["Silver"]
panama_v = intel_data.get("panama_canal_neopanamax_price")
urea_v = intel_data.get("urea_spot_price_ton")
hormuz_v = intel_data.get("hormuz_daily_transit_count")
helium_v = intel_data.get("helium_spot_price_mcf")
resin_v = intel_data.get("asian_pe_pp_resin_spike")
jet_v = intel_data.get("jet_fuel_price_ton")
malacca_sev = intel_data.get("malacca_severity")
malacca_status = intel_data.get("malacca_status")
malacca_ships = intel_data.get("malacca_ships_waiting")
rice_ban = intel_data.get("india_rice_ban_status")
shadow_active = malacca_shadow_active(intel_data)
shadow_pct = malacca_congestion_delta_pct(intel_data)

# OECD inventory breach forces Brent to CRITICAL regardless of spot.
brent_breach = (brent_v is not None and brent_v > 115) or OECD_INVENTORY_BREACH

# ----- 3-column shell -----
col1, col2, col3 = st.columns([1, 1, 1])

# ============================================================
# COLUMN 1 — Commodity & Equity Proxies
# ============================================================
with col1:
    st.markdown(
        '<div class="col-section-title">◆ Commodity Telemetry</div>',
        unsafe_allow_html=True,
    )
    commodity_cards = [
        card_numeric_html(
            "BRENT CRUDE  (BZ=F)", brent_v, BASELINE["Brent"],
            "$", True, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=brent_breach,
        ),
        card_numeric_html(
            "TTF GAS  (TTF=F)", ttf_v, BASELINE["TTF"],
            "€", True, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=ttf_v is not None and ttf_v > 65,
        ),
        card_numeric_html(
            "GOLD  (GC=F)", gold_v, BASELINE["Gold"],
            "$", False, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=gold_v is not None and gold_v > 4600,
        ),
        card_numeric_html(
            "SILVER  (SI=F)", silver_v, BASELINE["Silver"],
            "$", False, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=silver_v is not None and silver_v > 75,
        ),
    ]
    st.markdown(
        '<div class="intel-grid">' + "".join(commodity_cards) + '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="col-section-title">◆ Equity Proxy Radar</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="radar-explainer">'
        "These equities are the most liquid leading indicators for "
        "physical commodities currently blocked by the Hormuz conflict. "
        "They reflect institutional &ldquo;smart money&rdquo; pricing in "
        "shortages before they reach the public news cycle."
        '</div>',
        unsafe_allow_html=True,
    )
    equity_cards = [
        card_equity_html(key, equity_snapshots[key])
        for key in EQUITY_TICKERS
    ]
    st.markdown(
        '<div class="intel-grid">' + "".join(equity_cards) + '</div>',
        unsafe_allow_html=True,
    )

    # ----- v12.1 §1: HDD Stockout Countdown ("AI Storage" section) -----
    # Days remaining from today through Dec 31, 2026 — the structural
    # enterprise-channel hardware freeze window driven by hyperscaler
    # contract lockups on WDC/STX 2026 output.
    _hdd_days = hdd_stockout_days_remaining()
    _hdd_target_str = HDD_STOCKOUT_TARGET_DATE.strftime("%B %d, %Y")
    st.markdown(
        '<div class="col-section-title">◆ AI Storage</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="hdd-countdown">'
        f'<div class="hdd-countdown-label">'
        f'Estimated Enterprise HDD Stockout</div>'
        f'<div class="hdd-countdown-value">{_hdd_days}'
        f'<span class="hdd-unit">DAYS REMAINING</span></div>'
        f'<div class="hdd-countdown-target">'
        f'window closes {_hdd_target_str}</div>'
        f'<div class="hdd-countdown-alert">'
        f'95% of WDC/STX output locked to hyperscaler contracts. '
        f'Standard enterprise channels are in a physical hardware freeze.'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# COLUMN 2 — Logistics & Physical Inputs (Helium / CO2)
# ============================================================
with col2:
    st.markdown(
        '<div class="col-section-title">◆ Logistics &amp; Inputs Intel '
        '<span class="intel-tag">PERPLEXITY</span></div>',
        unsafe_allow_html=True,
    )

    intel_cards = []

    intel_cards.append(card_numeric_html(
        "PANAMA NEOPANAMAX  (slot $)",
        panama_v,
        INTEL_BASELINE["panama_canal_neopanamax_price"],
        "$", True, fmt="{:,.0f}",
        breach=panama_v is not None and panama_v > 2_500_000,
    ))
    intel_cards.append(card_numeric_html(
        "UREA SPOT  ($/ton)",
        urea_v,
        INTEL_BASELINE["urea_spot_price_ton"],
        "$", True, fmt="{:,.0f}",
        breach=urea_v is not None and urea_v > 600,
    ))
    intel_cards.append(card_numeric_html(
        "HORMUZ TRANSITS  (ships/day)",
        hormuz_v,
        INTEL_BASELINE["hormuz_daily_transit_count"],
        "", False, fmt="{:.0f}",
        breach=hormuz_v is not None and hormuz_v < 30,
    ))

    # v12.1 §2: Malacca Shadow Indicator — the upgraded Malacca card.
    # Three-state precedence (highest → lowest):
    #   1. Perplexity-flagged "critical" → red CRITICAL card.
    #   2. Shadow active (ships waiting >15% above 80-baseline) AND
    #      Perplexity not flagging elevated/critical → 🟡 WARNING:
    #      CONGESTION SHADOW with the 48-72h lead-time intelligence
    #      note.
    #   3. Otherwise existing severity logic (elevated / nominal /
    #      baseline fallback).
    if malacca_sev == "critical":
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            "CRITICAL",
            SEVERITY_COLORS["critical"],
            malacca_status or "(no status text returned)",
            breach=True,
        ))
    elif shadow_active and malacca_sev != "elevated":
        # CONGESTION SHADOW takes precedence over peace-time / nominal
        # readings when ships_waiting > 80 * 1.15. Tail-Risk lead-time
        # window is open even if Perplexity has not yet escalated.
        ships_label = f"{malacca_ships:.0f} ships waiting" if (
            malacca_ships is not None
        ) else "ships waiting"
        delta_label = (
            f" (+{shadow_pct:.1f}% vs 80/day baseline)"
            if shadow_pct is not None else ""
        )
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            "🟡 WARNING: CONGESTION SHADOW",
            "#eab308",
            f"{ships_label}{delta_label}. Malacca congestion provides "
            "48–72 hours of lead time before total global manufacturing "
            "collapse (Tail Risk Trigger).",
            breach=True,
        ))
    elif malacca_sev is None and malacca_status is None:
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            MALACCA_BASELINE_SEVERITY.upper(),
            SEVERITY_COLORS.get(MALACCA_BASELINE_SEVERITY, "#9ca3af"),
            MALACCA_BASELINE_STATUS,
            is_baseline=True,
        ))
    else:
        sev = malacca_sev or "nominal"
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            sev.upper(),
            SEVERITY_COLORS.get(sev, "#9ca3af"),
            malacca_status or "(no status text returned)",
            breach=sev == "elevated",
        ))

    if helium_exhausted():
        _he_days = helium_days_elapsed()
        _days_past = _he_days - HELIUM_BOIL_OFF_DAYS
        intel_cards.append(card_status_html(
            "INDUSTRIAL HELIUM (Qatar FM)",
            f"DAY {_he_days} — EXHAUSTED",
            "#dc2626",
            f"{_days_past} days past physical shelf-life limit. "
            "Semiconductor yield collapse imminent; fab floor reserves "
            "depleted.",
            breach=True,
        ))
    else:
        intel_cards.append(card_numeric_html(
            "HELIUM SPOT  ($/Mcf)",
            helium_v,
            INTEL_BASELINE["helium_spot_price_mcf"],
            "$", True, fmt="{:,.0f}",
            breach=helium_v is not None and helium_v > 2000,
        ))

    if CO2_BYPRODUCT_BREACH:
        intel_cards.append(card_status_html(
            f"INDUSTRIAL CO2 BYPRODUCT (EU ammonia "
            f"{EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}%)",
            "EXHAUSTED",
            "#dc2626",
            "Ammonia plants closed; byproduct food-grade CO2 exhausted. "
            "Meat processing, soft drinks, and medical gas at risk.",
            breach=True,
        ))
    else:
        intel_cards.append(card_status_html(
            "INDUSTRIAL CO2 BYPRODUCT",
            "NOMINAL",
            "#10b981",
            "European ammonia capacity within nominal range; food-grade "
            "CO2 byproduct supply stable.",
        ))

    intel_cards.append(card_numeric_html(
        "PE/PP RESIN SPIKE  (Asia)",
        resin_v,
        INTEL_BASELINE["asian_pe_pp_resin_spike"],
        "", True, fmt="{:.1f}", suffix="%", delta_decimals=1,
        breach=resin_v is not None and resin_v > 40,
    ))
    intel_cards.append(card_numeric_html(
        "JET FUEL  ($/ton)",
        jet_v,
        INTEL_BASELINE["jet_fuel_price_ton"],
        "$", True, fmt="{:,.0f}",
        breach=jet_v is not None and jet_v > 1500,
    ))

    if rice_ban == "ACTIVE":
        intel_cards.append(card_status_html(
            "INDIA RICE EXPORT BAN", "ACTIVE", "#dc2626",
            "Indian government export ban currently in force on at "
            "least one rice category. Sovereign food-policy shock "
            "active.",
            breach=True,
        ))
    elif rice_ban == "INACTIVE":
        intel_cards.append(card_status_html(
            "INDIA RICE EXPORT BAN", "INACTIVE", "#10b981",
            "No active Indian rice export ban currently in force.",
        ))
    else:
        intel_cards.append(card_status_html(
            "INDIA RICE EXPORT BAN",
            RICE_BAN_BASELINE,
            "#10b981",
            "Peace-time baseline — no active export ban on file.",
            is_baseline=True,
        ))

    st.markdown(
        '<div class="intel-grid">' + "".join(intel_cards) + '</div>',
        unsafe_allow_html=True,
    )

    if intel_meta["error"]:
        st.markdown(
            f'<div class="alert-warn" style="margin-top:0.5rem;">'
            f'INTEL FEED: {intel_meta["error"]}</div>',
            unsafe_allow_html=True,
        )
    elif intel_meta["fetched_at"]:
        st.markdown(
            f'<div class="status-strip" style="margin-top:0.5rem;">'
            f'INTEL CAPTURED: {intel_meta["fetched_at"]} '
            f'&nbsp;|&nbsp; SOURCE: perplexity sonar-pro</div>',
            unsafe_allow_html=True,
        )

    # ----- v12.1 §3: Systemic Cascade Map (Energy → Medical) -----
    # Visual chain of physical dependencies: natural gas drives
    # ammonia; ammonia carries food-grade CO2 as byproduct; that CO2
    # is what carbonates beverages, packs meat, and supplies medical
    # gas. When EU ammonia capacity < 40%, the CO2 and Meat/Medical
    # nodes flip RED to mark the active downstream collapse.
    _cascade_red_class = "cascade-red" if CO2_BYPRODUCT_BREACH else ""
    if CO2_BYPRODUCT_BREACH:
        _cascade_note = (
            f'<div class="cascade-trigger-note cascade-active">'
            f'<strong style="color:#fca5a5;">▼ CASCADE ACTIVE</strong> '
            f'— EU ammonia at {EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}% '
            f'(below {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}% threshold). '
            f'Food-grade CO2 byproduct is exhausted; downstream nodes '
            f'(meat shelf-life, beverage carbonation, MRI cryogenics) '
            f'all degrade in parallel.'
            f'</div>'
        )
    else:
        _cascade_note = (
            f'<div class="cascade-trigger-note">'
            f'EU ammonia capacity at {EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}% '
            f'(threshold {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}%). '
            f'Cascade nodes nominal — food-grade CO2 byproduct supply '
            f'stable.'
            f'</div>'
        )
    st.markdown(
        f'<div class="cascade-container">'
        f'<div class="col-section-title" '
        f'style="margin:0 0 0.35rem 0;border:none;padding:0;">'
        f'◆ Systemic Cascade: Energy to Medical</div>'
        f'<div class="cascade-flow">'
        f'<div class="cascade-node cascade-source">'
        f'<div class="cascade-node-title">Source</div>'
        f'Energy<br>(Natural Gas)</div>'
        f'<div class="cascade-arrow">▶</div>'
        f'<div class="cascade-node cascade-mid">'
        f'<div class="cascade-node-title">Stage 2</div>'
        f'Ammonia<br>Production</div>'
        f'<div class="cascade-arrow">▶</div>'
        f'<div class="cascade-node cascade-mid {_cascade_red_class}">'
        f'<div class="cascade-node-title">Byproduct</div>'
        f'CO₂<br>Byproduct</div>'
        f'<div class="cascade-arrow">▶</div>'
        f'<div class="cascade-node cascade-sink {_cascade_red_class}">'
        f'<div class="cascade-node-title">Endpoint</div>'
        f'Meat /<br>Medical Gas</div>'
        f'</div>'
        f'{_cascade_note}'
        f'</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# COLUMN 3 — Threshold Monitor & Scenario Probability
# ============================================================
with col3:
    st.markdown(
        '<div class="col-section-title">◆ Scenario Probability Matrix</div>',
        unsafe_allow_html=True,
    )
    for label in ["Best Case", "Slow Normalization",
                  "Base Case", "Tail Risk"]:
        render_prob_bar(label, adjusted[label], BASE_PROBS[label])

    drift = sum(abs(adjusted[k] - BASE_PROBS[k]) for k in BASE_PROBS) / 2
    notes = []
    if intel_data.get("malacca_severity") == "critical":
        notes.append('<span style="color:#dc2626;">'
                     'MALACCA OVERRIDE — TAIL RISK MAX</span>')
    if intel_data.get("india_rice_ban_status") == "ACTIVE":
        notes.append('<span style="color:#dc2626;">'
                     'RICE BAN — STAPLES SHOCK</span>')
    if shadow_active and intel_data.get("malacca_severity") not in (
        "elevated", "critical"
    ):
        notes.append('<span style="color:#eab308;">'
                     'CONGESTION SHADOW — 48-72h LEAD WINDOW</span>')
    drift_note = (
        " &nbsp;|&nbsp; " + " &nbsp;·&nbsp; ".join(notes)
    ) if notes else ""
    st.markdown(
        f'<div class="status-strip">SCENARIO DRIFT vs BASELINE: '
        f'<span style="color:#00ffd1;">{drift:.1f} pts</span>'
        f'{drift_note}</div>',
        unsafe_allow_html=True,
    )

    # ----- Threshold Monitor (with Intelligence Insight expanders) -----
    st.markdown(
        '<div class="col-section-title">◆ Threshold Monitor</div>',
        unsafe_allow_html=True,
    )

    # 8-tuple: (name, val, thr, cur, op, sfx, baseline, insight_key).
    # baseline=None → DATA UNAVAILABLE on missing val (yfinance feed).
    # baseline=number → fall back to baseline display when val is None
    # (Perplexity intel) — engine still sees None upstream so the math
    # is unchanged. insight_key drives the v12.1 "Intelligence Insight"
    # expander shown when the row is BREACHED or in WARNING tier.
    thresholds = [
        ("Brent > $130", prices["Brent"], 130, "$", "gt", "", None, "brent"),
        ("Brent > $115", prices["Brent"], 115, "$", "gt", "", None, "brent"),
        ("TTF > €80", prices["TTF"], 80, "€", "gt", "", None, "ttf"),
        ("TTF > €65", prices["TTF"], 65, "€", "gt", "", None, "ttf"),
        ("Gold > $4600", prices["Gold"], 4600, "$", "gt", "", None, "gold"),
        ("Silver > $75", prices["Silver"], 75, "$", "gt", "", None, "silver"),
        ("Urea > $800/t", urea_v, 800, "$", "gt", "",
         INTEL_BASELINE["urea_spot_price_ton"], "urea"),
        ("Urea > $600/t", urea_v, 600, "$", "gt", "",
         INTEL_BASELINE["urea_spot_price_ton"], "urea"),
        ("Hormuz < 30/day", hormuz_v, 30, "", "lt", "",
         INTEL_BASELINE["hormuz_daily_transit_count"], "hormuz"),
        ("Hormuz < 20/day", hormuz_v, 20, "", "lt", "",
         INTEL_BASELINE["hormuz_daily_transit_count"], "hormuz"),
        ("Panama slot > $2.5M", panama_v, 2_500_000, "$", "gt", "",
         INTEL_BASELINE["panama_canal_neopanamax_price"], "panama"),
        ("Panama slot > $4.0M", panama_v, 4_000_000, "$", "gt", "",
         INTEL_BASELINE["panama_canal_neopanamax_price"], "panama"),
        ("Helium > $2000/Mcf", helium_v, 2000, "$", "gt", "",
         INTEL_BASELINE["helium_spot_price_mcf"], "helium"),
        ("Resins > 40% spike", resin_v, 40, "", "gt", "%",
         INTEL_BASELINE["asian_pe_pp_resin_spike"], "resin"),
        ("Jet Fuel > $1500/t", jet_v, 1500, "$", "gt", "",
         INTEL_BASELINE["jet_fuel_price_ton"], "jet"),
    ]
    threshold_rows_html = []
    for name, val, thr, cur, op, sfx, baseline_val, insight_key in thresholds:
        is_fallback = val is None and baseline_val is not None
        display_val = baseline_val if is_fallback else val

        if display_val is None:
            status_html = (
                '<span style="color:#6b7280;">— DATA UNAVAILABLE</span>'
            )
            live_html = "—"
            row_breached = False
        else:
            row_breached = (
                (op == "gt" and display_val > thr)
                or (op == "lt" and display_val < thr)
            )
            if row_breached:
                status_html = (
                    '<span style="color:#dc2626;">● BREACHED</span>'
                )
            else:
                status_html = (
                    '<span style="color:#10b981;">● NOMINAL</span>'
                )
            if cur:
                live_html = f"{cur}{display_val:,.0f}{sfx}"
            else:
                live_html = (
                    f"{display_val:,.1f}{sfx}"
                    if sfx == "%"
                    else f"{display_val:.0f}"
                )
            if is_fallback:
                live_html += (
                    ' <span class="baseline-tag">(baseline)</span>'
                )
        threshold_rows_html.append(render_threshold_row_html(
            name, live_html, status_html,
            insight_key=insight_key, breached=row_breached,
        ))

    # Malacca severity row — three-state including the new shadow tier.
    if malacca_sev == "critical":
        m_status = (
            '<span style="color:#dc2626;">● BREACHED (CRITICAL)</span>'
        )
        m_live = "critical"
        m_breach, m_warn, m_key = True, False, "malacca_critical"
    elif shadow_active and malacca_sev != "elevated":
        m_status = (
            '<span style="color:#eab308;">'
            '● WARNING (CONGESTION SHADOW)</span>'
        )
        if shadow_pct is not None:
            m_live = f"+{shadow_pct:.1f}% vs 80/day baseline"
        else:
            m_live = "shadow active"
        m_breach, m_warn, m_key = False, True, "malacca_shadow"
    elif malacca_sev == "elevated":
        m_status = '<span style="color:#eab308;">● ELEVATED</span>'
        m_live = "elevated"
        m_breach, m_warn, m_key = False, True, "malacca_critical"
    elif malacca_sev is None:
        m_status = '<span style="color:#10b981;">● NOMINAL</span>'
        m_live = (
            f'{MALACCA_BASELINE_SEVERITY} '
            f'<span class="baseline-tag">(baseline)</span>'
        )
        m_breach, m_warn, m_key = False, False, None
    else:
        m_status = '<span style="color:#10b981;">● NOMINAL</span>'
        m_live = "nominal"
        m_breach, m_warn, m_key = False, False, None
    threshold_rows_html.append(render_threshold_row_html(
        "Malacca severity", m_live, m_status,
        insight_key=m_key, breached=m_breach, warning=m_warn,
    ))

    # India rice ban row.
    if rice_ban is None:
        r_status = '<span style="color:#10b981;">● NOMINAL</span>'
        r_live = (
            f'{RICE_BAN_BASELINE} '
            f'<span class="baseline-tag">(baseline)</span>'
        )
        r_breach, r_key = False, None
    elif rice_ban == "ACTIVE":
        r_status = (
            '<span style="color:#dc2626;">● BREACHED (ACTIVE)</span>'
        )
        r_live = "ACTIVE"
        r_breach, r_key = True, "rice"
    else:
        r_status = '<span style="color:#10b981;">● NOMINAL</span>'
        r_live = "INACTIVE"
        r_breach, r_key = False, None
    threshold_rows_html.append(render_threshold_row_html(
        "India rice ban", r_live, r_status,
        insight_key=r_key, breached=r_breach,
    ))

    # OECD commercial inventory row.
    if OECD_INVENTORY_BREACH:
        oecd_live = f"&lt; {OECD_INVENTORY_OPERATIONAL_MIN_MB} MB"
        oecd_status = (
            '<span style="color:#dc2626;">● BREACHED (CRITICAL)</span>'
        )
        oecd_breach, oecd_key = True, "oecd"
    else:
        oecd_live = f"&gt;= {OECD_INVENTORY_OPERATIONAL_MIN_MB} MB"
        oecd_status = '<span style="color:#10b981;">● NOMINAL</span>'
        oecd_breach, oecd_key = False, None
    threshold_rows_html.append(render_threshold_row_html(
        f"OECD commercial inv < {OECD_INVENTORY_OPERATIONAL_MIN_MB} MB",
        oecd_live, oecd_status,
        insight_key=oecd_key, breached=oecd_breach,
    ))

    # EU ammonia → CO2 byproduct row.
    if CO2_BYPRODUCT_BREACH:
        co2_live = (
            f"{EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}% "
            f"(&lt; {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}%)"
        )
        co2_status = (
            '<span style="color:#dc2626;">'
            '● BREACHED (CO2 EXHAUSTED)</span>'
        )
        co2_breach, co2_key = True, "co2"
    else:
        co2_live = (
            f"{EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}% "
            f"(&gt;= {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}%)"
        )
        co2_status = '<span style="color:#10b981;">● NOMINAL</span>'
        co2_breach, co2_key = False, None
    threshold_rows_html.append(render_threshold_row_html(
        f"EU ammonia capacity < {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}%",
        co2_live, co2_status,
        insight_key=co2_key, breached=co2_breach,
    ))

    # Helium boil-off (days since QA force majeure).
    _he_days = helium_days_elapsed()
    if helium_exhausted():
        he_live = f"day {_he_days} / {HELIUM_BOIL_OFF_DAYS}"
        he_status = (
            '<span style="color:#dc2626;">● BREACHED (EXHAUSTED)</span>'
        )
        he_breach, he_key = True, "helium_boiloff"
    else:
        he_live = f"day {_he_days} / {HELIUM_BOIL_OFF_DAYS}"
        he_status = '<span style="color:#10b981;">● NOMINAL</span>'
        he_breach, he_key = False, None
    threshold_rows_html.append(render_threshold_row_html(
        "Helium boil-off (QA FM)", he_live, he_status,
        insight_key=he_key, breached=he_breach,
    ))

    # Jet fuel "Payload Displacement" gate (>55% above baseline).
    _jet_pct_tm = jet_spike_pct(jet_v)
    if _jet_pct_tm is None:
        jp_live = "—"
        jp_status = (
            '<span style="color:#6b7280;">— DATA UNAVAILABLE</span>'
        )
        jp_breach, jp_key = False, None
    elif _jet_pct_tm > JET_FUEL_SPIKE_THRESHOLD_PCT:
        jp_live = f"+{_jet_pct_tm:.1f}% vs baseline"
        jp_status = (
            '<span style="color:#dc2626;">'
            '● BREACHED (PAYLOAD DISPLACEMENT)</span>'
        )
        jp_breach, jp_key = True, "jet_displacement"
    else:
        jp_live = f"+{_jet_pct_tm:.1f}% vs baseline"
        jp_status = '<span style="color:#10b981;">● NOMINAL</span>'
        jp_breach, jp_key = False, None
    threshold_rows_html.append(render_threshold_row_html(
        f"Jet fuel spike > {JET_FUEL_SPIKE_THRESHOLD_PCT}%",
        jp_live, jp_status,
        insight_key=jp_key, breached=jp_breach,
    ))

    # Equity Proxy Radar rows. CRITICAL (|Δ|>=12%) and WARNING
    # (|Δ|>=5%) tiers both unfold the equity_critical insight.
    for ticker_key in EQUITY_TICKERS:
        meta = EQUITY_PROXY_META[ticker_key]
        change = equity_changes.get(ticker_key)
        sev = equity_severity(change)

        if change is None:
            eq_live = "—"
            eq_status = (
                '<span style="color:#6b7280;">— DATA UNAVAILABLE</span>'
            )
            eq_breach, eq_warn, eq_key = False, False, None
        else:
            eq_live = (
                f"{'+' if change >= 0 else ''}{change:.2f}% spike"
            )
            color = EQUITY_TIER_COLORS.get(sev, "#9ca3af")
            glyph = EQUITY_TIER_GLYPH.get(sev, "●")
            tier = (sev or "nominal").upper()
            eq_status = (
                f'<span style="color: {color};">{glyph} {tier}</span>'
            )
            eq_breach = sev == "critical"
            eq_warn = sev == "warning"
            eq_key = "equity_critical" if (eq_breach or eq_warn) else None

        row_label = f"{ticker_key} ({meta['proxy_for']})"
        threshold_rows_html.append(render_threshold_row_html(
            row_label, eq_live, eq_status,
            insight_key=eq_key, breached=eq_breach, warning=eq_warn,
        ))

    st.markdown("".join(threshold_rows_html), unsafe_allow_html=True)

st.markdown("&nbsp;", unsafe_allow_html=True)

# ---------- PLAYBOOK ----------
actions = evaluate_playbook(prices, intel_data, equity_changes)
header = f"⚠  Triggered Playbook Actions  ({len(actions)} active)"
with st.expander(header, expanded=len(actions) > 0):
    if not actions:
        st.markdown(
            '<div class="alert-ok">● ALL THRESHOLDS NOMINAL — no '
            'playbook actions triggered. Continue routine monitoring.</div>',
            unsafe_allow_html=True,
        )
    else:
        for a in actions:
            css_class = "alert-critical" if a["level"] == "critical" else "alert-warn"
            tag = "CRITICAL" if a["level"] == "critical" else "ELEVATED"
            st.markdown(
                f'<div class="{css_class}"><b>[{tag}]  {a["trigger"]}</b><br>'
                f'<b>Business:</b> {a["business"]}<br>'
                f'<b>Household:</b> {a["household"]}</div>',
                unsafe_allow_html=True,
            )

# ---------- DEBUG / RAW INTEL ----------
if api_key and intel_meta.get("raw"):
    with st.expander("Raw Perplexity payload", expanded=False):
        st.code(intel_meta["raw"], language="json")

st.markdown("&nbsp;", unsafe_allow_html=True)
st.markdown(
    '<div class="status-strip" style="border-left-color:#374151;color:#6b7280;">'
    'Data: Yahoo Finance via yfinance for tickers (raw Close, no multipliers); '
    'Perplexity sonar-pro for logistics & inputs intel. Futures may be delayed '
    'up to 15 min. Intel values are LLM-retrieved; zero or negative numeric '
    'returns are treated as DATA UNAVAILABLE and excluded from the engine. '
    'Baseline reflects April 2026 pre-crisis reference levels. This dashboard '
    'is informational, not investment advice.</div>',
    unsafe_allow_html=True,
)
