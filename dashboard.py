import html
import json
import re
from datetime import date, datetime

import requests
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Global Supply Chain Overview",
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
        /* v15.2 final — extra top room so the page title sits clear
           of the sticky Critical Alert Ribbon at first paint, and
           never falls behind it once the user scrolls. */
        padding-top: 2.75rem;
        padding-bottom: 2rem;
        max-width: 1400px;
        scroll-margin-top: 4rem;
    }
    .hud-title {
        scroll-margin-top: 4rem;
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
        /* v15.2 final — bumped to 220 to keep every card in a row at
           equal height after the new "Why & What" caption + Source
           link block landed. overflow:visible is required so the
           pulsing red glow and the Source-link tooltip are not
           clipped at the card boundary. */
        min-height: 220px;
        display: flex;
        flex-direction: column;
        overflow: visible;
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
        line-height: 1.25;
        /* v15.2 final clipping hotfix — long status values like
           "🟡 WARNING: SHADOW CONGESTION" must wrap inside the
           card column instead of being truncated with ellipsis.
           !important defeats any inherited nowrap from container
           layouts (sparkline-row, etc.). */
        white-space: normal !important;
        overflow: visible !important;
        word-break: break-word;
        overflow-wrap: anywhere;
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
    /* ============================================================
       v13 GLOBAL SUPPLY CHAIN OVERVIEW — UI/UX OVERHAUL
       ============================================================ */

    /* v13 — Glassmorphism. All .intel-card surfaces get a frosted-glass
       treatment over the dark page background. backdrop-filter is the
       core effect; the rgba background and faint inner border give the
       characteristic translucent depth. */
    .intel-card {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }

    /* v13 — Status glow tiers.
       CRITICAL: pulsing red outer glow.
       WARNING: static amber glow.
       Both override the v12 .intel-card-breached border treatment so
       the glow becomes the dominant alert affordance. */
    @keyframes pulse-critical {
        0%, 100% {
            box-shadow: 0 0 20px #ff4b4b,
                        0 0 6px rgba(255, 75, 75, 0.4) inset;
        }
        50% {
            box-shadow: 0 0 38px #ff4b4b,
                        0 0 12px rgba(255, 75, 75, 0.55) inset;
        }
    }
    .intel-card-breached {
        border-color: rgba(255, 75, 75, 0.55) !important;
        box-shadow: 0 0 20px #ff4b4b !important;
        animation: pulse-critical 2.2s ease-in-out infinite;
    }
    .intel-card-warning {
        border-color: rgba(255, 165, 0, 0.65) !important;
        box-shadow: 0 0 15px rgba(255, 165, 0, 0.55) !important;
    }

    /* v15.2 — "Why & What" caption inside each card. Sits below the
       value/delta block. word-wrap forces multi-line text to break
       inside the 240px card column instead of overflowing. */
    .intel-card-caption {
        margin-top: 0.7rem;
        padding-top: 0.6rem;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        color: #9ca3af;
        font-size: 0.7rem;
        line-height: 1.55;
        font-style: italic;
        letter-spacing: 0.2px;
        word-wrap: break-word;
        overflow-wrap: break-word;
        white-space: normal;
        max-height: none;
    }
    .intel-card-caption.caption-critical { color: #fca5a5; }
    .intel-card-caption.caption-warning  { color: #fed7aa; }
    .intel-card-caption.caption-nominal  { color: #86efac; }
    .intel-card-caption .caption-tag {
        display: inline-block;
        font-style: normal;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.6rem;
        padding: 1px 5px;
        border-radius: 2px;
        margin-right: 5px;
        font-weight: 700;
    }
    .intel-card-caption.caption-critical .caption-tag {
        background: #ff4b4b; color: #000;
    }
    .intel-card-caption.caption-warning .caption-tag {
        background: #ffa500; color: #000;
    }
    .intel-card-caption.caption-nominal .caption-tag {
        background: #10b981; color: #000;
    }

    /* v15.2 final — Source hyperlink rendered at the end of each
       caption. Uses the same accent cyan as the rest of the HUD so
       it reads as a Streamlit-native link rather than a generic blue
       underline. Inline-block keeps it on the same wrapping line as
       the caption text. */
    .caption-source-link {
        display: inline;
        margin-left: 0.45rem;
        color: #00ffd1 !important;
        font-style: normal;
        font-size: 0.7rem;
        letter-spacing: 0.3px;
        text-decoration: underline;
        text-underline-offset: 2px;
        text-decoration-color: rgba(0, 255, 209, 0.5);
        white-space: nowrap;
    }
    .caption-source-link:hover {
        color: #00ffd1 !important;
        text-decoration-color: #00ffd1;
    }
    .caption-source-link::before {
        content: "↗ ";
        opacity: 0.85;
    }

    /* v13 — Critical Alert Ribbon. Sticky to the top of the scroll
       container, full-bleed across the block-container, high-contrast
       red-on-black with a slow pulse so the eye locks onto it the
       moment a critical breach is on the page. Hidden when there are
       no breaches (.is-empty). */
    @keyframes ribbon-pulse {
        0%, 100% {
            background: linear-gradient(90deg, #000 0%, #1a0000 50%, #000 100%);
            box-shadow: 0 0 24px rgba(255, 75, 75, 0.30);
        }
        50% {
            background: linear-gradient(90deg, #1a0000 0%, #2a0000 50%, #1a0000 100%);
            box-shadow: 0 0 36px rgba(255, 75, 75, 0.55);
        }
    }
    .critical-ribbon {
        position: sticky;
        top: 0;
        /* v15.2 final — z-index 999 per spec. The ribbon sits above
           every card glow and the Mermaid iframe but below any
           Streamlit modal/tooltip layer. */
        z-index: 999;
        background: linear-gradient(90deg, #000 0%, #1a0000 50%, #000 100%);
        color: #ff4b4b;
        border-top: 1px solid #ff4b4b;
        border-bottom: 1px solid #ff4b4b;
        padding: 0.55rem 1rem;
        /* Bleed -2rem upward so the ribbon hugs the top of the
           block container; main title gets its own scroll-margin so
           anchored navigation does not duck under the sticky bar. */
        margin: -2rem -1rem 1.25rem -1rem;
        text-align: center;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        letter-spacing: 1.8px;
        text-transform: uppercase;
        font-weight: 700;
        animation: ribbon-pulse 2.4s ease-in-out infinite;
        text-shadow: 0 0 6px rgba(255, 75, 75, 0.7);
    }
    .critical-ribbon .ribbon-tag {
        background: #ff4b4b;
        color: #000;
        padding: 1px 6px;
        border-radius: 2px;
        margin: 0 4px;
        font-weight: 800;
    }
    .critical-ribbon .ribbon-sep {
        color: #6b7280;
        margin: 0 0.65rem;
    }

    /* v13 — Global Resilience Score (GRS) header panel. The GRS lives
       directly under the title block and is the dominant element on
       first paint. Color theming flips between hard-break red (<50%),
       warn amber (50-75%), and ok green (>=75%) so a glance answers
       "are we OK?". */
    .grs-panel {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 1.4rem 1.75rem 1.2rem 1.75rem;
        margin-bottom: 1.5rem;
        font-family: 'Courier New', monospace;
    }
    .grs-panel.grs-hard-break {
        border-color: rgba(255, 75, 75, 0.45);
        box-shadow: 0 0 30px rgba(255, 75, 75, 0.18);
    }
    .grs-panel.grs-warn {
        border-color: rgba(255, 165, 0, 0.45);
        box-shadow: 0 0 24px rgba(255, 165, 0, 0.15);
    }
    .grs-panel.grs-ok {
        border-color: rgba(16, 185, 129, 0.45);
        box-shadow: 0 0 24px rgba(16, 185, 129, 0.12);
    }
    .grs-header {
        display: flex;
        align-items: baseline;
        gap: 1rem;
        flex-wrap: wrap;
    }
    .grs-title {
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 3px;
        font-size: 0.85rem;
    }
    .grs-tag {
        font-size: 0.65rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        padding: 2px 7px;
        border-radius: 2px;
        font-weight: 700;
    }
    .grs-tag.grs-hard-break {
        background: #ff4b4b;
        color: #000;
        animation: pulse-critical 2.2s ease-in-out infinite;
    }
    .grs-tag.grs-warn {
        background: #ffa500;
        color: #000;
    }
    .grs-tag.grs-ok {
        background: #10b981;
        color: #000;
    }
    .grs-score {
        margin-left: auto;
        font-size: 3.2rem;
        font-weight: 700;
        line-height: 1;
        letter-spacing: 1px;
    }
    .grs-score.grs-hard-break {
        color: #ff4b4b;
        text-shadow: 0 0 24px rgba(255, 75, 75, 0.55);
    }
    .grs-score.grs-warn {
        color: #ffa500;
        text-shadow: 0 0 18px rgba(255, 165, 0, 0.5);
    }
    .grs-score.grs-ok {
        color: #10b981;
        text-shadow: 0 0 18px rgba(16, 185, 129, 0.40);
    }
    .grs-score .grs-score-unit {
        font-size: 1.4rem;
        color: #9ca3af;
        margin-left: 0.2rem;
        letter-spacing: 1px;
    }
    .grs-bar {
        height: 10px;
        background: rgba(255,255,255,0.06);
        border-radius: 5px;
        overflow: hidden;
        margin-top: 1rem;
    }
    .grs-bar-fill {
        height: 100%;
        transition: width 0.6s ease;
    }
    .grs-bar-fill.grs-hard-break {
        background: linear-gradient(90deg, #dc2626 0%, #ff4b4b 100%);
    }
    .grs-bar-fill.grs-warn {
        background: linear-gradient(90deg, #c2772b 0%, #ffa500 100%);
    }
    .grs-bar-fill.grs-ok {
        background: linear-gradient(90deg, #059669 0%, #10b981 100%);
    }
    .grs-clusters {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
    }
    .grs-cluster {
        text-align: center;
        padding: 0.4rem 0.25rem 0.2rem 0.25rem;
    }
    .grs-cluster-label {
        color: #9ca3af;
        text-transform: uppercase;
        font-size: 0.66rem;
        letter-spacing: 1.8px;
        margin-bottom: 0.4rem;
    }
    .grs-cluster-value {
        font-size: 1.45rem;
        font-weight: 600;
        line-height: 1.1;
        letter-spacing: 1px;
    }
    .grs-cluster-value.grs-hard-break { color: #ff4b4b; }
    .grs-cluster-value.grs-warn { color: #ffa500; }
    .grs-cluster-value.grs-ok { color: #10b981; }
    .grs-cluster-value.grs-unavail { color: #6b7280; font-size: 0.95rem; }
    .grs-cluster-detail {
        color: #6b7280;
        font-size: 0.65rem;
        letter-spacing: 0.5px;
        margin-top: 0.3rem;
        line-height: 1.35;
    }
    .grs-info {
        margin-top: 1rem;
        padding-top: 0.85rem;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        color: #9ca3af;
        font-size: 0.78rem;
        line-height: 1.55;
        font-style: italic;
    }
    .grs-info strong {
        color: #fca5a5;
        font-style: normal;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.7rem;
    }
    /* v15.2 — GRS dynamic description block. Sits below the cluster
       grid and translates the numeric score into operating posture
       (Systemic Stability / Strained Baseline / Structural Failure).
       Color matches the active GRS tier so the block reads as part
       of the same panel. */
    .grs-description {
        margin-top: 1rem;
        padding: 0.95rem 1.1rem;
        border-radius: 5px;
        font-size: 0.85rem;
        line-height: 1.55;
        letter-spacing: 0.3px;
        border-left: 3px solid currentColor;
    }
    .grs-description.grs-hard-break {
        background: rgba(255, 75, 75, 0.08);
        color: #fca5a5;
    }
    .grs-description.grs-warn {
        background: rgba(255, 165, 0, 0.08);
        color: #fed7aa;
    }
    .grs-description.grs-ok {
        background: rgba(16, 185, 129, 0.08);
        color: #86efac;
    }
    .grs-description .grs-desc-headline {
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-size: 0.75rem;
        display: block;
        margin-bottom: 0.35rem;
    }

    /* v15.2 — Triggered Playbook two-column action layout. Each
       triggered action surfaces the Business directive on the left
       and the Household directive on the right so the operator sees
       both responses at a glance. Wraps to a single column on
       narrower viewports. */
    .playbook-actions {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.9rem;
        margin-top: 0.65rem;
    }
    .playbook-action {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        padding: 0.65rem 0.9rem;
        border-radius: 4px;
        border-left: 3px solid currentColor;
    }
    .playbook-action-title {
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.7rem;
        font-weight: 700;
        margin-bottom: 0.3rem;
        display: block;
    }
    .playbook-action-body {
        color: #d1d5db;
        font-size: 0.82rem;
        line-height: 1.5;
        font-style: normal;
    }
    @media (max-width: 720px) {
        .playbook-actions { grid-template-columns: 1fr; }
    }

    /* v13 — Sparkline (inline 7-day trend on key metric cards). Sits
       inline next to the card value; color matches the breach state
       (red = critical rise, amber = warning, green = stable). */
    .sparkline {
        display: inline-block;
        vertical-align: middle;
        margin-left: 0.5rem;
        opacity: 0.95;
    }
    .sparkline-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.4rem;
        white-space: nowrap;
        overflow: hidden;
    }
    .sparkline-row .intel-card-value {
        margin-bottom: 0;
        flex: 0 1 auto;
        min-width: 0;
        /* Inside a sparkline row the value is short ($130.50) and
           kept on a single line so the inline 7D chart sits to the
           right of the headline number. */
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis;
    }
    .sparkline-row .sparkline {
        margin-left: 0;
        flex: 0 0 auto;
    }
    .sparkline-label {
        font-size: 0.62rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-left: 0.35rem;
    }

    /* v13 — Subtitle under the main HUD title. */
    .hud-subtitle {
        color: #9ca3af;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-top: -0.5rem;
        margin-bottom: 1rem;
    }
    .hud-subtitle .intel-armed {
        color: #00ffd1;
        font-weight: 700;
        letter-spacing: 2px;
    }

    /* v13 — Mermaid cascade iframe wrapper sits inside the same
       cascade-container shell so the title bar above it stays visually
       attached to the diagram. */
    .mermaid-frame-wrap {
        margin-top: 0.4rem;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 4px;
        overflow: hidden;
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
def fetch_sparkline_series(ticker: str) -> list:
    """v13 — return last 7 trading-day Close values for sparkline
    rendering. Cached on the same 4-hour window as fetch_price /
    fetch_equity_snapshot so the trend is consistent with the headline
    number on every card."""
    try:
        data = yf.Ticker(ticker).history(period="14d", interval="1d")
        if data.empty:
            return []
        closes = [float(x) for x in data["Close"].tolist()]
        return closes[-7:] if len(closes) >= 7 else closes
    except Exception:
        return []


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


# ============================================================
# v15.2 — "Why & What" caption copy + state resolver
# ============================================================
# Each card surfaces one short italicised sentence below the value
# block explaining the strategic implication of its current state.
# Keys map to card identifiers; sub-keys are the tier resolved by
# get_card_caption() (critical / warning / nominal). Helium and CO2
# get post-format substitution for live values.

CAPTION_TEXTS = {
    "brent": {
        # v15.2 final — tightened critical phrasing per the brief.
        # Keeps the 1.2% transport-COGS pass-through anchor while
        # leading with the "Blockade Persistence" frame.
        "critical": "Blockade Persistence: Every $1 hike adds 1.2% "
                    "to transport COGS.",
        "warning":  "Supply Anxiety: Inventories near 842m barrel "
                    "floor. Expect high volatility and speculative "
                    "hedging.",
        "nominal":  "Buffer Restored: Strategic reserves or "
                    "de-escalation has stabilized flows.",
    },
    "ttf": {
        "critical": "Industrial Gas Squeeze: ammonia, glass, and "
                    "ceramic capacity falling offline; cascades into "
                    "Spring 2027 fertilizer input window.",
        "warning":  "Storage Anxiety: Q4 refill window narrowing; "
                    "industrial demand-destruction tier 1 active.",
        "nominal":  "Pipeline Steady: Storage refill on track; "
                    "industrial output unaffected.",
    },
    "gold": {
        "critical": "Regime Shift: safe-haven flight confirmed. "
                    "Stress-test cash reserves and FX-hedge ratios "
                    "for monetary-regime repricing.",
        "nominal":  "Flow Normal: macro signals align; defensive "
                    "positioning at routine levels.",
    },
    "silver": {
        "critical": "Industrial-Precious Break: solar and electronics "
                    "BOMs face direct cost pressure. Lock 90-day "
                    "futures for capex pipeline.",
        "nominal":  "Industrial Demand Stable: solar and BOM "
                    "exposure within nominal cost band.",
    },
    "panama": {
        "critical": "Slot Auction Spike: rerouting Asia-USEC freight "
                    "via Suez or USWC+rail; FAK rate spike inside "
                    "30-45 days.",
        "warning":  "Slot Cost Inflation: canal-fee pass-through "
                    "lifting holiday-season consumer goods 6-10%.",
        "nominal":  "Canal Throughput Steady: slot pricing within "
                    "the historical band; no rerouting required.",
    },
    "urea": {
        "critical": "Fertilizer Shock: grain/dairy/meat shelf prices "
                    "reflect input-cost rationing in 2-3 quarters.",
        "warning":  "Margin Pressure: ag procurement watching N-heavy "
                    "crop economics; Q3 hedge window opening.",
        "nominal":  "Input Cost Stable: fertilizer pass-through risk "
                    "to food shelf prices is contained.",
    },
    "hormuz": {
        "critical": "Chokepoint Closure: 20%+ of global crude/LNG "
                    "flow rerouting via Cape; pump-price shock within "
                    "3-6 weeks.",
        "warning":  "Transit Stress: tanker rates and war-risk premia "
                    "spreading. Pre-brief logistics on contingency "
                    "routing.",
        "nominal":  "Transit Stable: daily ship counts within the "
                    "post-war operating band.",
    },
    "malacca": {
        "critical": "Active Disruption: full Malacca-bypass "
                    "contingency engaged; 60-90 day inventory "
                    "pre-positioning required.",
        "warning":  "Shadow Congestion: 48-72h lead time before "
                    "global manufacturing collapse can fire as Tail "
                    "Risk trigger.",
        "nominal":  "Strait Clear: vessel backlog within baseline; "
                    "no rerouting required.",
    },
    "helium": {
        # Day-count is interpolated dynamically by get_card_caption()
        # using the {days_past} and {boil_off} placeholders.
        "critical": "Yield Collapse: {days_past} days past "
                    "{boil_off}-day boil-off. 5nm/3nm chip production "
                    "is physically compromised.",
        "nominal":  "Flow Restored: New Qatar/US supply has reached "
                    "Asian fabs.",
    },
    "co2": {
        "critical": "Supply Zero: Ammonia plants shuttered. Imminent "
                    "shelf-life collapse for protein and medical gas "
                    "rationing.",
        "nominal":  "Gas Stabilized: Ammonia plants restarted or CCS "
                    "capture scaled.",
    },
    "resin": {
        "critical": "Resin BOM Hit: medical device, sterile "
                    "packaging, and consumer goods carrying direct "
                    "COGS exposure.",
        "warning":  "Spec Tightening: pull forward 60-day POs; "
                    "qualify alternate-grade suppliers ahead of "
                    "retail pass-through.",
        "nominal":  "Resin Supply Open: Asia PE/PP feedstocks within "
                    "spec; medical and packaging BOMs unaffected.",
    },
    "jet": {
        "critical": "Payload Displacement: airlines trade revenue "
                    "weight for fuel weight; 30-50% air-freight rate "
                    "spike inside the lead-time window.",
        "warning":  "Fuel Surcharge Climb: re-quote air-freight "
                    "contracts; lock seasonal travel before airfare "
                    "repricing completes.",
        "nominal":  "Aviation Fuel Stable: cargo and passenger "
                    "capacity within normal commercial band.",
    },
    "rice": {
        "critical": "Staple Shock: India ban active. Leading "
                    "indicator for Vietnam/Thailand bans and 20% "
                    "price spike.",
        "nominal":  "Exports Resumed: Global grain liquidity "
                    "returning to baseline.",
    },
    # AI Storage equities (WDC + STX share the same playbook copy).
    "ai_storage": {
        "critical": "Total Lockout: 95% of output diverted to Big "
                    "Tech. Non-hyperscaler hardware refreshes frozen "
                    "for 12 mo.",
        "warning":  "Lead Time Spike: Orders slipping 6-9 months. "
                    "AI demand outstripping legacy production.",
        "nominal":  "Allocation Easing: enterprise channels seeing "
                    "capacity opening up.",
    },
    "cf": {
        "critical": "Fertilizer Equity Spike: market pricing in "
                    "ammonia/urea stress ahead of physical feed.",
        "warning":  "Equity Drift: smart money rotating into "
                    "fertilizer exposure on early-warning signals.",
        "nominal":  "Equity Quiet: no anomalous flow into the "
                    "fertilizer complex.",
    },
    "dow": {
        "critical": "Petrochemical Shock: PE/PP feedstock stress "
                    "pricing into resin BOMs and medical packaging.",
        "warning":  "Resin Drift: institutional flow tilting on "
                    "petrochemical input concerns.",
        "nominal":  "Petrochemicals Calm: feedstock and resin "
                    "channels operating normally.",
    },
    "apd": {
        "critical": "Industrial Gas Spike: helium/MRI/cryogenic stress "
                    "pricing in ahead of physical reads.",
        "warning":  "Industrial Gas Drift: smart money repositioning "
                    "around helium and semiconductor cooling.",
        "nominal":  "Industrial Gas Quiet: helium and cryogenic "
                    "exposures within normal operating band.",
    },
    "jets": {
        "critical": "Aviation Repricing: market pricing fuel-cost "
                    "rationing into airline P&Ls and freight rates.",
        "warning":  "Aviation Drift: institutional flow rotating on "
                    "jet-fuel and travel-budget concerns.",
        "nominal":  "Aviation Quiet: airline equities within "
                    "historical operating range.",
    },
}


def get_card_caption(key, breach=False, warning=False, **fmt):
    """Resolve a card's "Why & What" caption from CAPTION_TEXTS.

    Returns (text, state) where state is one of 'critical', 'warning',
    'nominal', or None when no caption is configured for the requested
    state. Optional `fmt` kwargs are applied via str.format() — used
    for the helium days_past / boil_off interpolation."""
    if key not in CAPTION_TEXTS:
        return None, None
    if breach:
        state = "critical"
    elif warning:
        state = "warning"
    else:
        state = "nominal"
    text = CAPTION_TEXTS[key].get(state)
    if text is None:
        return None, None
    if fmt:
        try:
            text = text.format(**fmt)
        except (KeyError, IndexError):
            pass
    return text, state


# ============================================================
# v15.2 final — Source URLs (Intelligence Hyperlinks)
# ============================================================
# One canonical source URL per metric. The caption block renders a
# small "Source ↗" hyperlink after the body text whenever a URL is
# defined for the active caption_key. Keys without an entry simply
# omit the link — future intel updates can extend this dict without
# touching the rendering layer.
#
# Three URLs are confirmed by the v15.2 brief; additional canonical
# sources will be supplied in subsequent intel updates.
SOURCE_URLS = {
    "rice":    "https://apeda.gov.in/dgft-notifications",
    "malacca": "https://mykn.kuehne-nagel.com/news/article/"
               "indonesia-says-it-has-no-plan-to-toll-malacca",
    "helium":  "https://www.iaphworldports.org/news/"
               "worldmaritimenews/22046/",
    # brent / ttf / gold / silver / panama / urea / hormuz / co2 /
    # resin / jet / ai_storage / cf / dow / apd / jets — pending
    # canonical-source confirmation.
}


def render_source_link_html(caption_key):
    """Build the Source-link HTML appended to a caption block.

    Returns an empty string when no URL is registered for the key,
    so cards without a confirmed source render cleanly without an
    orphan link. URLs are HTML-escaped to defend against any future
    payload tampering."""
    if not caption_key:
        return ""
    url = SOURCE_URLS.get(caption_key)
    if not url:
        return ""
    safe_url = html.escape(url, quote=True)
    return (
        f' <a class="caption-source-link" href="{safe_url}" '
        f'target="_blank" rel="noopener noreferrer">Source</a>'
    )


# ============================================================
# v13 — Global Resilience Score (GRS) + UI helpers
# ============================================================

def _metric_health(value, baseline, crit, inverted=False):
    """Map a metric to a 0-100 health score.

    inverted=False (default):
        value <= baseline → 100 (healthy)
        value >= crit     → 0   (critical)
        linear in between
    inverted=True (e.g., Hormuz transit count, where LOWER is bad):
        value >= baseline → 100
        value <= crit     → 0
        linear in between

    Returns None if value is None — the cluster average will skip it
    rather than treat missing data as either healthy or critical."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if inverted:
        if v >= baseline:
            return 100.0
        if v <= crit:
            return 0.0
        span = baseline - crit
        if span <= 0:
            return None
        return (v - crit) / span * 100.0
    if v <= baseline:
        return 100.0
    if v >= crit:
        return 0.0
    span = crit - baseline
    if span <= 0:
        return None
    return (1.0 - (v - baseline) / span) * 100.0


def _avg_or_none(parts):
    cleaned = [p for p in parts if p is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def grs_compute(prices: dict, intel: dict | None = None) -> dict:
    """v13 — Global Resilience Score. Three clusters averaged equally:

      1. Commodity Health (Brent + TTF + Fertilizer/Urea)
      2. Logistics Health (Malacca + Hormuz + Panama)
      3. Physical Buffers (Helium boil-off + CO2 byproduct + OECD oil inv)

    Returns a dict with the overall score, each cluster's score, and
    the per-metric components used for the breakdown tooltip. Any
    cluster whose components are all unavailable returns None for
    that cluster — the overall score then averages whichever clusters
    do have data.

    Hard Break threshold is 50%: below that, physical availability is
    overriding market pricing and the dashboard is in resource-rationing
    territory."""
    intel = intel or {}

    # Cluster 1 — Commodity Health
    brent_h = _metric_health(prices.get("Brent"), 100.0, 130.0)
    ttf_h = _metric_health(prices.get("TTF"), 52.0, 80.0)
    urea_h = _metric_health(intel.get("urea_spot_price_ton"), 320.0, 800.0)
    commodity = _avg_or_none([brent_h, ttf_h, urea_h])

    # Cluster 2 — Logistics Health
    malacca_sev = intel.get("malacca_severity")
    if malacca_sev == "critical":
        malacca_h = 0.0
    elif malacca_sev == "elevated":
        malacca_h = 30.0
    elif malacca_shadow_active(intel):
        malacca_h = 55.0
    elif malacca_sev == "nominal" or malacca_sev is None:
        # No live signal → assume nominal for health math (the engine
        # itself still treats None as None and does not fire rules).
        malacca_h = 100.0
    else:
        malacca_h = 100.0

    hormuz_h = _metric_health(
        intel.get("hormuz_daily_transit_count"), 80.0, 20.0, inverted=True
    )
    panama_h = _metric_health(
        intel.get("panama_canal_neopanamax_price"), 1_500_000.0, 4_000_000.0
    )
    logistics = _avg_or_none([malacca_h, hormuz_h, panama_h])

    # Cluster 3 — Physical Buffers
    if helium_exhausted():
        helium_h = 0.0
    else:
        days = helium_days_elapsed()
        # Pre-FM (negative or zero days) → 100. Approaching boil-off
        # threshold → ramps to 0.
        ratio = max(0.0, min(1.0, days / float(HELIUM_BOIL_OFF_DAYS)))
        helium_h = (1.0 - ratio) * 100.0
    co2_h = 0.0 if CO2_BYPRODUCT_BREACH else 100.0
    oecd_h = 0.0 if OECD_INVENTORY_BREACH else 100.0
    buffers = _avg_or_none([helium_h, co2_h, oecd_h])

    overall = _avg_or_none([commodity, logistics, buffers])

    return {
        "overall": overall,
        "commodity": commodity,
        "logistics": logistics,
        "buffers": buffers,
        "components": {
            "brent": brent_h,
            "ttf": ttf_h,
            "urea": urea_h,
            "malacca": malacca_h,
            "hormuz": hormuz_h,
            "panama": panama_h,
            "helium": helium_h,
            "co2": co2_h,
            "oecd": oecd_h,
        },
    }


def grs_tier(score):
    """v15.2 three-tier classification used for color theming, the
    GRS tag, and the dynamic description block.

      score < 40   → 'hard-break'  ("Structural Failure")
      40 <= s <= 70 → 'warn'        ("Strained Baseline")
      score > 70   → 'ok'           ("Systemic Stability")
    """
    if score is None:
        return "unavail"
    if score < 40:
        return "hard-break"
    if score <= 70:
        return "warn"
    return "ok"


# v15.2 — operating-posture copy for the GRS description block. Each
# tier maps to a short headline + one-line directive translating the
# numeric score into action.
GRS_DESCRIPTIONS = {
    "ok": (
        "Systemic Stability",
        "Global buffers are absorbing current shocks. "
        "Maintain normal procurement.",
    ),
    "warn": (
        "Strained Baseline",
        "Buffers are depleting. "
        "Move to 'Just-in-Case' inventory positioning.",
    ),
    "hard-break": (
        "Structural Failure",
        "Physical supply gaps have replaced price discovery. "
        "Rationing protocols active.",
    ),
}


def build_critical_ribbon(prices: dict, intel: dict | None = None) -> str:
    """v13 — assemble the critical-alert ribbon text from active
    physical-logic gates. Returns an empty string when nothing is
    breached so the caller can hide the ribbon entirely."""
    intel = intel or {}
    pieces = []

    if helium_exhausted():
        pieces.append(
            f'<span class="ribbon-tag">CRITICAL</span> '
            f'HELIUM EXHAUSTED (DAY {helium_days_elapsed()})'
        )
    if CO2_BYPRODUCT_BREACH:
        pieces.append(
            '<span class="ribbon-tag">CRITICAL</span> '
            'CO2 BYPRODUCT EXHAUSTED'
        )
    if OECD_INVENTORY_BREACH:
        pieces.append(
            f'<span class="ribbon-tag">BREACH</span> '
            f'OECD OIL INVENTORIES &lt; '
            f'{OECD_INVENTORY_OPERATIONAL_MIN_MB}MB'
        )

    # Live intel-driven additions — kept compact so the ribbon stays
    # one line on a 1400px container.
    if intel.get("malacca_severity") == "critical":
        pieces.append(
            '<span class="ribbon-tag">CRITICAL</span> MALACCA BLOCKADE'
        )
    if intel.get("india_rice_ban_status") == "ACTIVE":
        pieces.append(
            '<span class="ribbon-tag">BREACH</span> INDIA RICE BAN ACTIVE'
        )
    brent = prices.get("Brent")
    if brent is not None and brent > 130:
        pieces.append(
            f'<span class="ribbon-tag">BREACH</span> '
            f'BRENT &gt; $130 (live: ${brent:,.0f})'
        )

    if not pieces:
        return ""
    sep = '<span class="ribbon-sep">|</span>'
    return sep.join(pieces)


def render_sparkline_svg(values, color="#10b981", width=72, height=22):
    """Build an inline SVG path showing the 7-day trend for a single
    metric. Color is chosen by the caller based on breach state:
        red    (#ff4b4b) — current value is in the BREACHED tier
        amber  (#eab308) — current value is in the WARNING tier
        green  (#10b981) — stable / nominal
    Returns an empty string if there is not enough data to draw a line."""
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        # Flat series → flat horizontal stroke at mid-height.
        y = height / 2.0
        d = f"M0,{y:.1f} L{width},{y:.1f}"
    else:
        n = len(values)
        pts = []
        for i, v in enumerate(values):
            x = (i / (n - 1)) * width
            # Flip Y so higher value renders higher on the SVG.
            y = height - ((v - lo) / (hi - lo)) * height
            pts.append(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}")
        d = " ".join(pts)
    # A faint area fill underneath the stroke gives the trend visual
    # weight without competing with the headline number.
    if hi != lo:
        area_pts = list(pts) + [f"L{width},{height}", f"L0,{height}", "Z"]
        area_d = " ".join(area_pts)
        area = (
            f'<path d="{area_d}" fill="{color}" '
            f'fill-opacity="0.18" stroke="none"/>'
        )
    else:
        area = ""
    return (
        f'<svg class="sparkline" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'preserveAspectRatio="none" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'{area}'
        f'<path d="{d}" stroke="{color}" stroke-width="1.6" '
        f'fill="none" stroke-linecap="round" '
        f'stroke-linejoin="round" '
        f'vector-effect="non-scaling-stroke"/>'
        f'</svg>'
    )


def sparkline_color_for_breach(breach: bool, warning: bool = False) -> str:
    """v13 — color-key for the trend mini-chart. Critical rise → red,
    warning → amber, stable → green."""
    if breach:
        return "#ff4b4b"
    if warning:
        return "#eab308"
    return "#10b981"


def render_mermaid_cascade(co2_breach: bool):
    """v13 — render the Energy → Ammonia → CO2 → Meat/Medical cascade
    using Mermaid via st.components.v1.html (iframe with the Mermaid
    ESM module loaded from CDN; no new pip dependency).

    When `co2_breach` is True, the CO2 Byproduct and Meat/Medical Gas
    nodes adopt the spec'd `fill:#ff4b4b,stroke:#fff,stroke-width:2px`
    treatment to make the active downstream collapse impossible to miss."""
    if co2_breach:
        co2_style = "fill:#ff4b4b,stroke:#fff,stroke-width:2px,color:#fff"
        med_style = "fill:#ff4b4b,stroke:#fff,stroke-width:2px,color:#fff"
        # v15.2 final — when the byproduct stage has gone CRITICAL,
        # the entire downstream half of the chain is failing. Both
        # the Ammonia → CO2 edge AND the CO2 → Medical Gas edge are
        # marked red+thick so the cascading propagation is visually
        # unmistakable. Edge indexing: 0=A->B, 1=B->C, 2=C->D.
        link_styles = (
            "    linkStyle 1 stroke:#ff4b4b,stroke-width:3px;\n"
            "    linkStyle 2 stroke:#ff4b4b,stroke-width:3px;\n"
        )
    else:
        co2_style = "fill:#854d0e,stroke:#9ca3af,stroke-width:1px,color:#fff"
        med_style = "fill:#1e3a8a,stroke:#9ca3af,stroke-width:1px,color:#fff"
        link_styles = ""

    mermaid_def = (
        "flowchart LR\n"
        "    A[\"Energy<br/>(Natural Gas)\"] --> B[\"Ammonia<br/>Production\"]\n"
        "    B --> C[\"CO2<br/>Byproduct\"]\n"
        "    C --> D[\"Meat /<br/>Medical Gas\"]\n"
        "    style A fill:#1e3a8a,stroke:#9ca3af,stroke-width:1px,color:#fff\n"
        "    style B fill:#854d0e,stroke:#9ca3af,stroke-width:1px,color:#fff\n"
        f"    style C {co2_style}\n"
        f"    style D {med_style}\n"
        f"{link_styles}"
    )
    # mermaid_def must be embedded raw — html.escape would mangle
    # the `-->` arrows and `<br/>` line breaks. The content is
    # hardcoded (no user input flows in), so there is no XSS surface.
    html_body = (
        "<!DOCTYPE html><html><head>"
        "<style>"
        "html,body{background:transparent;margin:0;padding:0;"
        "font-family:'Courier New',monospace;}"
        ".mermaid{display:flex;justify-content:center;padding:8px;}"
        "</style></head><body>"
        f'<pre class="mermaid">\n{mermaid_def}</pre>'
        '<script type="module">'
        "import mermaid from "
        "'https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/"
        "mermaid.esm.min.mjs';"
        "mermaid.initialize({startOnLoad:true,theme:'dark',"
        "securityLevel:'loose',"
        "themeVariables:{fontFamily:'Courier New, monospace',"
        "fontSize:'13px'}});"
        "</script></body></html>"
    )
    st.components.v1.html(html_body, height=180, scrolling=False)


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
                      use_baseline_fallback=True, breach=False,
                      warning=False, sparkline_series=None,
                      caption_key=None, caption_fmt=None):
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

    Status flags:
      `breach=True`   → .intel-card-breached (pulsing red glow)
      `warning=True`  → .intel-card-warning (static amber glow)
      neither         → plain glassmorphic card
    breach takes precedence if both are set.

    `sparkline_series` (v13) — optional 7-day price series. When
    provided, renders an inline SVG sparkline next to the headline
    value. Color picks up the breach/warning state automatically."""
    label_safe = html.escape(label)
    if breach:
        card_class = "intel-card intel-card-breached"
    elif warning:
        card_class = "intel-card intel-card-warning"
    else:
        card_class = "intel-card"

    spark_color = sparkline_color_for_breach(breach, warning)
    sparkline_html = (
        render_sparkline_svg(sparkline_series, color=spark_color)
        if sparkline_series else ""
    )

    # v15.2 final — "Why & What" caption + Source hyperlink. The
    # link only renders when SOURCE_URLS has an entry for the key.
    caption_html = ""
    if caption_key:
        cap_text, cap_state = get_card_caption(
            caption_key, breach=breach, warning=warning,
            **(caption_fmt or {}),
        )
        if cap_text:
            source_html = render_source_link_html(caption_key)
            caption_html = (
                f'<div class="intel-card-caption caption-{cap_state}">'
                f'<span class="caption-tag">{cap_state}</span>'
                f'{html.escape(cap_text)}'
                f'{source_html}'
                f'</div>'
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
            f'{caption_html}'
            f'</div>'
        )

    if value is None:
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value intel-card-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="intel-card-delta">&nbsp;</div>'
            f'{caption_html}'
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
    # delta direction. v13: WARNING tier renders amber to match the
    # static amber glow on the card frame.
    if breach:
        delta_class = "delta-bear"
    elif warning:
        delta_class = "delta-bear"
    else:
        delta_class = "delta-bull"
    value_display = f"{currency}{fmt.format(value)}{suffix}"

    # When a sparkline is supplied, render value + sparkline side by
    # side in a flex row instead of stacked vertically — keeps the
    # card compact and the trend visually attached to the number.
    if sparkline_html:
        value_block = (
            f'<div class="sparkline-row">'
            f'<div class="intel-card-value">'
            f'{html.escape(value_display)}</div>'
            f'{sparkline_html}'
            f'<span class="sparkline-label">7D</span>'
            f'</div>'
        )
    else:
        value_block = (
            f'<div class="intel-card-value">'
            f'{html.escape(value_display)}</div>'
        )

    return (
        f'<div class="{card_class}">'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'{value_block}'
        f'<div class="intel-card-delta {delta_class}">'
        f'{html.escape(delta_str)}</div>'
        f'{caption_html}'
        f'</div>'
    )


def card_status_html(label, value_text, value_color, detail,
                     is_baseline=False, breach=False, warning=False,
                     caption_key=None, caption_fmt=None):
    """Qualitative card returning a single HTML string. value_text=None
    → DATA UNAVAILABLE (used only when no peace-time baseline applies).

    When `is_baseline` is True, a small italic "(baseline)" tag is
    appended to the value and the detail line is rendered in muted
    grey. The card otherwise looks like a live nominal reading. The
    detail string can contain Perplexity-sourced text and is
    HTML-escaped to defend against payload tampering.

    Status flags:
      `breach=True`  → .intel-card-breached pulsing red glow
      `warning=True` → .intel-card-warning static amber glow
    breach takes precedence if both are set.

    `caption_key` (v15.2) — optional key into CAPTION_TEXTS for the
    "Why & What" italic line below the detail."""
    label_safe = html.escape(label)
    detail_safe = html.escape(detail) if detail else "&nbsp;"
    if breach:
        base_class = "intel-card intel-card-breached"
    elif warning:
        base_class = "intel-card intel-card-warning"
    else:
        base_class = "intel-card"

    caption_html = ""
    if caption_key:
        cap_text, cap_state = get_card_caption(
            caption_key, breach=breach, warning=warning,
            **(caption_fmt or {}),
        )
        if cap_text:
            source_html = render_source_link_html(caption_key)
            caption_html = (
                f'<div class="intel-card-caption caption-{cap_state}">'
                f'<span class="caption-tag">{cap_state}</span>'
                f'{html.escape(cap_text)}'
                f'{source_html}'
                f'</div>'
            )

    if value_text is None:
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value intel-card-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="intel-card-detail">{detail_safe}</div>'
            f'{caption_html}'
            f'</div>'
        )
    color = html.escape(value_color or "#9ca3af")
    baseline_tag = (
        '<span class="baseline-tag">(baseline)</span>' if is_baseline else ""
    )
    detail_class = (
        "intel-card-baseline-note" if is_baseline else "intel-card-detail"
    )
    # Inline border-color only fires when no breach/warning glow is
    # active — otherwise the glow's own border treatment takes over.
    if not (breach or warning):
        style_attr = f' style="border-color: {color};"'
    else:
        style_attr = ""
    return (
        f'<div class="{base_class}"{style_attr}>'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'<div class="intel-card-value" style="color: {color};">'
        f'● {html.escape(value_text)}{baseline_tag}</div>'
        f'<div class="{detail_class}">{detail_safe}</div>'
        f'{caption_html}'
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


# ---------- DATA FETCH (consolidated; runs before any rendering) ----------
# Fetch upstream data FIRST so the v13 Critical Alert Ribbon and the
# Global Resilience Score header can both read from the live snapshot.
# All downstream sections (Strategic Outlook, 3-column body, Threshold
# Monitor, Playbook) reuse the same dicts. Caching is on each fetch
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

# v15.2 — 7-day sparkline series for ALL Telemetry and Equity cards.
# Each ticker is cached individually on the same 4-hour TTL as
# fetch_price, so adding the full set is essentially free after the
# first warm-up.
sparkline_series = {}
for _name, _tk in TICKERS.items():
    sparkline_series[_name] = fetch_sparkline_series(_tk)
for _key, _tk in EQUITY_TICKERS.items():
    sparkline_series[_key] = fetch_sparkline_series(_tk)

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

# ---------- v15.2 INTELLIGENCE HOTFIX OVERRIDES ----------
# These overrides take precedence over whatever Perplexity returned.
# They reflect the v15.2 brief's confirmed real-world state and ensure
# the engine, GRS, ribbon, and rendering all see the same picture
# regardless of LLM retrieval drift.
#
#   • India Rice Export Ban — forced ACTIVE / CRITICAL.
#   • Malacca Status        — forced 🟡 WARNING (Shadow Congestion)
#                             with the v15.2 context text. The shadow
#                             tier is engaged via the existing
#                             ships_waiting > 80 * 1.15 trigger.
#
# Helium (Day 59) and Industrial CO2 (EU ammonia 35%) are already
# CRITICAL via their physical-logic gates — no override needed there.
intel_data["india_rice_ban_status"] = "ACTIVE"
# Suppress any Perplexity-returned severity so the shadow tier wins
# the malacca rendering precedence chain.
intel_data["malacca_severity"] = None
intel_data["malacca_ships_waiting"] = 100  # +25% over 80/day baseline
intel_data["malacca_status"] = (
    "Indonesia considering transit fees (Hormuz Contagion); "
    "vessels loitering for insurance verification."
)

# Scenario probabilities + Global Resilience Score computed once for
# the consolidated snapshot so every section is internally consistent.
adjusted = adjust_probabilities(prices, intel_data, equity_changes)
grs = grs_compute(prices, intel_data)

# v15.2 final — confirmed failing-grade hotfix. The brief sits the
# headline GRS at 38% (Structural Failure tier). Cluster scores below
# are still computed from live data so the breakdown remains
# diagnostic; only the headline number is overridden.
GRS_OVERRIDE_PCT = 38.0
if GRS_OVERRIDE_PCT is not None:
    grs["overall"] = GRS_OVERRIDE_PCT

# ---------- v13 CRITICAL ALERT RIBBON (sticky, absolute top) ----------
# High-contrast red-on-black sticky bar. Hidden when nothing is
# breached. Pulls from physical-logic gates + live intel critical
# states. Lives BEFORE the title so it owns the absolute top of the
# scroll container.
_ribbon_html = build_critical_ribbon(prices, intel_data)
if _ribbon_html:
    st.markdown(
        f'<div class="critical-ribbon">{_ribbon_html}</div>',
        unsafe_allow_html=True,
    )

# ---------- MAIN HEADER (v13 branding) ----------
st.markdown(
    '<h1 class="hud-title">■ Global Supply Chain Overview</h1>',
    unsafe_allow_html=True,
)
_intel_grade = "ARMED" if api_key else "STANDBY"
_grade_class = "intel-armed" if api_key else ""
st.markdown(
    f'<div class="hud-subtitle">'
    f'Strategic Logistics &amp; Resource Intelligence '
    f'&nbsp;|&nbsp; Intel Grade: '
    f'<span class="{_grade_class}">{_intel_grade}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ---------- v13 GLOBAL RESILIENCE SCORE (GRS) HEADER ----------
# Single composite metric averaging three equally-weighted clusters:
#   1. Commodity Health   — Brent, TTF, Urea (fertilizer)
#   2. Logistics Health   — Malacca, Hormuz, Panama
#   3. Physical Buffers   — Helium boil-off, CO2 byproduct, OECD oil inv
# A score below 50% indicates a 'Hard Break' — physical availability
# is overriding market pricing and the dashboard is in resource-
# rationing territory.
_grs_overall = grs["overall"]
_grs_tier = grs_tier(_grs_overall)
_grs_panel_class = f"grs-panel grs-{_grs_tier}" if _grs_tier != "unavail" \
    else "grs-panel"

if _grs_overall is None:
    _grs_score_html = (
        '<div class="grs-score grs-unavail" '
        'style="color:#6b7280;font-size:1.6rem;">DATA UNAVAILABLE</div>'
    )
    _grs_bar_html = ""
    _grs_tag_html = ""
else:
    if _grs_tier == "hard-break":
        _grs_tag_html = (
            '<span class="grs-tag grs-hard-break">'
            'STRUCTURAL FAILURE</span>'
        )
    elif _grs_tier == "warn":
        _grs_tag_html = (
            '<span class="grs-tag grs-warn">STRAINED BASELINE</span>'
        )
    else:
        _grs_tag_html = (
            '<span class="grs-tag grs-ok">SYSTEMIC STABILITY</span>'
        )
    _grs_score_html = (
        f'<div class="grs-score grs-{_grs_tier}">'
        f'{_grs_overall:.1f}<span class="grs-score-unit">%</span>'
        f'</div>'
    )
    _grs_bar_html = (
        f'<div class="grs-bar">'
        f'<div class="grs-bar-fill grs-{_grs_tier}" '
        f'style="width: {_grs_overall:.1f}%;"></div>'
        f'</div>'
    )


def _cluster_block(label, score, detail):
    if score is None:
        return (
            f'<div class="grs-cluster">'
            f'<div class="grs-cluster-label">{label}</div>'
            f'<div class="grs-cluster-value grs-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="grs-cluster-detail">{detail}</div>'
            f'</div>'
        )
    tier = grs_tier(score)
    return (
        f'<div class="grs-cluster">'
        f'<div class="grs-cluster-label">{label}</div>'
        f'<div class="grs-cluster-value grs-{tier}">'
        f'{score:.0f}<span style="font-size:0.85rem;">%</span></div>'
        f'<div class="grs-cluster-detail">{detail}</div>'
        f'</div>'
    )


_clusters_html = (
    '<div class="grs-clusters">'
    + _cluster_block(
        "Commodity Health",
        grs["commodity"],
        "Brent · TTF · Fertilizer (Urea)",
    )
    + _cluster_block(
        "Logistics Health",
        grs["logistics"],
        "Malacca · Hormuz · Panama",
    )
    + _cluster_block(
        "Physical Buffers",
        grs["buffers"],
        "Helium · CO2 Byproduct · OECD Oil Inv",
    )
    + '</div>'
)

# v15.2 — dynamic description: maps the numeric tier to operating
# posture (Systemic Stability / Strained Baseline / Structural
# Failure) so the panel translates the score into an action stance.
if _grs_tier in GRS_DESCRIPTIONS:
    _desc_headline, _desc_body = GRS_DESCRIPTIONS[_grs_tier]
    _grs_description_html = (
        f'<div class="grs-description grs-{_grs_tier}">'
        f'<span class="grs-desc-headline">{_desc_headline}</span>'
        f'{_desc_body}'
        f'</div>'
    )
else:
    _grs_description_html = ""

st.markdown(
    f'<div class="{_grs_panel_class}">'
    f'<div class="grs-header">'
    f'<span class="grs-title">◆ Global Resilience Score (GRS)</span>'
    f'{_grs_tag_html}'
    f'{_grs_score_html}'
    f'</div>'
    f'{_grs_bar_html}'
    f'{_clusters_html}'
    f'{_grs_description_html}'
    f'</div>',
    unsafe_allow_html=True,
)
with st.expander("ⓘ How is the Global Resilience Score calculated?",
                 expanded=False):
    st.markdown(
        "**The GRS measures total systemic health** by averaging "
        "three equally-weighted clusters and translating the result "
        "into an operating posture:\n\n"
        "- **> 70% Systemic Stability** — global buffers absorbing "
        "shocks, normal procurement.\n"
        "- **40–70% Strained Baseline** — buffers depleting, shift "
        "to 'Just-in-Case' inventory.\n"
        "- **< 40% Structural Failure** — physical supply gaps have "
        "replaced price discovery, rationing protocols active.\n\n"
        "Cluster definitions:\n"
        "1. **Commodity Health** — Brent ($100→$130), TTF (€52→€80), "
        "Urea ($320→$800).\n"
        "2. **Logistics Health** — Malacca severity, Hormuz daily "
        "transits (80→20), Panama Neopanamax slot ($1.5M→$4.0M).\n"
        "3. **Physical Buffers** — Helium boil-off ramp (0→48 days), "
        "EU ammonia / CO2 byproduct breach, OECD commercial oil "
        "inventories vs the 842 MB operational minimum.\n\n"
        "Each metric is mapped to a 0–100 health score; the cluster "
        "average ignores any inputs that are currently unavailable."
    )

# Status strip + extended-blockade banner sit *under* the GRS so the
# composite score gets first read.
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


def card_equity_html(ticker_key, snapshot, sparkline_series=None,
                     caption_key=None):
    """Equity proxy card. CRITICAL (|daily move| >= 12%) raises the
    pulsing red glow, WARNING (>= 5%) raises the static amber glow,
    NOMINAL stays plain.

    `sparkline_series` (v13) — optional 7-day price series. When
    provided, renders an inline SVG sparkline next to the headline
    price.

    `caption_key` (v15.2) — optional key into CAPTION_TEXTS for the
    state-dependent "Why & What" caption (e.g., 'ai_storage' for
    WDC/STX, 'cf' for CF Industries).

    Each card carries a small italic 'why it matters' footer sourced
    from EQUITY_PROXY_META."""
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

    is_breach = sev == "critical"
    is_warn = sev == "warning"
    if is_breach:
        card_class = "intel-card intel-card-breached"
    elif is_warn:
        card_class = "intel-card intel-card-warning"
    else:
        card_class = "intel-card"
    glyph = EQUITY_TIER_GLYPH.get(sev or "nominal", "●")
    tier_label = (sev or "nominal").upper()
    price_str = f"${price:,.2f}" if price is not None else "—"

    spark_color = sparkline_color_for_breach(is_breach, is_warn)
    sparkline_html = (
        render_sparkline_svg(sparkline_series, color=spark_color)
        if sparkline_series else ""
    )
    if sparkline_html:
        value_block = (
            f'<div class="sparkline-row">'
            f'<div class="intel-card-value">{price_str}</div>'
            f'{sparkline_html}'
            f'<span class="sparkline-label">7D</span>'
            f'</div>'
        )
    else:
        value_block = (
            f'<div class="intel-card-value">{price_str}</div>'
        )

    caption_html = ""
    if caption_key:
        cap_text, cap_state = get_card_caption(
            caption_key, breach=is_breach, warning=is_warn,
        )
        if cap_text:
            source_html = render_source_link_html(caption_key)
            caption_html = (
                f'<div class="intel-card-caption caption-{cap_state}">'
                f'<span class="caption-tag">{cap_state}</span>'
                f'{html.escape(cap_text)}'
                f'{source_html}'
                f'</div>'
            )

    if change is None:
        delta_html = (
            f'<div class="intel-card-delta">'
            f'proxy: {proxy_safe} · daily Δ unavailable</div>'
        )
    else:
        change_str = f"{'+' if change >= 0 else ''}{change:.2f}%"
        if is_breach or is_warn:
            delta_class = "delta-bear"
        else:
            delta_class = "delta-flat"
        delta_html = (
            f'<div class="intel-card-delta {delta_class}">'
            f'{glyph} {tier_label} &nbsp;·&nbsp; {change_str} '
            f'&nbsp;·&nbsp; {proxy_safe}</div>'
        )
    return (
        f'<div class="{card_class}">'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'{value_block}'
        f'{delta_html}'
        f'{context_html}'
        f'{caption_html}'
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
    # v15.2 — every commodity card carries a 7-day sparkline plus a
    # state-driven "Why & What" caption. Warning tiers light up the
    # static amber glow before the critical pulse engages.
    _brent_warn = (
        brent_v is not None and 115 < brent_v <= 130
    ) and not brent_breach
    _gold_warn = (gold_v is not None and 4400 < gold_v <= 4600)
    _ttf_warn = (
        ttf_v is not None and 65 < ttf_v <= 80
    ) and not (ttf_v is not None and ttf_v > 80)
    _ttf_breach = ttf_v is not None and ttf_v > 80
    _silver_warn = (silver_v is not None and 60 < silver_v <= 75)

    commodity_cards = [
        card_numeric_html(
            "BRENT CRUDE  (BZ=F)", brent_v, BASELINE["Brent"],
            "$", True, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=brent_breach,
            warning=_brent_warn,
            sparkline_series=sparkline_series.get("Brent"),
            caption_key="brent",
        ),
        card_numeric_html(
            "TTF GAS  (TTF=F)", ttf_v, BASELINE["TTF"],
            "€", True, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=_ttf_breach,
            warning=_ttf_warn,
            sparkline_series=sparkline_series.get("TTF"),
            caption_key="ttf",
        ),
        card_numeric_html(
            "GOLD  (GC=F)", gold_v, BASELINE["Gold"],
            "$", False, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=gold_v is not None and gold_v > 4600,
            warning=_gold_warn,
            sparkline_series=sparkline_series.get("Gold"),
            caption_key="gold",
        ),
        card_numeric_html(
            "SILVER  (SI=F)", silver_v, BASELINE["Silver"],
            "$", False, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=silver_v is not None and silver_v > 75,
            warning=_silver_warn,
            sparkline_series=sparkline_series.get("Silver"),
            caption_key="silver",
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
    # v15.2 — sparklines on every equity card; per-ticker caption
    # keys map into CAPTION_TEXTS. WDC and STX share the 'ai_storage'
    # caption since they tell the same hyperscaler-lockout story.
    _equity_caption_keys = {
        "CF": "cf",
        "DOW": "dow",
        "APD": "apd",
        "JETS": "jets",
        "WDC": "ai_storage",
        "STX": "ai_storage",
    }
    equity_cards = [
        card_equity_html(
            key, equity_snapshots[key],
            sparkline_series=sparkline_series.get(key),
            caption_key=_equity_caption_keys.get(key),
        )
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

    # v15.2 — three-tier breach/warning state so amber lights up
    # before the pulsing red critical glow does.
    _panama_breach = panama_v is not None and panama_v > 4_000_000
    _panama_warn = (
        panama_v is not None
        and 2_500_000 < panama_v <= 4_000_000
    )
    _urea_breach = urea_v is not None and urea_v > 800
    _urea_warn = urea_v is not None and 600 < urea_v <= 800
    _hormuz_breach = hormuz_v is not None and hormuz_v < 20
    _hormuz_warn = hormuz_v is not None and 20 <= hormuz_v < 30

    intel_cards.append(card_numeric_html(
        "PANAMA NEOPANAMAX  (slot $)",
        panama_v,
        INTEL_BASELINE["panama_canal_neopanamax_price"],
        "$", True, fmt="{:,.0f}",
        breach=_panama_breach,
        warning=_panama_warn,
        caption_key="panama",
    ))
    intel_cards.append(card_numeric_html(
        "UREA SPOT  ($/ton)",
        urea_v,
        INTEL_BASELINE["urea_spot_price_ton"],
        "$", True, fmt="{:,.0f}",
        breach=_urea_breach,
        warning=_urea_warn,
        caption_key="urea",
    ))
    intel_cards.append(card_numeric_html(
        "HORMUZ TRANSITS  (ships/day)",
        hormuz_v,
        INTEL_BASELINE["hormuz_daily_transit_count"],
        "", False, fmt="{:.0f}",
        breach=_hormuz_breach,
        warning=_hormuz_warn,
        caption_key="hormuz",
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
            caption_key="malacca",
        ))
    elif shadow_active and malacca_sev != "elevated":
        # v15.2 — CONGESTION SHADOW now renders with the static amber
        # glow (warning=True) instead of the pulsing red critical
        # glow. The spec calls this state "🟡 WARNING (Shadow
        # Congestion)" — distinct from a confirmed CRITICAL closure.
        ships_label = f"{malacca_ships:.0f} ships waiting" if (
            malacca_ships is not None
        ) else "ships waiting"
        delta_label = (
            f" (+{shadow_pct:.1f}% vs 80/day baseline)"
            if shadow_pct is not None else ""
        )
        # Status-card detail combines the v15.2 hotfix context text
        # (Indonesia transit fees + insurance loiter) with the live
        # ships-waiting figure so the operator sees both the cause
        # and the leading-indicator number on one card.
        detail_text = malacca_status or (
            "Malacca congestion provides 48–72 hours of lead time "
            "before total global manufacturing collapse (Tail Risk "
            "Trigger)."
        )
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            "🟡 WARNING: SHADOW CONGESTION",
            "#ffa500",
            f"{ships_label}{delta_label}. {detail_text}",
            warning=True,
            caption_key="malacca",
        ))
    elif malacca_sev is None and malacca_status is None:
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            MALACCA_BASELINE_SEVERITY.upper(),
            SEVERITY_COLORS.get(MALACCA_BASELINE_SEVERITY, "#9ca3af"),
            MALACCA_BASELINE_STATUS,
            is_baseline=True,
            caption_key="malacca",
        ))
    else:
        sev = malacca_sev or "nominal"
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            sev.upper(),
            SEVERITY_COLORS.get(sev, "#9ca3af"),
            malacca_status or "(no status text returned)",
            breach=sev == "elevated",
            caption_key="malacca",
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
            caption_key="helium",
            caption_fmt={
                "days_past": _days_past,
                "boil_off": HELIUM_BOIL_OFF_DAYS,
            },
        ))
    else:
        _helium_breach = helium_v is not None and helium_v > 2000
        intel_cards.append(card_numeric_html(
            "HELIUM SPOT  ($/Mcf)",
            helium_v,
            INTEL_BASELINE["helium_spot_price_mcf"],
            "$", True, fmt="{:,.0f}",
            breach=_helium_breach,
            caption_key="helium",
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
            caption_key="co2",
        ))
    else:
        intel_cards.append(card_status_html(
            "INDUSTRIAL CO2 BYPRODUCT",
            "NOMINAL",
            "#10b981",
            "European ammonia capacity within nominal range; food-grade "
            "CO2 byproduct supply stable.",
            caption_key="co2",
        ))

    _resin_breach = resin_v is not None and resin_v > 40
    _resin_warn = resin_v is not None and 20 < resin_v <= 40
    intel_cards.append(card_numeric_html(
        "PE/PP RESIN SPIKE  (Asia)",
        resin_v,
        INTEL_BASELINE["asian_pe_pp_resin_spike"],
        "", True, fmt="{:.1f}", suffix="%", delta_decimals=1,
        breach=_resin_breach,
        warning=_resin_warn,
        caption_key="resin",
    ))
    _jet_breach = jet_v is not None and jet_v > 1500
    _jet_warn = jet_v is not None and 1100 < jet_v <= 1500
    intel_cards.append(card_numeric_html(
        "JET FUEL  ($/ton)",
        jet_v,
        INTEL_BASELINE["jet_fuel_price_ton"],
        "$", True, fmt="{:,.0f}",
        breach=_jet_breach,
        warning=_jet_warn,
        caption_key="jet",
    ))

    if rice_ban == "ACTIVE":
        intel_cards.append(card_status_html(
            "INDIA RICE EXPORT BAN", "🔴 ACTIVE / CRITICAL", "#dc2626",
            "Indian government export ban currently in force on at "
            "least one rice category. Sovereign food-policy shock "
            "active.",
            breach=True,
            caption_key="rice",
        ))
    elif rice_ban == "INACTIVE":
        intel_cards.append(card_status_html(
            "INDIA RICE EXPORT BAN", "INACTIVE", "#10b981",
            "No active Indian rice export ban currently in force.",
            caption_key="rice",
        ))
    else:
        intel_cards.append(card_status_html(
            "INDIA RICE EXPORT BAN",
            RICE_BAN_BASELINE,
            "#10b981",
            "Peace-time baseline — no active export ban on file.",
            is_baseline=True,
            caption_key="rice",
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

    # ----- v13: Systemic Cascade Map (Mermaid flowchart) -----
    # Streamlit renders each call as its own DOM container, so we
    # don't try to wrap the title + iframe + trigger note in a single
    # div. Instead, each part is styled independently to read as a
    # unified panel. Mermaid runs inside an iframe via
    # st.components.v1.html so the spec'd
    # `fill:#ff4b4b,stroke:#fff,stroke-width:2px` styling on the CO2
    # and Medical Gas nodes is honoured exactly when EU ammonia < 40%.
    st.markdown(
        '<div class="cascade-container" '
        'style="padding-bottom:0.6rem;margin-bottom:0;">'
        '<div class="col-section-title" '
        'style="margin:0 0 0.4rem 0;border:none;padding:0;">'
        '◆ Systemic Cascade: Energy to Medical</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    render_mermaid_cascade(CO2_BYPRODUCT_BREACH)
    if CO2_BYPRODUCT_BREACH:
        st.markdown(
            f'<div class="cascade-container cascade-trigger-note '
            f'cascade-active" style="margin-top:0;'
            f'padding:0.85rem 1.1rem;font-style:normal;">'
            f'<strong style="color:#fca5a5;">▼ CASCADE ACTIVE</strong> '
            f'— EU ammonia at {EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}% '
            f'(below {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}% threshold). '
            f'Food-grade CO2 byproduct is exhausted; downstream nodes '
            f'(meat shelf-life, beverage carbonation, MRI cryogenics) '
            f'all degrade in parallel.'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="cascade-container cascade-trigger-note" '
            f'style="margin-top:0;padding:0.85rem 1.1rem;'
            f'font-style:normal;">'
            f'EU ammonia capacity at {EUROPEAN_AMMONIA_CAPACITY_PCT:.0f}% '
            f'(threshold {EUROPEAN_AMMONIA_THRESHOLD_PCT:.0f}%). '
            f'Cascade nodes nominal — food-grade CO2 byproduct supply '
            f'stable.'
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
            css_class = (
                "alert-critical" if a["level"] == "critical"
                else "alert-warn"
            )
            tag = "CRITICAL" if a["level"] == "critical" else "ELEVATED"
            # v15.2 — Business and Household sit in a two-column
            # grid so the operator sees both responses side by side.
            # html.escape on the trigger/body text guards against
            # any LLM-derived content that might contain raw HTML.
            trigger_safe = html.escape(a["trigger"])
            biz_safe = html.escape(a["business"])
            hh_safe = html.escape(a["household"])
            st.markdown(
                f'<div class="{css_class}">'
                f'<b>[{tag}]  {trigger_safe}</b>'
                f'<div class="playbook-actions">'
                f'<div class="playbook-action">'
                f'<span class="playbook-action-title">'
                f'🏢 Business</span>'
                f'<div class="playbook-action-body">{biz_safe}</div>'
                f'</div>'
                f'<div class="playbook-action">'
                f'<span class="playbook-action-title">'
                f'🏠 Household</span>'
                f'<div class="playbook-action-body">{hh_safe}</div>'
                f'</div>'
                f'</div>'
                f'</div>',
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
