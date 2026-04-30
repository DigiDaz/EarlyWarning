import concurrent.futures
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
        /* v15.3 — bumped to 5rem to clear the Streamlit / GitHub
           top navigation bar plus the sticky Critical Alert Ribbon
           in one shot. Earlier 2.75rem was leaving the ribbon
           partially clipped behind the host chrome. */
        padding-top: 5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
        scroll-margin-top: 5rem;
    }
    /* v15.3 — also target Streamlit's more specific
       `.main .block-container` selector so the spacing wins on
       Community Cloud where the host chrome is tallest. */
    .main .block-container {
        padding-top: 5rem !important;
    }
    .hud-title {
        scroll-margin-top: 5rem;
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
    .hud-subtitle .intel-armed,
    .hud-subtitle .intel-live {
        color: #00ffd1;
        font-weight: 700;
        letter-spacing: 2px;
    }
    /* Fix C-4 — the badge now reflects live-fraction + override
       count, not the credentials check. Three tiers, each with its
       own colour so the user can read the dashboard's truthfulness
       at a glance. */
    .hud-subtitle .intel-mixed {
        color: #ffa500;
        font-weight: 700;
        letter-spacing: 2px;
    }
    .hud-subtitle .intel-degraded {
        color: #fca5a5;
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

    /* v15.3 — Strategic Planning & Action cards. Sit between the
       Strategic Outlook narrative and the 3-column body, surfacing
       a single directive per RED/AMBER metric. Same glassmorphic
       treatment as the rest of the HUD with tier-coloured glow so
       the eye groups them with the per-card alert pulse below. */
    .strategic-action-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .strategic-action-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-left-width: 4px;
        border-radius: 6px;
        padding: 1rem 1.15rem;
        font-family: 'Courier New', monospace;
        display: flex;
        flex-direction: column;
        min-height: 180px;
    }
    .strategic-action-card.sa-critical {
        border-left-color: #ff4b4b;
        box-shadow: 0 0 18px rgba(255, 75, 75, 0.20);
    }
    .strategic-action-card.sa-warning {
        border-left-color: #ffa500;
        box-shadow: 0 0 14px rgba(255, 165, 0, 0.18);
    }
    .sa-tag {
        font-size: 0.62rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 2px;
        display: inline-block;
        margin-bottom: 0.55rem;
        align-self: flex-start;
    }
    .sa-critical .sa-tag { background: #ff4b4b; color: #000; }
    .sa-warning  .sa-tag { background: #ffa500; color: #000; }
    .sa-metric {
        color: #9ca3af;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1.8px;
        margin-bottom: 0.35rem;
    }
    .sa-headline {
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 0.55rem;
        letter-spacing: 0.5px;
        line-height: 1.3;
    }
    .sa-critical .sa-headline { color: #fca5a5; }
    .sa-warning  .sa-headline { color: #fed7aa; }
    .sa-body {
        color: #d1d5db;
        font-size: 0.83rem;
        line-height: 1.55;
        margin-top: auto;
    }

    /* Fix C-2 — Visible stale state. Cards with no live read must
       not look like nominal cards displaying a peace-time price.
       Dashed grey border, dimmed surface, "NO LIVE DATA" headline,
       and a hatched "STALE" badge so a 2-second glance never
       mistakes stale data for live nominal. */
    .intel-card-stale {
        background: rgba(255, 255, 255, 0.025) !important;
        border: 1px dashed rgba(156, 163, 175, 0.5) !important;
        border-left: 1px dashed rgba(156, 163, 175, 0.5) !important;
        box-shadow: none !important;
        animation: none !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
    }
    .intel-card-stale .intel-card-label {
        color: #6b7280;
    }
    .intel-card-stale-headline {
        color: #6b7280;
        font-size: 1.15rem;
        line-height: 1.25;
        letter-spacing: 1px;
        margin-bottom: 0.45rem;
        text-transform: uppercase;
        display: flex;
        align-items: center;
        gap: 0.55rem;
        flex-wrap: wrap;
    }
    .stale-badge {
        font-family: 'Courier New', monospace;
        font-size: 0.6rem;
        letter-spacing: 1.5px;
        font-weight: 700;
        color: #1f2937;
        padding: 2px 8px;
        border-radius: 2px;
        text-transform: uppercase;
        background-color: #9ca3af;
        background-image: repeating-linear-gradient(
            45deg,
            rgba(0, 0, 0, 0.18) 0,
            rgba(0, 0, 0, 0.18) 4px,
            transparent 4px,
            transparent 8px
        );
        border: 1px solid rgba(0, 0, 0, 0.15);
    }
    .intel-card-stale-meta {
        color: #6b7280;
        font-size: 0.7rem;
        line-height: 1.45;
        margin-top: 0.4rem;
        font-style: italic;
    }
    .intel-card-stale-meta strong {
        color: #9ca3af;
        font-style: normal;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.62rem;
    }
    .intel-card-caption.caption-stale {
        color: #9ca3af;
        border-top-color: rgba(156, 163, 175, 0.18);
    }

    /* Fix 2b — per-card "LAST PULL" footer. Sits below the
       caption block, separated by a thin top border. Single-line
       (white-space: nowrap) so the source label and relative
       time scan cleanly across all cards in a row. Muted grey
       so it doesn't compete with the headline. */
    .intel-card-source-footer {
        margin-top: 0.55rem;
        padding-top: 0.45rem;
        border-top: 1px solid rgba(156, 163, 175, 0.14);
        color: #9ca3af;
        font-size: 0.72rem;
        line-height: 1.3;
        letter-spacing: 0.4px;
        font-family: 'Courier New', monospace;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .intel-card-source-footer.source-editorial {
        color: #fde68a;
    }
    .intel-card-source-footer.source-baseline {
        color: #9ca3af;
        font-style: italic;
    }
    .intel-card-caption.caption-stale .caption-tag {
        background-color: #6b7280;
        color: #f3f4f6;
        background-image: repeating-linear-gradient(
            45deg,
            rgba(0, 0, 0, 0.18) 0,
            rgba(0, 0, 0, 0.18) 3px,
            transparent 3px,
            transparent 6px
        );
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# v15.3 — explicit ribbon-clearance override. Streamlit on Community
# Cloud / GitHub Codespaces injects its own top chrome which clips
# the Critical Alert Ribbon at first paint. This single-rule
# stylesheet guarantees the dashboard has 5rem of clear space at
# the top of the block container regardless of host chrome.
st.markdown(
    '<style>.main .block-container {padding-top: 5rem;}</style>',
    unsafe_allow_html=True,
)

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
    # Fix 3 — resin metric reframed. The data key now carries the
    # absolute Asia PP spot price in USD per metric tonne; the
    # "spike percentage" is computed at render time so Perplexity
    # can be asked for what trade press actually publishes.
    # Late-2024 / early-2025 Asia PP traded around $0.90–1.05/kg
    # (= $900–1050/tonne); $1,000 is the clean baseline.
    "asian_pp_spot_price_ton": 1000.0,
    "jet_fuel_price_ton": 850.0,
    # v18 Fix 3 — EU gas storage fill % (AGSI+). Peak storage runs
    # ~95% in October before winter draw; Q2 is the rebuild window
    # so 80%+ is a healthy baseline target heading into next winter.
    "eu_gas_storage_pct": 80.0,
}

# Qualitative peace-time defaults (no numeric baseline applies).
MALACCA_BASELINE_SEVERITY = "nominal"
MALACCA_BASELINE_STATUS = (
    "Peace-time baseline — no active maritime disruption flagged."
)
RICE_BAN_BASELINE = "INACTIVE"

# Fix C-5 — un-pinned base probabilities so the engine has room to
# move in BOTH directions. The v11 hard-pin {Best 0, Slow 0, Base
# 60, Tail 40} prevented the matrix from ever reflecting an
# improving real-world picture; with Urea at $685 (well below the
# Tail trigger), Jet at $989 (well below $1500), and TTF at €46
# (BELOW the €52 baseline), the engine should be able to drift
# toward Slow Normalization or Best Case but mathematically could
# not. v11 starting weights are restored here. The "blockade
# extension" event is now represented as a starting tilt the
# downside rules can offset, not a hard zero.
BASE_PROBS = {
    "Best Case": 5.0,
    "Slow Normalization": 15.0,
    "Base Case": 50.0,
    "Tail Risk": 30.0,
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

# v15.5 — strictly-neutral query pattern. Every metric is asked in
# the same exact form: "What is the status/value of [X] on April 30,
# 2026? Find primary source official notifications." This matches
# the `get_neutral_intel(topic)` interface from the brief and
# eliminates leading phrasing that could bias the LLM toward a
# particular answer. Primary sources only — no speculation, no
# secondary commentary.
PERPLEXITY_USER_PROMPT = (
    "For each metric below, answer the strictly-neutral question: "
    "\"What is the status/value of this metric on April 30, 2026?\" "
    "Find primary source official notifications, regulator "
    "statements, exchange data feeds, and recognised "
    "market-intelligence reports. Do not rely on speculation or "
    "unverified social media. "
    "Metrics: "
    "1. Panama Canal average auction price for Neopanamax slots. "
    "2. Global Urea spot price per ton. "
    "3. Strait of Hormuz daily ship transit counts. "
    "4. Strait of Malacca maritime congestion status, vessel backlog "
    "delays, or breaking maritime incidents. "
    "4b. Number of ships waiting/queued at the Strait of Malacca "
    "anchorage (peace-time baseline ~80). "
    "5. Global spot price for Helium per Mcf. "
    "6. Estimated price spike / percentage increase for Asian PE/PP "
    "base resins. "
    "7. Global average jet fuel price per ton. "
    "8. Whether an Indian rice export ban is currently in place "
    "(output exactly \"ACTIVE\" or \"INACTIVE\" — note that DGFT "
    "Notification 07/2026-27 from April 10 was a liberalising "
    "measure, not a ban). "
    "If you cannot find the exact live data for today, provide the "
    "most recently available closing price or count from the last "
    "7 days. Do not output 0. "
    "Return a single raw JSON object with exactly these keys: "
    "panama_canal_neopanamax_price, urea_spot_price_ton, "
    "hormuz_daily_transit_count, malacca_status, malacca_severity, "
    "malacca_ships_waiting, helium_spot_price_mcf, "
    "asian_pe_pp_resin_spike, jet_fuel_price_ton, "
    "india_rice_ban_status. "
    "Numeric values only for the numeric keys. No markdown, no prose."
)


# ============================================================
# v16 (Fix 1) — INTEL_METRICS fan-out config
# ============================================================
# The v15.x single-call ten-field prompt was too broad — sonar-pro
# couldn't reliably source ten heterogeneous metrics in one shot for
# a specific date and most fields came back null. This config drives
# a per-metric fan-out: each metric becomes its own narrow neutral
# Perplexity question with a tight expected-type contract and a
# named primary-source list. Calls run in parallel via a
# ThreadPoolExecutor so wall time stays comparable to the old
# single call. Each metric is cached independently so a single
# failing metric does not poison the whole feed.
#
# The dict shape mirrors the v15.x output keys exactly so downstream
# rendering, the editorial-override layer, and the engine all keep
# working without changes.
INTEL_METRICS = {
    "panama_canal_neopanamax_price": {
        # v18 Fix 1a — wider 30-day window. ACP reports auction
        # averages in batches every few weeks, not daily; a 7-day
        # window guaranteed null on most days. Trade press
        # (Maritime Executive, Seatrade, gCaptain) re-publishes the
        # ACP figures so they're a valid secondary source.
        "question":
            "What is the most recent Panama Canal Authority "
            "(ACP) reported average auction slot price for "
            "Neopanamax vessels in US dollars? Use the latest "
            "publicly reported figure from the last 30 days. "
            "Provide a primary citation.",
        "expected_type": "number",
        "unit_hint": "USD per slot",
        "primary_sources": [
            "Panama Canal Authority press releases (pancanal.com)",
            "Reuters Maritime",
            "Maritime Executive",
            "Seatrade Maritime",
            "gCaptain",
            "Argus",
        ],
    },
    "urea_spot_price_ton": {
        "question":
            "What is the current global urea spot price in US "
            "dollars per metric tonne?",
        "expected_type": "number",
        "unit_hint": "USD per metric tonne",
        "primary_sources": [
            "Argus", "S&P Global Platts", "ICIS",
            "CME urea futures", "Reuters Commodities",
        ],
    },
    "hormuz_daily_transit_count": {
        "question":
            "What is the current Strait of Hormuz daily ship "
            "transit count? Provide a primary citation.",
        "expected_type": "number",
        "unit_hint": "ships per day",
        "primary_sources": [
            "Lloyd's List Intelligence",
            "Kpler", "Bloomberg shipping desk", "Reuters Maritime",
        ],
    },
    "malacca_status": {
        "question":
            "What is the current Strait of Malacca maritime traffic "
            "status? Summarise any congestion, vessel backlog, or "
            "breaking incidents in one sentence.",
        "expected_type": "string",
        "unit_hint": None,
        "primary_sources": [
            "Reuters Maritime", "Lloyd's List Intelligence",
            "Kpler", "MarineTraffic",
        ],
    },
    "malacca_severity": {
        "question":
            "What is the current Strait of Malacca traffic severity? "
            "Output exactly one of: \"nominal\", \"elevated\", or "
            "\"critical\". Use \"critical\" only when transit is "
            "actively disrupted by a confirmed closure, channel "
            "obstruction, or security incident reported in the last "
            "7 days.",
        "expected_type": "enum",
        "enum_values": ["nominal", "elevated", "critical"],
        "primary_sources": [
            "Reuters Maritime", "Lloyd's List Intelligence", "Kpler",
        ],
    },
    "malacca_ships_waiting": {
        "question":
            "What is the current number of ships waiting or queued "
            "at the Strait of Malacca anchorage? Peace-time baseline "
            "is approximately 80 vessels.",
        "expected_type": "number",
        "unit_hint": "ships waiting",
        "primary_sources": [
            "MarineTraffic", "Kpler", "Reuters Maritime",
        ],
    },
    "helium_spot_price_mcf": {
        "question":
            "What is the current global helium spot price in US "
            "dollars per Mcf (thousand cubic feet)?",
        "expected_type": "number",
        "unit_hint": "USD per Mcf",
        "primary_sources": [
            "gasworld", "Linde / Air Products / Air Liquide investor disclosures",
            "specialty gas trade press",
        ],
    },
    "asian_pp_spot_price_ton": {
        # Fix 3 — ask for the absolute Asia PP spot price (which
        # trade press actually publishes) instead of a derived
        # "spike percentage" (which they don't). The card's spike
        # display is computed at render time from this absolute
        # price vs the $1,000/tonne 2024-2025 baseline.
        "question":
            "What is the current Asian polypropylene (PP) spot "
            "price in US dollars per metric tonne? Use Northeast "
            "Asia / Southeast Asia FOB or CFR China. Provide a "
            "primary citation from the last 7 days.",
        "expected_type": "number",
        "unit_hint": "USD per metric tonne (Asia PP spot)",
        "primary_sources": [
            "ICIS", "S&P Global Platts", "Argus",
            "Reuters Commodities", "IMARC monthly regional report",
            "Trading Economics polypropylene CFD",
        ],
    },
    "jet_fuel_price_ton": {
        "question":
            "What is the current global average jet fuel (kerosene) "
            "price in US dollars per metric tonne?",
        "expected_type": "number",
        "unit_hint": "USD per metric tonne",
        "primary_sources": [
            "IATA fuel monitor", "S&P Global Platts",
            "Argus", "Reuters Commodities",
        ],
    },
    "india_rice_ban_status": {
        "question":
            "Is an Indian government rice export ban currently in "
            "force? Output exactly \"ACTIVE\" or \"INACTIVE\". "
            "ACTIVE means a ban on any rice category (non-basmati "
            "white, broken, or parboiled) is currently in force.",
        "expected_type": "enum",
        "enum_values": ["ACTIVE", "INACTIVE"],
        "primary_sources": [
            "DGFT (apeda.gov.in/dgft-notifications)",
            "Reuters India",
            "Bloomberg",
        ],
    },
    # v18 Fix 3 — EU gas storage fill level. Highest-quality
    # directly-observable buffer indicator; AGSI+ (Gas
    # Infrastructure Europe) publishes this daily.
    "eu_gas_storage_pct": {
        "question":
            "What is the current EU gas storage fill level as a "
            "percentage of capacity? Use the most recent AGSI+ "
            "(Gas Infrastructure Europe) daily report.",
        "expected_type": "percent",
        "unit_hint": "percent of capacity",
        "primary_sources": [
            "AGSI+ (agsi.gie.eu)",
            "Gas Infrastructure Europe",
            "Reuters Commodities",
            "Bloomberg",
        ],
    },
}


# v16 (Fix 1) — terse system prompt. Each per-metric call uses the
# same short system instruction; the user prompt carries the metric-
# specific question + primary-source hints + return-shape contract.
PERPLEXITY_PER_METRIC_SYSTEM_PROMPT = (
    "You are a neutral primary-source research assistant. "
    "Answer the user's single-metric question with strict honesty: "
    "if you cannot find a primary citation from the last 7 days, "
    "return null. Do not guess, infer, or extrapolate. "
    "Return ONLY a single raw JSON object on one line: "
    '{"value": ...}. '
    "No prose, no markdown fences, no citations, no commentary."
)


# v18 Fix 2 — cache the fetch timestamp ALONGSIDE the value so it
# survives across reruns. The previous module-level _FETCH_TIMESTAMPS
# dict was reset every script run; cache hits never re-recorded so
# every yfinance card showed "LAST PULL: unknown". Returning the
# timestamp as part of the cached payload means the cache stores it
# too, and on a cache hit we get the original fetch time back.
_FETCH_TIMESTAMPS = {}  # legacy; kept for sparkline-only paths


def _record_fetch(kind, ticker):
    _FETCH_TIMESTAMPS[(kind, ticker)] = (
        datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    )


@st.cache_data(ttl=14400)
def fetch_price(ticker: str):
    """v18 Fix 2 — return (value, fetched_at_iso). Tuple is cached
    so the timestamp persists across reruns. value is None when
    yfinance returned no data."""
    try:
        data = yf.Ticker(ticker).history(period="2d", interval="1d")
        if data.empty:
            return None, None
        return (
            float(data["Close"].iloc[-1]),
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    except Exception:
        return None, None


@st.cache_data(ttl=14400)
def fetch_sparkline_series(ticker: str) -> list:
    """v13 — return last 7 trading-day Close values for sparkline
    rendering. Cached on the same 4-hour window as fetch_price /
    fetch_equity_snapshot so the trend is consistent with the headline
    number on every card. Sparkline doesn't need a timestamp; the
    headline card carries that."""
    _record_fetch("yfinance_sparkline", ticker)
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
    """v18 Fix 2 — Return {"price", "pct_change", "fetched_at"}.
    Any field can be None when the data is unavailable. period=5d
    guarantees we get at least two trading-day closes even after a
    long weekend or holiday. fetched_at is captured at fetch time
    so it survives cache hits."""
    out = {"price": None, "pct_change": None, "fetched_at": None}
    try:
        data = yf.Ticker(ticker).history(period="5d", interval="1d")
        if data.empty:
            return out
        out["price"] = float(data["Close"].iloc[-1])
        out["fetched_at"] = (
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )
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
    """Fix C-5 — date math AND no contradicting live signal.

    v11 brief: at >= 48 days past the Qatar force majeure, fab and
    MRI stockpiles drain — semiconductor yield collapse is imminent.
    But the calendar alone is no longer a defensible default: if
    live helium spot has fallen back below $1,000/Mcf, supply is
    plausibly recovering and 'exhausted' should not auto-fire on
    date math alone.

    Live signal source: the module-level _LIVE_INTEL_DATA cache,
    populated by the call site after the fan-out fetch + editorial
    layer have run. When the cache is empty (e.g. function called
    before the first fetch), date math is the only signal.

    Returns True only when (days_elapsed >= boil-off) AND
    (live spot is None OR live spot >= $1,000/Mcf)."""
    if helium_days_elapsed() < HELIUM_BOIL_OFF_DAYS:
        return False
    live_price = _LIVE_INTEL_DATA.get("helium_spot_price_mcf")
    if live_price is not None and live_price < 1000:
        # Live signal contradicts the date math — supply has
        # plausibly recovered. Don't fire the breach gate.
        return False
    return True


def jet_spike_pct(jet_value):
    """Jet fuel price as % above the peace-time baseline. None-safe."""
    if jet_value is None:
        return None
    base = INTEL_BASELINE["jet_fuel_price_ton"]
    if not base:
        return None
    return (jet_value - base) / base * 100.0


def pp_spike_pct(pp_price):
    """Fix 3 — Asian PP spot price as % above the $1,000/tonne
    2024-2025 baseline. None-safe. Used at render time and inside
    adjust_probabilities / evaluate_playbook so the engine continues
    to think in spike percentages while the data layer carries the
    absolute price the trade press actually publishes."""
    if pp_price is None:
        return None
    base = INTEL_BASELINE.get("asian_pp_spot_price_ton")
    if not base:
        return None
    return (pp_price - base) / base * 100.0


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
        # v15.4 — Gold lost the $4,660 ceiling and is now defending
        # the $4,571 floor. Watch this support; loss of it likely
        # signals a deeper risk-off reset.
        "warning":  "Testing $4,571 support after breaking below "
                    "the $4,660 ceiling.",
        "nominal":  "Flow Normal: macro signals align; defensive "
                    "positioning at routine levels.",
    },
    "silver": {
        "critical": "Industrial-Precious Break: solar and electronics "
                    "BOMs face direct cost pressure. Lock 90-day "
                    "futures for capex pipeline.",
        # Fix A — silver in the warning band ($60-75) needed its own
        # caption; without it the lookup returned (None, None) which
        # collapsed the caption block AND the Source link inside it.
        "warning":  "Industrial-Precious Stretch: cost pressure "
                    "building on solar/electronics BOMs; review "
                    "60-90 day hedge window for capex pipeline.",
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
        # v15.5 — Blockade persists at ~4 ships/day (95% collapse).
        # US rejection of the April 27th reopening offer is now
        # confirmed; assume Ras Laffan offline 3-5 years.
        "critical": "Blockade persists; ~4 ships/day (95% collapse). "
                    "US rejection of April 27th reopening offer "
                    "confirmed.",
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
        # v15.5 — FM Sugiono (April 28) reaffirmed free passage; the
        # transit-fee proposal that triggered the v15.2 shadow tier
        # was confirmed as a retracted thought-experiment, not policy.
        # Traffic at the strait remains within normal bounds.
        "nominal":  "FM Sugiono (April 28) reaffirmed free passage; "
                    "the transit fee proposal was a retracted "
                    "thought-experiment. Traffic remains normal.",
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
    # v18 Fix 3 — EU gas storage caption tiers. <20% sub-critical
    # heading into winter; 20-50% rebuild lagging; 80%+ healthy.
    "eu_gas_storage": {
        "critical": "Storage Sub-Critical: EU gas inventories below "
                    "20% — winter cushion gone. Industrial demand "
                    "destruction tier 2 likely if heating-season "
                    "draw begins on this base.",
        "warning":  "Rebuild Lagging: Q2 storage refill behind the "
                    "80%+ pre-winter target. Watch import flows; "
                    "sustained shortfall pulls TTF up.",
        "nominal":  "Storage On-Track: EU buffer is rebuilding "
                    "toward the 80%+ pre-winter target. AGSI+ "
                    "daily report stable.",
    },
    # v18 Fix 4 — Diesel crack spread caption. Crack > $50/bbl
    # signals product markets are running tighter than crude;
    # consumer transmission accelerates regardless of Brent.
    "diesel_crack": {
        "critical": "Crack Blowout: refined product markets running "
                    "tighter than crude. Diesel pass-through to "
                    "freight, ag, and trucking accelerates "
                    "independent of Brent.",
        "warning":  "Crack Widening: refining margins above the "
                    "normal $15-25/bbl band; downstream pricing "
                    "pressure building.",
        "nominal":  "Refining Margins Stable: diesel crack within "
                    "the normal $15-25/bbl operating band.",
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
        # v15.5 — DGFT Notification 07/2026-27 (April 10, 2026)
        # liberalises rice exports to non-EU European countries by
        # removing the Certificate of Inspection requirement. Net-net
        # liberalising, not restrictive.
        "nominal":  "DGFT Notification 07/2026-27 (April 10) "
                    "liberalizes rice exports to non-EU European "
                    "countries by removing Certificate of Inspection "
                    "requirements.",
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
    'nominal', 'stale', or None when no caption is configured for the
    requested key at all.

    Fix A — graceful severity fallback. If the requested state is
    missing for a configured key, walk DOWN the severity ladder
    (critical → warning → nominal) until a defined caption is found.
    'nominal' is the floor: any configured key returns at minimum
    its nominal copy rather than collapsing to (None, None) and
    eating the Source link below it.

    The state returned is the one that was actually resolved (not
    the one requested) so the caption pill colour stays honest.

    Fix C-2 — when `stale=True` is passed via fmt, look up the
    metric-specific 'stale' copy if present, falling back to a
    generic stale message rather than narrating nominal conditions
    over a card with no live data."""
    if key not in CAPTION_TEXTS:
        return None, None

    is_stale = bool(fmt.pop("stale", False))
    if is_stale:
        text = CAPTION_TEXTS[key].get("stale")
        if text is None:
            text = (
                "No primary-source read available in the last 4 hours. "
                "Card reflects last known reference, not current market."
            )
        if fmt:
            try:
                text = text.format(**fmt)
            except (KeyError, IndexError):
                pass
        return text, "stale"

    if breach:
        ladder = ["critical", "warning", "nominal"]
    elif warning:
        ladder = ["warning", "nominal"]
    else:
        ladder = ["nominal"]

    state = None
    text = None
    for candidate in ladder:
        if candidate in CAPTION_TEXTS[key]:
            state = candidate
            text = CAPTION_TEXTS[key][candidate]
            break

    if text is None:
        return None, None
    if fmt:
        try:
            text = text.format(**fmt)
        except (KeyError, IndexError):
            pass
    return text, state


# ============================================================
# v15.3 — Source URLs (Intelligence Hyperlinks, full coverage)
# ============================================================
# Every captioned card now carries a Source ↗ hyperlink in its
# "Why & What" footer. The five canonical domains confirmed by the
# v15.3 brief are mapped by category:
#
#   Reuters Commodities     → energy, fuels, fertilizer, resins
#   Bloomberg Currencies    → precious metals, equity proxies
#   Gas World News          → industrial gases (helium, CO2)
#   APEDA DGFT Notifications → India rice export ban
#   Kuehne+Nagel News       → maritime / shipping / chokepoints
#
# Additional canonical sources can be wired by extending this dict.
SOURCE_URLS = {
    # Energy & fuels — Reuters commodity desk.
    "brent":      "https://www.reuters.com/markets/commodities/",
    "ttf":        "https://www.reuters.com/markets/commodities/",
    "urea":       "https://www.reuters.com/markets/commodities/",
    "resin":      "https://www.reuters.com/markets/commodities/",
    "jet":        "https://www.reuters.com/markets/commodities/",
    # Precious metals & equity proxies — Bloomberg markets desk.
    "gold":       "https://www.bloomberg.com/markets/currencies/",
    "silver":     "https://www.bloomberg.com/markets/currencies/",
    "ai_storage": "https://www.bloomberg.com/markets/currencies/",
    "cf":         "https://www.bloomberg.com/markets/currencies/",
    "dow":        "https://www.bloomberg.com/markets/currencies/",
    "apd":        "https://www.bloomberg.com/markets/currencies/",
    "jets":       "https://www.bloomberg.com/markets/currencies/",
    # Industrial gases — Gas World news desk.
    "helium":     "https://www.gasworld.com/news/",
    "co2":        "https://www.gasworld.com/news/",
    # Sovereign food policy — APEDA DGFT notifications.
    "rice":       "https://apeda.gov.in/dgft-notifications",
    # Maritime / shipping chokepoints — Kuehne+Nagel news.
    "malacca":    "https://mykn.kuehne-nagel.com/news/",
    "hormuz":     "https://mykn.kuehne-nagel.com/news/",
    "panama":     "https://mykn.kuehne-nagel.com/news/",
    # v18 Fix 3 — EU gas storage primary feed.
    "eu_gas_storage": "https://agsi.gie.eu/",
    # v18 Fix 4 — diesel crack source.
    "diesel_crack":   "https://www.reuters.com/markets/commodities/",
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


def _eu_gas_storage_health(pct):
    """v18 Fix 3 — EU gas storage health gradient. AGSI+ storage
    runs ~30-100% seasonally with 80%+ being healthy heading into
    winter. Linear in between — 80% maps to 100, 20% maps to 0."""
    if pct is None:
        return None
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return None
    if v >= 80.0:
        return 100.0
    if v <= 20.0:
        return 0.0
    return ((v - 20.0) / 60.0) * 100.0


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
    # v18 Fix 4 — diesel crack spread captures downstream consumer
    # transmission Brent alone misses. "Normal" crack ~$15-25/bbl;
    # critical >$50. Even weighting (1/4 each) keeps the cluster
    # balanced.
    diesel_h = _metric_health(
        intel.get("diesel_crack_per_bbl"), 25.0, 50.0,
    )
    commodity = _avg_or_none([brent_h, ttf_h, urea_h, diesel_h])

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
        # v18 Fix 1c — recalibrated to today's actual auction-price
        # band. The previous 1.5M / 4M anchors were tuned for
        # peace-time conditions and read 100% on every realistic
        # number, making the metric mute. New anchors: $385K =
        # current normal (healthy floor), $1M = critical stress.
        intel.get("panama_canal_neopanamax_price"), 385_000.0, 1_000_000.0
    )
    logistics = _avg_or_none([malacca_h, hormuz_h, panama_h])

    # Cluster 3 — Physical Buffers (calibration v2 — gradient scoring)
    #
    # The previous binary 0/100 flips on each gate manufactured a
    # 0% buffers reading the moment all three editorial facts were
    # set TRUE — collapsing GRS by a full 33 points without
    # measuring how strained things actually were. Replace with
    # gradients that map "severely strained but not totally drained"
    # onto a meaningful score.

    # Helium — days-elapsed gradient.
    #   day 0          → 100
    #   day 48 (boil-off)→ 50
    #   day 96 (full drain) → 0
    # Live-spot recovery overlay floors helium_h at 60 when spot
    # falls below $1,000/Mcf for two weeks; the supply has
    # plausibly recovered and date math no longer dominates.
    days = helium_days_elapsed()
    boil_off = HELIUM_BOIL_OFF_DAYS  # 48
    depletion = boil_off * 2          # 96 — full drain
    if days <= 0:
        helium_h = 100.0
    elif days >= depletion:
        helium_h = 0.0
    elif days <= boil_off:
        helium_h = 100.0 - (days / boil_off) * 50.0
    else:
        past = days - boil_off
        helium_h = 50.0 - (past / boil_off) * 50.0
    live_spot = _LIVE_INTEL_DATA.get("helium_spot_price_mcf")
    if live_spot is not None and live_spot < 1000:
        helium_h = max(helium_h, 60.0)

    # CO2 byproduct — capacity-vs-threshold gradient.
    #   capacity   0%  → 0
    #   capacity  40% (threshold) → 50
    #   capacity 100%  → 100
    cap = EUROPEAN_AMMONIA_CAPACITY_PCT
    threshold = EUROPEAN_AMMONIA_THRESHOLD_PCT
    if cap >= 100.0:
        co2_h = 100.0
    elif cap <= 0.0:
        co2_h = 0.0
    elif cap >= threshold:
        span = 100.0 - threshold
        co2_h = 50.0 + ((cap - threshold) / span) * 50.0 \
            if span > 0 else 100.0
    else:
        co2_h = (cap / threshold) * 50.0 if threshold > 0 else 0.0

    # OECD inventory — keep binary (no live MB number available),
    # but reduce its weight in the cluster average so it cannot
    # zero the cluster on its own.
    oecd_h = 0.0 if OECD_INVENTORY_BREACH else 100.0

    # v18 Fix 3 — EU gas storage. Highest-quality directly-
    # observable buffer indicator; AGSI+ publishes this daily.
    # Linear gradient: 80%+ = healthy (100), 20% or below = 0,
    # linear in between.
    gas_storage_h = _eu_gas_storage_health(
        intel.get("eu_gas_storage_pct"),
    )

    # v18 Fix 3 — rebalanced weights now that the cluster has 4
    # signals. Helium + CO2 each drop from 40% to 30%; gas storage
    # comes in at 20%; OECD stays at 20%.
    buffer_parts = [
        (helium_h, 0.30),
        (co2_h, 0.30),
        (gas_storage_h, 0.20),
        (oecd_h, 0.20),
    ]
    cleaned = [(v, w) for v, w in buffer_parts if v is not None]
    if cleaned:
        total_w = sum(w for _, w in cleaned)
        buffers = (
            sum(v * w for v, w in cleaned) / total_w
            if total_w > 0 else None
        )
    else:
        buffers = None

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


# ============================================================
# v15.3 — Strategic Planning & Action
# ============================================================
# Translates the live RED/AMBER status of each cluster into a single
# actionable directive. The catalog below holds the v15.3 brief copy
# verbatim; build_strategic_actions() decides which entries fire
# based on the same trip-points used by the Threshold Monitor and
# the GRS engine, so every section of the dashboard agrees on what
# is hot.

# v15.4 — Strategic Planning collapses to two combined directives,
# matching the v15.4 brief's tightened action set. The Rice / Malacca
# / generic Oil entries from v15.3 are retired because the v15.4
# truth anchor reports those metrics as NOMINAL (Rice liberalised,
# Malacca free-passage). Helium and CO2 are merged into one combined
# directive — they share the same hardware/medical/protein response
# playbook and firing both separately under v15.4 conditions doubled
# the cognitive load without adding new advice.
STRATEGIC_ACTION_CATALOG = {
    "helium_co2": {
        "level": "critical",
        "metric": "Industrial Gases (Helium / CO2)",
        "headline": "Defer Hardware Refreshes",
        "body":
            "Defer hardware refreshes. Pre-position 60-day protein "
            "buffer. Audit medical gas supply.",
    },
    "hormuz": {
        "level": "critical",
        "metric": "Strait of Hormuz",
        "headline": "Lock Energy Financing",
        "body":
            "Lock fixed-rate energy/fuel costs. Assume Ras Laffan "
            "offline 3-5 years.",
    },
}


def build_strategic_actions(prices, intel, brent_breach):
    """v15.4 — emit the directives whose underlying metric is in a
    RED state right now. Two rules:

      1. Helium OR CO2 RED → combined gases directive.
      2. Hormuz RED        → energy / fuel-financing directive.

    Trip-points mirror the Threshold Monitor's tripwires so the
    Strategic Planning section never disagrees with the rest of the
    dashboard. Returns a list (possibly empty) of catalog entries
    that the caller can render as cards.

    Note: `prices` and `brent_breach` are accepted for signature
    stability with v15.3 callers; v15.4 logic does not consult them
    directly because the truth anchor binds Hormuz status."""
    intel = intel or {}
    fired = []

    helium_red = (
        helium_exhausted()
        or (intel.get("helium_spot_price_mcf") or 0) > 2000
    )
    co2_red = CO2_BYPRODUCT_BREACH
    if helium_red or co2_red:
        fired.append(STRATEGIC_ACTION_CATALOG["helium_co2"])

    hormuz = intel.get("hormuz_daily_transit_count")
    hormuz_red = hormuz is not None and hormuz < 20
    if hormuz_red:
        fired.append(STRATEGIC_ACTION_CATALOG["hormuz"])

    return fired


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


def _relative_time(ts):
    """Fix 2b — humanise an ISO-8601 string / date / datetime as
    '14 min ago', '3h ago', '2 days ago'. Returns 'unknown' when
    the input is None or unparseable. Date-only inputs (no time)
    are treated as 00:00 UTC of that date so the math works."""
    if ts is None:
        return "unknown"
    try:
        if isinstance(ts, datetime):
            target = ts
        elif isinstance(ts, date):
            target = datetime(ts.year, ts.month, ts.day)
        elif isinstance(ts, str):
            ts_clean = ts.strip()
            if ts_clean.endswith("Z"):
                ts_clean = ts_clean[:-1] + "+00:00"
            try:
                target = datetime.fromisoformat(ts_clean)
            except ValueError:
                # Date-only ISO string ("2026-04-28")
                target = datetime.fromisoformat(ts_clean + "T00:00:00")
            if target.tzinfo is not None:
                target = target.replace(tzinfo=None)
        else:
            return "unknown"
    except (ValueError, TypeError):
        return "unknown"

    delta_seconds = (datetime.utcnow() - target).total_seconds()
    if delta_seconds < 0:
        return "just now"
    if delta_seconds < 60:
        return f"{int(delta_seconds)}s ago"
    minutes = delta_seconds // 60
    if minutes < 60:
        return f"{int(minutes)} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{int(hours)}h ago"
    days_ = int(hours // 24)
    if days_ < 365:
        return f"{days_} day{'s' if days_ != 1 else ''} ago"
    years = days_ // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def _format_source_footer(source_kind, timestamp_iso,
                          editorial_set_on=None,
                          last_live_fetch=None):
    """Fix 2b — single-line per-card footer.

    source_kind:
      'MARKET'    → 'LAST PULL: <rel> · MARKET (yfinance)'
      'INTEL'     → 'LAST PULL: <rel> · INTEL (perplexity)'
      'EDITORIAL' → 'LAST PULL: <rel> · EDITORIAL (set <date>)'
      'BASELINE'  → 'BASELINE (no live read since <last_live_fetch>)'

    Returns the formatted string, or None when there is genuinely
    no information to show (so the card builder skips the line)."""
    if source_kind is None:
        return None
    if source_kind == "BASELINE":
        when = last_live_fetch or "no successful fetch this session"
        if isinstance(when, str) and "T" in when:
            when = when.split("T")[0]
        return f"BASELINE (no live read since {when})"
    rel = _relative_time(timestamp_iso)
    if source_kind == "EDITORIAL":
        set_on_str = editorial_set_on or "unknown"
        if isinstance(set_on_str, date) and not isinstance(set_on_str, datetime):
            set_on_str = set_on_str.isoformat()
        elif isinstance(set_on_str, str) and "T" in set_on_str:
            set_on_str = set_on_str.split("T")[0]
        return f"LAST PULL: {rel} · EDITORIAL (set {set_on_str})"
    if source_kind == "MARKET":
        return f"LAST PULL: {rel} · MARKET (yfinance)"
    if source_kind == "INTEL":
        return f"LAST PULL: {rel} · INTEL (perplexity)"
    # Unknown kind — don't fabricate.
    return None


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


def _normalize_enum(value, allowed):
    """v16 (Fix 1) — generic case-insensitive enum match used by the
    per-metric fan-out fetcher. Returns the canonical value from
    `allowed` or None when the input does not match.

    Supersedes the metric-specific _normalize_severity /
    _normalize_ban_status helpers but does not replace them — the
    legacy helpers stay so the v15.x single-call code path keeps
    working until Fix 6 (code hygiene) retires it."""
    if not isinstance(value, str) or not allowed:
        return None
    cleaned = value.strip()
    for candidate in allowed:
        if candidate.lower() == cleaned.lower():
            return candidate
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
        "asian_pp_spot_price_ton",
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


# ============================================================
# v16 (Fix 1) — per-metric fan-out fetcher
# ============================================================

def _build_per_metric_user_prompt(metric_key: str, spec: dict) -> str:
    """Compose the narrow neutral user prompt for a single metric.

    Pattern: <neutral question> · <primary-source list> · <fallback
    rule> · <return-shape contract>. No leading framing, no
    deck-anchoring language, no narrative."""
    sources_str = ", ".join(spec.get("primary_sources", []))
    expected = spec.get("expected_type", "string")
    enum_values = spec.get("enum_values", [])

    if expected == "number":
        contract = (
            'Return ONLY a JSON object {"value": <number>} or '
            '{"value": null} if you cannot source a primary '
            'reference from the last 7 days. Plain number, no '
            'currency symbol, no commas, no units inside the value. '
            'No prose, no markdown, no citations.'
        )
    elif expected == "percent":
        contract = (
            'Return ONLY a JSON object {"value": <number>} where the '
            'number is the percent (e.g. 25 means 25%) — or '
            '{"value": null} if you cannot source a primary '
            'reference from the last 7 days. No prose, no markdown, '
            'no citations.'
        )
    elif expected == "enum":
        valid = ", ".join(f'"{v}"' for v in enum_values)
        contract = (
            f'Return ONLY a JSON object {{"value": <one of {valid}>}} '
            f'or {{"value": null}} if you cannot determine from '
            f'primary sources. No prose, no markdown, no citations.'
        )
    else:  # string
        contract = (
            'Return ONLY a JSON object {"value": <string up to 200 '
            'chars>} or {"value": null} if you cannot source a '
            'primary reference from the last 7 days. No prose, no '
            'markdown, no citations.'
        )

    return (
        f'{spec["question"]} '
        f'Use primary references only: {sources_str}. '
        f'If no primary source within the last 7 days, return null. '
        f'Do not infer, extrapolate, or guess. {contract}'
    )


@st.cache_data(ttl=14400, show_spinner=False)
def fetch_intel_metric(metric_key: str, api_key: str) -> dict:
    """v16 (Fix 1) — single-metric narrow Perplexity call.

    Each metric is cached independently on the same 4-hour TTL so a
    single failing call never poisons the rest of the feed. Returns:

        {
            "value":        <coerced value or None>,
            "fetched_at":   ISO timestamp or None,
            "error":        None or short error string,
            "source_hint":  primary-source list (rendered to user),
            "raw":          raw LLM content (for the debug expander),
        }

    Caching is keyed on (metric_key, api_key). Both args are simple
    strings so the @st.cache_data wrapper hashes them cleanly."""
    spec = INTEL_METRICS.get(metric_key)
    sources_hint = (
        ", ".join(spec["primary_sources"])
        if spec and spec.get("primary_sources")
        else None
    )
    base = {
        "value": None,
        "fetched_at": None,
        "error": None,
        "source_hint": sources_hint,
        "raw": None,
    }

    if spec is None:
        base["error"] = f"unknown metric: {metric_key}"
        return base
    if not api_key:
        base["error"] = "no api key"
        return base

    user_prompt = _build_per_metric_user_prompt(metric_key, spec)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system",
             "content": PERPLEXITY_PER_METRIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
    }

    try:
        response = requests.post(
            PERPLEXITY_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        base["error"] = f"network: {exc}"
        return base

    if response.status_code != 200:
        base["error"] = (
            f"http {response.status_code}: {response.text[:160]}"
        )
        return base

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as exc:
        base["error"] = f"malformed response: {exc}"
        return base

    base["raw"] = content
    parsed = _extract_json_object(content)
    if parsed is None:
        base["error"] = "json parse failed"
        return base

    raw_value = parsed.get("value")
    expected = spec.get("expected_type", "string")

    if expected in ("number", "percent"):
        cleaned = _positive_or_none(_coerce_number(raw_value))
    elif expected == "enum":
        cleaned = _normalize_enum(raw_value, spec.get("enum_values", []))
    else:  # string
        cleaned = _normalize_status(raw_value) if raw_value else None

    base["value"] = cleaned
    base["fetched_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if cleaned is None:
        # Successful call, just no usable value — flag distinctly so
        # the freshness UI can tell "null answer" apart from "no
        # call made".
        base["error"] = "value was null"
    return base


def fetch_all_intel(api_key: str) -> dict:
    """v16 (Fix 1) — orchestrate the per-metric fan-out.

    Each metric in INTEL_METRICS is dispatched in parallel via a
    ThreadPoolExecutor (max_workers=10). Cache hits short-circuit
    inside `fetch_intel_metric` so warm reruns are essentially free.

    Returns:
        {
            "data":        {metric_key: cleaned_value or None},
            "metric_meta": {metric_key: per-call meta dict},
            "fetched_at":  ISO timestamp of this orchestration run,
        }

    The `data` dict mirrors the v15.x output shape exactly so the
    rest of the dashboard (engine, render, editorial overrides)
    keeps working unchanged."""
    fetched_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if not api_key:
        empty_meta = {
            k: {
                "value": None,
                "fetched_at": None,
                "error": "no api key",
                "source_hint": ", ".join(
                    INTEL_METRICS[k].get("primary_sources", [])
                ),
                "raw": None,
            }
            for k in INTEL_METRICS
        }
        return {
            "data": {k: None for k in INTEL_METRICS},
            "metric_meta": empty_meta,
            "fetched_at": fetched_at,
        }

    results = {}
    max_workers = min(10, len(INTEL_METRICS)) or 1
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="intel_fanout",
    ) as ex:
        futures = {
            ex.submit(fetch_intel_metric, key, api_key): key
            for key in INTEL_METRICS
        }
        for fut in concurrent.futures.as_completed(futures):
            key = futures[fut]
            try:
                results[key] = fut.result()
            except Exception as exc:
                results[key] = {
                    "value": None,
                    "fetched_at": None,
                    "error": f"future raised: {exc}",
                    "source_hint": ", ".join(
                        INTEL_METRICS[key].get("primary_sources", [])
                    ),
                    "raw": None,
                }

    data = {key: results[key]["value"] for key in INTEL_METRICS}
    return {
        "data": data,
        "metric_meta": results,
        "fetched_at": fetched_at,
    }


# ============================================================
# v16 (Fix 1) — Real-feed adapters
# ============================================================
# For metrics with deterministic public sources, prefer the real
# feed over Perplexity entirely. Each adapter returns a (value, tag)
# pair where `tag` describes the source — surfaced in the metric
# meta so the user can see whether a value came from a live tape, a
# derived calculation, or an LLM retrieval.

@st.cache_data(ttl=14400)
def fetch_urea_yfinance():
    """v18 Fix 2 — CME urea futures (UFV=F). Returns
    (value, fetched_at) tuple; value is None if the ticker isn't
    accessible. Caller falls back to Perplexity when value is None."""
    try:
        data = yf.Ticker("UFV=F").history(period="5d", interval="1d")
        if data.empty:
            return None, None
        return (
            float(data["Close"].iloc[-1]),
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    except Exception:
        return None, None


@st.cache_data(ttl=14400)
def fetch_diesel_yfinance():
    """v18 Fix 4 — NY Harbor ULSD heating-oil futures (HO=F),
    quoted in USD per gallon. Returns (price_per_bbl, fetched_at)
    so the crack-spread calculation is straightforward downstream:
    diesel_per_gal × 42 = diesel_per_bbl. Returns (None, None) if
    the ticker isn't accessible."""
    try:
        data = yf.Ticker("HO=F").history(period="5d", interval="1d")
        if data.empty:
            return None, None
        per_gal = float(data["Close"].iloc[-1])
        return (
            per_gal * 42.0,
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    except Exception:
        return None, None


def diesel_crack_per_bbl(diesel_per_bbl, brent_v):
    """v18 Fix 4 — diesel crack spread = diesel ($/bbl) − Brent
    ($/bbl). Returns None when either input is None. The crack is
    the canonical refining-margin signal for downstream consumer
    transmission; widens materially when product markets run
    tighter than crude."""
    if diesel_per_bbl is None or brent_v is None:
        return None
    return float(diesel_per_bbl) - float(brent_v)


def fetch_jet_fuel_derived(brent_v):
    """Derived from Brent crude. Jet (kerosene) typically trades at
    ~1.18x Brent on a $/bbl basis; convert to $/tonne via ~7.5
    barrels per tonne. Returns (value, tag) so the caller can stamp
    the metric meta with `derived from Brent`. None when Brent
    itself is unavailable."""
    if brent_v is None:
        return None, "unavailable"
    derived = float(brent_v) * 1.18 * 7.5
    return derived, "derived from Brent (~1.18× crude × 7.5 bbl/t)"


# ============================================================
# Fix C-3 — Editorial Layer
# ============================================================
# Every hand-set value lives here. No silent post-fetch mutation of
# intel_data or prices anywhere else. Each entry carries its own
# expiry; once the calendar passes `expires_on` the override falls
# off automatically and live data takes over. The UI surfaces the
# count of applied / expired / disagreeing overrides so the
# operator always knows what is hand-set vs what is live.
#
# Schema:
#   value           - the value to write to the target dict
#   set_on          - date the override was added
#   set_by          - human-readable owner (editorial team / brief)
#   rationale       - one-line reason
#   primary_source  - URL or descriptive citation (the only excuse
#                     for an override is a real source)
#   expires_on      - date past which the override is suppressed
#
# The target dict is resolved by key match: keys in INTEL_METRICS
# write to intel_data; keys in TICKERS write to prices. No need to
# embed routing info in the entry itself.

EDITORIAL_OVERRIDES = {
    "india_rice_ban_status": {
        "value": "INACTIVE",
        "set_on": date(2026, 4, 10),
        "set_by": "v15.4 brief (DGFT primary read)",
        "rationale":
            "DGFT Notification 07/2026-27 (April 10) liberalised "
            "rice exports to non-EU European countries by removing "
            "the Certificate of Inspection requirement. Sets the "
            "policy snapshot until the next DGFT update.",
        "primary_source":
            "https://apeda.gov.in/dgft-notifications",
        # Regulatory notifications turn over slowly — 90-day window.
        "expires_on": date(2026, 7, 10),
    },
    "malacca_severity": {
        "value": "nominal",
        "set_on": date(2026, 4, 28),
        "set_by": "v15.4 brief (FM Sugiono Apr 28 statement)",
        "rationale":
            "FM Sugiono publicly reaffirmed free passage on April 28; "
            "the transit-fee proposal that drove the v15.2 shadow "
            "tier was retracted as a thought-experiment.",
        "primary_source":
            "https://mykn.kuehne-nagel.com/news/",
        # Verbal political commitment — 30-day re-check window.
        "expires_on": date(2026, 5, 28),
    },
    "malacca_ships_waiting": {
        "value": 80,
        "set_on": date(2026, 4, 28),
        "set_by": "v15.4 brief",
        "rationale":
            "Anchor at the peace-time baseline so the shadow trigger "
            "(>15% above 80) does not fire while the FM Sugiono "
            "free-passage statement is current.",
        "primary_source":
            "https://mykn.kuehne-nagel.com/news/",
        "expires_on": date(2026, 5, 28),
    },
    "malacca_status": {
        "value": (
            "FM Sugiono (April 28) reaffirmed free passage; the "
            "transit fee proposal was a retracted thought-experiment. "
            "Traffic remains normal."
        ),
        "set_on": date(2026, 4, 28),
        "set_by": "v15.4 brief",
        "rationale":
            "Surfaces the FM Sugiono primary statement as the card "
            "detail line under the nominal severity.",
        "primary_source":
            "https://mykn.kuehne-nagel.com/news/",
        "expires_on": date(2026, 5, 28),
    },
    "hormuz_daily_transit_count": {
        "value": 4,
        "set_on": date(2026, 4, 28),
        "set_by": "v11-B brief",
        "rationale":
            "Strait of Hormuz at ~95% transit collapse following the "
            "blockade extension. US rejected the April 27 reopening "
            "offer. Override anchors the threshold engine until "
            "Lloyd's List / Kpler resume publishing live counts.",
        "primary_source":
            "v11-B brief — Hormuz transit collapse (Reuters Maritime, "
            "Lloyd's List press)",
        # Fast-moving geopolitical condition — 14-day re-check.
        "expires_on": date(2026, 5, 14),
    },
    "Gold": {
        "value": 4571.0,
        "set_on": date(2026, 4, 28),
        "set_by": "v15.2 brief (technical level)",
        "rationale":
            "Anchor on the $4,571 support level being tested after "
            "the break below the $4,660 ceiling. Live yfinance "
            "reads can drift around technical analysis levels; this "
            "override is a brief-time snapshot.",
        "primary_source":
            "https://www.bloomberg.com/markets/currencies/",
        # Technical level — 14-day re-check.
        "expires_on": date(2026, 5, 14),
    },
}


def _resolve_override_target(key, intel_data, prices):
    """Route a flat EDITORIAL_OVERRIDES key to the dict it should
    write into. INTEL_METRICS keys → intel_data; TICKERS keys →
    prices. Returns the target dict or None if the key matches
    neither — that's a misconfigured override and apply_editorial_
    layer will skip it with a log entry."""
    if key in INTEL_METRICS:
        return intel_data
    if key in TICKERS:
        return prices
    return None


# Fix C-5 — module-level facts with expiry. Parallel to
# EDITORIAL_OVERRIDES but for non-routable facts (the OECD breach
# bool, the EU ammonia capacity %). When their expiry passes the
# fact auto-falls-off and the engine defaults to a non-breach
# stance until live data resolves it. apply_editorial_facts()
# below reassigns the module globals.
EDITORIAL_FACTS = {
    "oecd_inventory_below_min": {
        "value": True,
        "set_on": date(2026, 4, 1),
        "set_by": "v11 brief",
        "rationale":
            "OECD commercial inventories confirmed below the 842 MB "
            "operational minimum; price has become the rationing "
            "mechanism rather than supply.",
        "primary_source":
            "EIA / IEA monthly oil market reports",
        # 14-day re-check window; if EIA / IEA monthly data eases,
        # this fact should expire and the engine reverts to live.
        "expires_on": date(2026, 5, 14),
    },
    "eu_ammonia_capacity_pct": {
        "value": 35.0,
        "set_on": date(2026, 4, 1),
        "set_by": "v11 brief",
        "rationale":
            "EU ammonia plant utilisation at ~35%, below the 40% "
            "food-grade CO2 byproduct threshold. Sub-threshold "
            "operation kills food-grade CO2 production.",
        "primary_source":
            "Fertilizer Europe / industry trade press",
        # 21-day re-check window — slower-moving than OECD fact.
        "expires_on": date(2026, 5, 21),
    },
    # v18 Fix 1b — Panama Neopanamax editorial fallback. ACP
    # publishes auction averages in batches every few weeks; on
    # days between releases this fact fills the gap so the card
    # doesn't sit STALE while a real number is sitting in the
    # last ACP press release. The `target_intel_key` field marks
    # this as a fallback into intel_data rather than a module
    # global; apply_editorial_facts handles the routing.
    "panama_neopanamax_avg_price": {
        "value": 385_000.0,
        "set_on": date(2026, 4, 26),
        "set_by": "v18 brief (ACP press release, April 2026)",
        "rationale":
            "ACP reported the average auction price climbed from "
            "~$140K pre-conflict to ~$385K between March and "
            "April 2026. Anchors the Panama card and the GRS "
            "Logistics cluster while ACP's next press release is "
            "awaited.",
        "primary_source":
            "https://pancanal.com (ACP press releases) — "
            "April 2026 reporting",
        "expires_on": date(2026, 5, 28),
        "target_intel_key": "panama_canal_neopanamax_price",
    },
}


# Fix C-5 — live intel cache used by physical-logic gates.
# helium_exhausted() consults this so the date math can be
# overridden by a live signal. Set by the call site after the
# fetch + editorial layer have run.
_LIVE_INTEL_DATA = {}


def apply_editorial_facts(today=None, intel_data=None,
                          intel_meta=None):
    """Fix C-5 — walk EDITORIAL_FACTS and reassign the module
    globals (OECD_INVENTORY_BREACH, EUROPEAN_AMMONIA_CAPACITY_PCT,
    CO2_BYPRODUCT_BREACH). Expired facts fall off automatically;
    the global defaults to a non-breach stance until live data
    arrives. Returns a log dict for the editorial UI panel.

    v18 Fix 1b — also handles "fallback" facts that target an
    intel_data key (`target_intel_key`). When a fallback fact has
    not expired AND the live intel value is None, the fact's
    value is written into intel_data and intel_meta so the card
    renders the editorial number with an EDITORIAL footer instead
    of going STALE."""
    today = today or date.today()
    log = {"applied": [], "expired": [], "evaluated_at": today.isoformat()}

    global OECD_INVENTORY_BREACH
    global EUROPEAN_AMMONIA_CAPACITY_PCT
    global CO2_BYPRODUCT_BREACH

    fact_oecd = EDITORIAL_FACTS.get("oecd_inventory_below_min")
    if fact_oecd:
        if fact_oecd["expires_on"] >= today:
            OECD_INVENTORY_BREACH = bool(fact_oecd["value"])
            log["applied"].append({
                "key": "oecd_inventory_below_min",
                "value": fact_oecd["value"],
                "expires_on": fact_oecd["expires_on"].isoformat(),
                "set_by": fact_oecd["set_by"],
                "rationale": fact_oecd["rationale"],
                "primary_source": fact_oecd["primary_source"],
            })
        else:
            # Expired — default to non-breach until live data
            # arrives; the engine will not assert OECD-driven Tail
            # Risk on stale evidence.
            OECD_INVENTORY_BREACH = False
            log["expired"].append({
                "key": "oecd_inventory_below_min",
                "expired_on": fact_oecd["expires_on"].isoformat(),
                "rationale": fact_oecd["rationale"],
            })

    fact_ammonia = EDITORIAL_FACTS.get("eu_ammonia_capacity_pct")
    if fact_ammonia:
        if fact_ammonia["expires_on"] >= today:
            EUROPEAN_AMMONIA_CAPACITY_PCT = float(fact_ammonia["value"])
            log["applied"].append({
                "key": "eu_ammonia_capacity_pct",
                "value": fact_ammonia["value"],
                "expires_on": fact_ammonia["expires_on"].isoformat(),
                "set_by": fact_ammonia["set_by"],
                "rationale": fact_ammonia["rationale"],
                "primary_source": fact_ammonia["primary_source"],
            })
        else:
            # Expired — default above the breach threshold so the
            # cascade nodes drop back to nominal until live data
            # confirms otherwise.
            EUROPEAN_AMMONIA_CAPACITY_PCT = 50.0
            log["expired"].append({
                "key": "eu_ammonia_capacity_pct",
                "expired_on": fact_ammonia["expires_on"].isoformat(),
                "rationale": fact_ammonia["rationale"],
            })

    # Always recompute the CO2 breach bool from the (possibly
    # reassigned) ammonia capacity vs the threshold.
    CO2_BYPRODUCT_BREACH = (
        EUROPEAN_AMMONIA_CAPACITY_PCT < EUROPEAN_AMMONIA_THRESHOLD_PCT
    )

    # v18 Fix 1b — fallback facts that target a specific intel_data
    # key. Only fire when (a) not expired AND (b) the live intel
    # value is None. Writes both the value into intel_data and
    # synthetic meta into intel_meta so the LAST PULL footer reads
    # EDITORIAL.
    for fact_key, fact in EDITORIAL_FACTS.items():
        target_key = fact.get("target_intel_key")
        if not target_key:
            continue
        expires = fact.get("expires_on")
        if intel_data is None:
            continue
        live_value = intel_data.get(target_key)
        if live_value is not None:
            # Live data wins — log nothing, no fallback fired.
            continue
        if expires is not None and expires < today:
            log["expired"].append({
                "key": fact_key,
                "target_intel_key": target_key,
                "expired_on": expires.isoformat(),
                "rationale": fact.get("rationale"),
            })
            continue
        intel_data[target_key] = fact["value"]
        if intel_meta is not None:
            set_on_str = fact["set_on"].isoformat() if isinstance(
                fact.get("set_on"), date,
            ) else (fact.get("set_on") or "")
            intel_meta.setdefault("metric_meta", {})[target_key] = {
                "value": fact["value"],
                "fetched_at": set_on_str,
                "error": None,
                "source_hint":
                    "editorial fallback: " + fact.get(
                        "primary_source", "n/a",
                    ),
                "raw": None,
                "editorial_fact_fallback": True,
            }
        log["applied"].append({
            "key": fact_key,
            "target_intel_key": target_key,
            "value": fact["value"],
            "expires_on":
                expires.isoformat() if expires else None,
            "set_by": fact.get("set_by"),
            "rationale": fact.get("rationale"),
            "primary_source": fact.get("primary_source"),
        })
    return log


def _values_disagree(live, override, tolerance=0.10):
    """Conservative disagreement check used by the editorial-log.
    Numbers compare with a relative tolerance (default 10%). Strings
    compare case-insensitive. Anything else uses == . `live` of None
    never disagrees (no live signal is no contradiction)."""
    if live is None:
        return False
    if isinstance(live, (int, float)) and isinstance(override, (int, float)):
        if override == 0:
            return live != 0
        return abs(live - override) / abs(override) > tolerance
    if isinstance(live, str) and isinstance(override, str):
        return live.strip().lower() != override.strip().lower()
    return live != override


def apply_realfeed_overlays(intel_data, intel_meta, prices):
    """Fix C-3 — overlays for deterministic public feeds. Pulled out
    of the call site so the post-fetch flow is exactly two named
    transformations: real-feed overlays, then editorial layer.

    Both functions mutate intel_data in place; intel_meta is updated
    so the per-metric provenance reflects the real-feed source. Live
    LLM data wins over derived approximations (jet fuel only fills
    when LLM returned None).

    Source-Dump support — when an overlay fires, the original
    Perplexity meta is preserved under a `pre_overlay` sub-key on
    the new meta record. This lets _build_source_dump distinguish
    "we shipped a yfinance value" from "we shipped a Perplexity
    value", which is the canonical bug-hunt question for the AI
    auditor."""
    metric_meta = intel_meta.setdefault("metric_meta", {})

    _urea_live, _urea_ts = fetch_urea_yfinance()
    if _urea_live is not None:
        _pre_urea = metric_meta.get("urea_spot_price_ton") or {}
        intel_data["urea_spot_price_ton"] = _urea_live
        metric_meta["urea_spot_price_ton"] = {
            "value": _urea_live,
            "fetched_at": _urea_ts or
                datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "error": None,
            "source_hint": "yfinance UFV=F (CME urea futures)",
            "raw": None,
            "pre_overlay": {
                "value": _pre_urea.get("value"),
                "fetched_at": _pre_urea.get("fetched_at"),
                "source_hint": _pre_urea.get("source_hint"),
                "error": _pre_urea.get("error"),
            },
        }

    _brent = prices.get("Brent")
    _jet_derived, _jet_tag = fetch_jet_fuel_derived(_brent)
    if (
        _jet_derived is not None
        and intel_data.get("jet_fuel_price_ton") is None
    ):
        _pre_jet = metric_meta.get("jet_fuel_price_ton") or {}
        intel_data["jet_fuel_price_ton"] = _jet_derived
        metric_meta["jet_fuel_price_ton"] = {
            "value": _jet_derived,
            "fetched_at":
                datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "error": None,
            "source_hint": _jet_tag,
            "raw": None,
            "pre_overlay": {
                "value": _pre_jet.get("value"),
                "fetched_at": _pre_jet.get("fetched_at"),
                "source_hint": _pre_jet.get("source_hint"),
                "error": _pre_jet.get("error"),
            },
        }


def apply_editorial_layer(intel_data, prices, today=None):
    """Fix C-3 — apply EDITORIAL_OVERRIDES with explicit logging.

    Walks the dict; for each entry:
      1. Skip if past `expires_on` and add to the `expired` log.
      2. Otherwise compare against the live value (if any) and add
         to the `disagree` log when they differ outside tolerance.
      3. Apply the override and add to the `applied` log with
         before/after values.

    Returns the editorial_log dict; mutates intel_data and prices
    in place. The UI surfaces the log via the editorial-layer
    panel so the operator sees exactly what's hand-set right now."""
    today = today or date.today()
    log = {
        "applied": [],
        "expired": [],
        "disagree": [],
        "skipped_unknown": [],
        "evaluated_at": today.isoformat(),
    }

    for key, override in EDITORIAL_OVERRIDES.items():
        expires = override.get("expires_on")
        target = _resolve_override_target(key, intel_data, prices)

        if target is None:
            log["skipped_unknown"].append({
                "key": key,
                "reason": "no matching dict (intel_data or prices)",
            })
            continue

        if expires is not None and expires < today:
            log["expired"].append({
                "key": key,
                "expired_on": expires.isoformat(),
                "value": override.get("value"),
                "rationale": override.get("rationale"),
            })
            continue

        live_value = target.get(key)
        before = live_value
        new_value = override.get("value")

        if _values_disagree(live_value, new_value):
            log["disagree"].append({
                "key": key,
                "live": live_value,
                "override": new_value,
                "rationale": override.get("rationale"),
                "primary_source": override.get("primary_source"),
            })

        target[key] = new_value
        log["applied"].append({
            "key": key,
            "before": before,
            "after": new_value,
            "set_on": override.get("set_on").isoformat()
                if override.get("set_on") else None,
            "set_by": override.get("set_by"),
            "rationale": override.get("rationale"),
            "primary_source": override.get("primary_source"),
            "expires_on": expires.isoformat() if expires else None,
        })

    return log


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

    # Fix C-5 — every upside rule now has a downside counterpart so
    # the matrix can drift in BOTH directions when the world moves.
    # The previous engine was strictly one-way: every threshold
    # pushed Tail Risk up, only `brent < 90` nudged Best Case up,
    # and Best Case was hard-pinned at 0%. With v11 starting weights
    # restored above and the symmetric rules below, an improving
    # commodity / logistics picture actually shows up in the matrix.
    if brent is not None and brent > 130:
        probs["Tail Risk"] += 10
        probs["Base Case"] -= 10
    elif brent is not None and brent > 115:
        probs["Tail Risk"] += 5
        probs["Base Case"] -= 5
    elif brent is not None and brent < 90:
        probs["Best Case"] += 5
        probs["Tail Risk"] -= 5
    elif brent is not None and brent < 95:
        # Mid-band easing — softer Best Case nudge.
        probs["Best Case"] += 3
        probs["Tail Risk"] -= 3

    if ttf is not None and ttf > 80:
        probs["Tail Risk"] += 8
        probs["Slow Normalization"] -= 4
        probs["Base Case"] -= 4
    elif ttf is not None and ttf > 65:
        probs["Tail Risk"] += 4
        probs["Base Case"] -= 4
    elif ttf is not None and ttf < 50:
        # TTF below the €52 baseline — gas market materially
        # easing. Push toward Slow Normalization.
        probs["Slow Normalization"] += 4
        probs["Tail Risk"] -= 4

    urea = intel.get("urea_spot_price_ton")
    if urea is not None and urea > 800:
        probs["Tail Risk"] += 6
        probs["Base Case"] -= 4
        probs["Best Case"] -= 2
    elif urea is not None and urea > 600:
        probs["Tail Risk"] += 3
        probs["Base Case"] -= 3
    elif urea is not None and urea < 500:
        # Urea well below the warning band — fertilizer-cost
        # pressure on food inflation eases.
        probs["Slow Normalization"] += 4
        probs["Tail Risk"] -= 4

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
    elif hormuz is not None and hormuz > 60:
        # Strait actively recovering toward peace-time throughput.
        probs["Best Case"] += 5
        probs["Tail Risk"] -= 5
    elif hormuz is not None and hormuz > 30:
        # Above the Tail trigger but not yet near peace-time.
        probs["Slow Normalization"] += 4
        probs["Tail Risk"] -= 4

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

    # Fix C-5 — symmetric tripwires for helium, resins, jet fuel.
    helium = intel.get("helium_spot_price_mcf")
    if helium is not None and helium > 2000:
        probs["Tail Risk"] += 4
        probs["Base Case"] += 4
        probs["Best Case"] -= 4
        probs["Slow Normalization"] -= 4
    elif helium is not None and helium < 1000:
        # Live helium spot has fallen back below $1,000/Mcf —
        # supply is plausibly recovering; push Slow Normalization.
        probs["Slow Normalization"] += 4
        probs["Tail Risk"] -= 4

    # Fix 3 — engine still thinks in spike-percent terms; compute
    # the spike from the absolute Asia PP spot price the data layer
    # now carries.
    resin_spike = pp_spike_pct(intel.get("asian_pp_spot_price_ton"))
    if resin_spike is not None and resin_spike > 40:
        probs["Base Case"] += 5
        probs["Best Case"] -= 3
        probs["Slow Normalization"] -= 2
    elif resin_spike is not None and resin_spike < 10:
        # Resin spike at near-baseline — petrochemical input
        # pressure on packaging / medical BOMs has eased.
        probs["Slow Normalization"] += 3
        probs["Tail Risk"] -= 3

    jet = intel.get("jet_fuel_price_ton")
    if jet is not None and jet > 1500:
        probs["Base Case"] += 4
        probs["Best Case"] -= 2
        probs["Slow Normalization"] -= 2
    elif jet is not None and jet < 1200:
        # Jet fuel below the warning band — aviation-arithmetic
        # stress relieved; air-freight rates can normalise.
        probs["Slow Normalization"] += 3
        probs["Tail Risk"] -= 3

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
    # Fix 3 — resin reframed: data layer carries the absolute Asia
    # PP spot price; the engine still cares about the spike % so we
    # compute it here.
    pp_price = intel.get("asian_pp_spot_price_ton")
    resin = pp_spike_pct(pp_price)
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
                      caption_key=None, caption_fmt=None,
                      last_fetched_at=None, source_hint=None,
                      source_footer=None, source_footer_kind=None):
    """Numeric card returning a single HTML string for the .intel-grid
    wrapper.

    Display rules:
      - If `value` is a real number, show it with the live delta vs
        baseline.
      - If `value` is None (Perplexity returned 0/null/missing) and
        `use_baseline_fallback` is True (default for intel cards), the
        card renders in a STALE state: dashed border, "NO LIVE DATA"
        headline, hatched STALE badge, and a meta line showing the
        last successful fetch + baseline reference + source hint.
        The card explicitly does NOT pretend the baseline is live.
      - If `value` is None and fallback is disabled, fall through to
        DATA UNAVAILABLE.

    The probability engine never sees the baseline — it operates on
    the raw `intel_data` dict where missing values are still None.
    Fallback is presentation-only.

    Status flags:
      `breach=True`   → .intel-card-breached (pulsing red glow)
      `warning=True`  → .intel-card-warning (static amber glow)
      neither         → plain glassmorphic card
    breach takes precedence if both are set.

    `sparkline_series` (v13) — optional 7-day price series. When
    provided, renders an inline SVG sparkline next to the headline
    value. Color picks up the breach/warning state automatically.

    Fix C-2 stale provenance:
      `last_fetched_at` — ISO timestamp of the most recent successful
                         fetch for this metric. Surfaced in the stale
                         meta line. None means "never fetched in this
                         session" (the most stale case).
      `source_hint`     — short string describing where a live read
                         would come from (e.g. "Argus, S&P Platts").
                         Shown in the stale meta line so the user
                         knows what source to chase up."""
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
        # Fix C-2 — render the stale state, not a baseline price
        # masquerading as live. The caption is forced to its 'stale'
        # variant so we never narrate nominal conditions over a card
        # with no real read.
        baseline_display = f"{currency}{fmt.format(baseline)}{suffix}"
        last_seen = (
            html.escape(last_fetched_at) if last_fetched_at
            else "no successful fetch this session"
        )
        source_str = (
            html.escape(source_hint) if source_hint
            else "see metric source-hint list"
        )
        title_attr = (
            f'Last successful fetch: {last_seen}. '
            f'Baseline reference: {baseline_display}. '
            f'Source: {source_str}.'
        )
        stale_caption_html = ""
        if caption_key:
            stale_text, stale_state = get_card_caption(
                caption_key, stale=True,
                **(caption_fmt or {}),
            )
            if stale_text:
                source_html = render_source_link_html(caption_key)
                stale_caption_html = (
                    f'<div class="intel-card-caption '
                    f'caption-{stale_state or "stale"}">'
                    f'<span class="caption-tag">STALE</span>'
                    f'{html.escape(stale_text)}'
                    f'{source_html}'
                    f'</div>'
                )
        # Stale path always emits a BASELINE footer line — auto-fill
        # if the call site didn't pass one.
        stale_footer_text = source_footer or _format_source_footer(
            "BASELINE", None, last_live_fetch=last_fetched_at,
        )
        stale_footer_html = ""
        if stale_footer_text:
            stale_footer_html = (
                f'<div class="intel-card-source-footer '
                f'source-baseline">'
                f'{html.escape(stale_footer_text)}</div>'
            )
        return (
            f'<div class="intel-card intel-card-stale" '
            f'title="{title_attr}">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-stale-headline">'
            f'NO LIVE DATA <span class="stale-badge">STALE</span>'
            f'</div>'
            f'<div class="intel-card-stale-meta">'
            f'<strong>Last fetch:</strong> {last_seen}<br>'
            f'<strong>Baseline ref:</strong> '
            f'{html.escape(baseline_display)}<br>'
            f'<strong>Source:</strong> {source_str}'
            f'</div>'
            f'{stale_caption_html}'
            f'{stale_footer_html}'
            f'</div>'
        )

    if value is None:
        unavail_footer_html = ""
        if source_footer:
            unavail_footer_html = (
                f'<div class="intel-card-source-footer '
                f'source-{(source_footer_kind or "").lower()}">'
                f'{html.escape(source_footer)}</div>'
            )
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value intel-card-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="intel-card-delta">&nbsp;</div>'
            f'{caption_html}'
            f'{unavail_footer_html}'
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

    footer_html = ""
    if source_footer:
        kind_class = (source_footer_kind or "market").lower()
        footer_html = (
            f'<div class="intel-card-source-footer '
            f'source-{kind_class}">'
            f'{html.escape(source_footer)}</div>'
        )

    return (
        f'<div class="{card_class}">'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'{value_block}'
        f'<div class="intel-card-delta {delta_class}">'
        f'{html.escape(delta_str)}</div>'
        f'{caption_html}'
        f'{footer_html}'
        f'</div>'
    )


def card_status_html(label, value_text, value_color, detail,
                     is_baseline=False, breach=False, warning=False,
                     caption_key=None, caption_fmt=None,
                     last_fetched_at=None, source_hint=None,
                     source_footer=None, source_footer_kind=None):
    """Qualitative card returning a single HTML string. value_text=None
    → DATA UNAVAILABLE (used only when no peace-time baseline applies).

    Fix C-2 — when `is_baseline` is True the card now renders in the
    STALE state instead of looking like a live nominal reading. The
    `(baseline)` tag pattern from earlier versions silently posed
    peace-time defaults as live readings; under v17 (Fix C-2) any
    baseline-only render is unmistakably stale.

    Status flags:
      `breach=True`  → .intel-card-breached pulsing red glow
      `warning=True` → .intel-card-warning static amber glow
    breach takes precedence if both are set.

    `caption_key` (v15.2) — optional key into CAPTION_TEXTS for the
    "Why & What" italic line below the detail.

    `last_fetched_at` / `source_hint` (Fix C-2) — surfaced in the
    stale meta line + tooltip so the operator knows what failed."""
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

    if is_baseline:
        # Fix C-2 — explicit STALE render. No mistaking the
        # peace-time default for a live nominal reading.
        last_seen = (
            html.escape(last_fetched_at) if last_fetched_at
            else "no successful fetch this session"
        )
        source_str = (
            html.escape(source_hint) if source_hint
            else (html.escape(detail) if detail else "")
        )
        baseline_summary = html.escape(value_text)
        title_attr = (
            f"Last successful fetch: {last_seen}. "
            f"Baseline reference: {baseline_summary}. "
            f"Source: {source_str or 'n/a'}."
        )
        stale_caption_html = ""
        if caption_key:
            stale_text, stale_state = get_card_caption(
                caption_key, stale=True,
                **(caption_fmt or {}),
            )
            if stale_text:
                source_html = render_source_link_html(caption_key)
                stale_caption_html = (
                    f'<div class="intel-card-caption '
                    f'caption-{stale_state or "stale"}">'
                    f'<span class="caption-tag">STALE</span>'
                    f'{html.escape(stale_text)}'
                    f'{source_html}'
                    f'</div>'
                )
        stale_footer_text = source_footer or _format_source_footer(
            "BASELINE", None, last_live_fetch=last_fetched_at,
        )
        stale_footer_html = ""
        if stale_footer_text:
            stale_footer_html = (
                f'<div class="intel-card-source-footer '
                f'source-baseline">'
                f'{html.escape(stale_footer_text)}</div>'
            )
        return (
            f'<div class="intel-card intel-card-stale" '
            f'title="{title_attr}">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-stale-headline">'
            f'NO LIVE DATA <span class="stale-badge">STALE</span>'
            f'</div>'
            f'<div class="intel-card-stale-meta">'
            f'<strong>Last fetch:</strong> {last_seen}<br>'
            f'<strong>Baseline ref:</strong> {baseline_summary}<br>'
            f'<strong>Source:</strong> '
            f'{source_str or "n/a"}'
            f'</div>'
            f'{stale_caption_html}'
            f'{stale_footer_html}'
            f'</div>'
        )
    color = html.escape(value_color or "#9ca3af")
    baseline_tag = ""  # legacy; live status cards never tag now
    detail_class = "intel-card-detail"
    # Inline border-color only fires when no breach/warning glow is
    # active — otherwise the glow's own border treatment takes over.
    if not (breach or warning):
        style_attr = f' style="border-color: {color};"'
    else:
        style_attr = ""
    footer_html = ""
    if source_footer:
        kind_class = (source_footer_kind or "intel").lower()
        footer_html = (
            f'<div class="intel-card-source-footer '
            f'source-{kind_class}">'
            f'{html.escape(source_footer)}</div>'
        )
    return (
        f'<div class="{base_class}"{style_attr}>'
        f'<div class="intel-card-label">{label_safe}</div>'
        f'<div class="intel-card-value" style="color: {color};">'
        f'● {html.escape(value_text)}{baseline_tag}</div>'
        f'<div class="{detail_class}">{detail_safe}</div>'
        f'{caption_html}'
        f'{footer_html}'
        f'</div>'
    )


# ============================================================
# Source Dump — full provenance ledger
# ============================================================
# Consolidates everything in memory after the data fetch + overlay
# layers + editorial layer + engine output into a single auditable
# dict. No new network calls. Designed so a downstream AI can spot
# bugs like "card claims live data but Perplexity returned null"
# just by reading the dump — without re-fetching.

def _classify_intel_source(metric_key, intel_data, intel_meta,
                           editorial_log):
    """Decide which `source_of_record` label applies to a given
    metric. The classification is a strict precedence ladder:

      1. editorial_override   — apply_editorial_layer set the value.
      2. yfinance_overlay     — apply_realfeed_overlays' urea path.
      3. brent_derived        — apply_realfeed_overlays' jet path.
      4. perplexity_live      — Perplexity returned a non-null value.
      5. stale_baseline_fallback — value is None but we have an
                                  INTEL_BASELINE entry (card renders
                                  STALE per Fix C-2).
      6. no_data              — no live read and no baseline."""
    for entry in editorial_log.get("applied", []):
        if entry["key"] == metric_key:
            return "editorial_override"
    meta = (intel_meta.get("metric_meta") or {}).get(metric_key) or {}
    if "pre_overlay" in meta:
        hint = (meta.get("source_hint") or "").lower()
        if "yfinance" in hint or "ufv=f" in hint:
            return "yfinance_overlay"
        if "derived" in hint:
            return "brent_derived"
        return "yfinance_overlay"  # default for any overlay
    if intel_data.get(metric_key) is not None:
        return "perplexity_live"
    if metric_key in INTEL_BASELINE:
        return "stale_baseline_fallback"
    return "no_data"


def _perplexity_raw_value(metric_key, intel_meta, editorial_log):
    """Return what Perplexity LITERALLY returned for this metric
    before any overlay or editorial override mutated it.

    Resolution order:
      - if real-feed overlay fired, the original meta is preserved
        under meta["pre_overlay"]["value"]
      - else if editorial override fired, the editorial_log's
        applied entry has `before` = post-fetch value (which is
        the Perplexity value when no overlay also ran)
      - else the meta's current `value` IS the raw value"""
    meta = (intel_meta.get("metric_meta") or {}).get(metric_key) or {}
    if "pre_overlay" in meta:
        return meta["pre_overlay"].get("value")
    for entry in editorial_log.get("applied", []):
        if entry["key"] == metric_key:
            return entry.get("before")
    return meta.get("value")


def _editorial_for_key(key, editorial_log):
    """Return the full applied-override dict for this key, or None
    if no override is active."""
    for entry in editorial_log.get("applied", []):
        if entry["key"] == key:
            return entry
    return None


def _build_source_dump(prices, intel_data, intel_meta, editorial_log,
                       editorial_facts_log, grs, adjusted, actions,
                       intel_grade, live_count, total_metrics,
                       api_key_configured, sparkline_series=None):
    """Pure function. Consolidates the in-memory state into a dict
    for the Source Dump panel. No network calls, no globals beyond
    read-only constants. Returns a dict; callers format it as
    Markdown or JSON."""
    sparkline_series = sparkline_series or {}

    # ----- 1. METADATA -----
    metadata = {
        "dashboard_version": (
            "v17 — Fix 1+2+3+4+5+A+B + Source Dump"
        ),
        "generated_at":
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "intel_grade": intel_grade,
        "intel_grade_fraction":
            f"{live_count}/{total_metrics} live",
        "live_count": live_count,
        "total_metrics": total_metrics,
        "api_key_configured": bool(api_key_configured),
    }

    # ----- 2. COMMODITY PRICES (yfinance) -----
    commodity_prices = {}
    for label, ticker in TICKERS.items():
        live_value = prices.get(label)
        baseline = BASELINE.get(label)
        delta_pct = None
        if (
            live_value is not None and baseline
            and baseline != 0
        ):
            delta_pct = round(
                (live_value - baseline) / baseline * 100.0, 2
            )
        override_entry = _editorial_for_key(label, editorial_log)
        source = "yfinance"
        if override_entry is not None:
            source = "editorial_override"
        commodity_prices[ticker] = {
            "ticker_symbol": ticker,
            "label": label,
            "current_value": live_value,
            "baseline_ref": baseline,
            "delta_vs_baseline_pct": delta_pct,
            "source": source,
            "fetched_at": "live cache 4h TTL",
            "sparkline_7d": sparkline_series.get(label) or [],
            "override_active": override_entry is not None,
            "override": override_entry,
        }

    # ----- 3. INTEL METRICS (Perplexity fan-out) -----
    intel_metrics_dump = {}
    for key in INTEL_METRICS:
        meta = (intel_meta.get("metric_meta") or {}).get(key) or {}
        displayed = intel_data.get(key)
        if displayed is None and key in INTEL_BASELINE:
            displayed_for_card = INTEL_BASELINE[key]
            stale = True
        else:
            displayed_for_card = displayed
            stale = False
        source_of_record = _classify_intel_source(
            key, intel_data, intel_meta, editorial_log,
        )
        raw_perplexity = _perplexity_raw_value(
            key, intel_meta, editorial_log,
        )
        override_entry = _editorial_for_key(key, editorial_log)
        intel_metrics_dump[key] = {
            "metric_key": key,
            "displayed_value": displayed_for_card,
            "stale_baseline_used": stale,
            "source_of_record": source_of_record,
            "fetched_at": meta.get("fetched_at"),
            "primary_source": meta.get("source_hint"),
            "perplexity_raw_value": raw_perplexity,
            "perplexity_error": meta.get("error"),
            "editorial_override": override_entry,
            "expected_type":
                INTEL_METRICS[key].get("expected_type"),
            "primary_sources_queried":
                INTEL_METRICS[key].get("primary_sources"),
        }

    # ----- 4. EDITORIAL LAYER -----
    editorial_layer = {
        "overrides": editorial_log,
        "facts": editorial_facts_log,
    }

    # ----- 5. PHYSICAL-LOGIC GATES -----
    helium_live_signal = (
        intel_data.get("helium_spot_price_mcf")
    )
    helium_days = helium_days_elapsed()
    physical_gates = {
        "helium_exhausted": {
            "value": helium_exhausted(),
            "days_elapsed_since_qatar_fm": helium_days,
            "boil_off_threshold_days": HELIUM_BOIL_OFF_DAYS,
            "live_signal_value": helium_live_signal,
            "live_signal_unit": "USD per Mcf",
            "source": (
                "live signal overrides date math (live < $1000)"
                if helium_live_signal is not None
                and helium_live_signal < 1000
                else "date math (no contradicting live signal)"
            ),
        },
        "oecd_inventory_breach": {
            "value": OECD_INVENTORY_BREACH,
            "operational_minimum_mb": OECD_INVENTORY_OPERATIONAL_MIN_MB,
            "source": _gate_source(
                "oecd_inventory_below_min", editorial_facts_log,
            ),
        },
        "co2_byproduct_breach": {
            "value": CO2_BYPRODUCT_BREACH,
            "european_ammonia_capacity_pct":
                EUROPEAN_AMMONIA_CAPACITY_PCT,
            "european_ammonia_threshold_pct":
                EUROPEAN_AMMONIA_THRESHOLD_PCT,
            "source": _gate_source(
                "eu_ammonia_capacity_pct", editorial_facts_log,
            ),
        },
        "european_ammonia_capacity_pct": {
            "value": EUROPEAN_AMMONIA_CAPACITY_PCT,
            "source": _gate_source(
                "eu_ammonia_capacity_pct", editorial_facts_log,
            ),
        },
    }

    # ----- 6. ENGINE OUTPUT -----
    drift = sum(
        abs(adjusted.get(k, 0.0) - BASE_PROBS.get(k, 0.0))
        for k in BASE_PROBS
    ) / 2.0 if adjusted else 0.0
    playbook = []
    for a in (actions or []):
        playbook.append({
            "level": a.get("level"),
            "trigger": a.get("trigger"),
            "business": a.get("business"),
            "household": a.get("household"),
        })
    engine_output = {
        "grs": grs,
        "scenario_probabilities": adjusted,
        "scenario_baseline": dict(BASE_PROBS),
        "drift_vs_baseline_pts": round(drift, 2),
        "playbook_triggers": playbook,
    }

    # ----- 7. SOURCE URL MANIFEST (reverse-mapped) -----
    url_manifest = {}
    for caption_key, url in SOURCE_URLS.items():
        url_manifest.setdefault(url, []).append(caption_key)
    # Stable ordering for reproducibility.
    for url in url_manifest:
        url_manifest[url] = sorted(url_manifest[url])

    return {
        "metadata": metadata,
        "commodity_prices": commodity_prices,
        "intel_metrics": intel_metrics_dump,
        "editorial_layer": editorial_layer,
        "physical_logic_gates": physical_gates,
        "engine_output": engine_output,
        "source_urls": url_manifest,
    }


def _gate_source(fact_key, facts_log):
    """Helper: classify a physical-logic gate's source by looking
    in the editorial-facts log."""
    if not facts_log:
        return "constant (no facts log)"
    for f in facts_log.get("applied", []):
        if f.get("key") == fact_key:
            return (
                f"editorial fact (set {f.get('set_by')}, expires "
                f"{f.get('expires_on')})"
            )
    for f in facts_log.get("expired", []):
        if f.get("key") == fact_key:
            return (
                f"expired editorial fact (was: "
                f"expires {f.get('expired_on')}); defaulted"
            )
    return "constant"


def _format_source_dump_json(dump):
    """Pretty JSON for the AI-audit tab. Single st.code block can
    be copied with the Streamlit one-click clipboard icon."""
    return json.dumps(dump, indent=2, default=str)


def _format_source_dump_markdown(dump):
    """Render the same dump as readable Markdown. Editorial
    overrides 🟠, stale ⚪, no-data ⚫."""
    md = []
    meta = dump.get("metadata", {})
    md.append("## 📋 Source Dump — provenance ledger")
    md.append("")
    md.append(f"- **Generated:** `{meta.get('generated_at')}`")
    md.append(
        f"- **Intel Grade:** `{meta.get('intel_grade')} "
        f"({meta.get('intel_grade_fraction')})`"
    )
    md.append(
        f"- **API key configured:** "
        f"`{meta.get('api_key_configured')}`"
    )
    md.append(
        f"- **Dashboard version:** "
        f"`{meta.get('dashboard_version')}`"
    )
    md.append("")

    md.append("### 1. Commodity Prices (yfinance)")
    md.append("")
    for ticker, row in dump.get("commodity_prices", {}).items():
        flag = "🟠" if row.get("override_active") else ""
        md.append(
            f"- {flag} **{row['label']}** (`{ticker}`): "
            f"`{row['current_value']}` "
            f"(baseline `{row['baseline_ref']}`, "
            f"Δ `{row['delta_vs_baseline_pct']}%`) "
            f"— source: `{row['source']}`"
        )
        if row.get("override_active") and row.get("override"):
            ov = row["override"]
            md.append(
                f"    - 🟠 **Editorial override:** "
                f"value `{ov.get('after')}` (was "
                f"`{ov.get('before')}`), set "
                f"{ov.get('set_on')} by "
                f"{ov.get('set_by')}, expires "
                f"{ov.get('expires_on')}"
            )
            md.append(
                f"    - Rationale: *{ov.get('rationale')}*"
            )
            md.append(
                f"    - Source: {ov.get('primary_source')}"
            )
    md.append("")

    md.append("### 2. Intel Metrics (Perplexity fan-out)")
    md.append("")
    for key, row in dump.get("intel_metrics", {}).items():
        sor = row["source_of_record"]
        if sor == "editorial_override":
            flag = "🟠"
        elif sor == "stale_baseline_fallback":
            flag = "⚪"
        elif sor == "no_data":
            flag = "⚫"
        elif sor in ("yfinance_overlay", "brent_derived"):
            flag = "🟢"
        else:
            flag = "✅"
        md.append(
            f"- {flag} **{key}**: displayed "
            f"`{row['displayed_value']}` — "
            f"source `{sor}`"
        )
        md.append(
            f"    - Perplexity raw value: "
            f"`{row['perplexity_raw_value']}` · "
            f"fetched_at: `{row['fetched_at']}`"
        )
        if row.get("perplexity_error"):
            md.append(
                f"    - Perplexity error: "
                f"`{row['perplexity_error']}`"
            )
        md.append(
            f"    - Primary sources queried: "
            f"`{row.get('primary_sources_queried')}`"
        )
        if row.get("editorial_override"):
            ov = row["editorial_override"]
            md.append(
                f"    - 🟠 **Override:** `{ov.get('after')}` "
                f"(was `{ov.get('before')}`), expires "
                f"{ov.get('expires_on')}"
            )
            md.append(
                f"      Rationale: *{ov.get('rationale')}* · "
                f"Source: {ov.get('primary_source')}"
            )
    md.append("")

    md.append("### 3. Editorial Layer")
    md.append("")
    ov_log = dump.get("editorial_layer", {}).get("overrides", {})
    md.append(
        f"- **Active overrides:** "
        f"{len(ov_log.get('applied', []))}"
    )
    md.append(
        f"- **Expired overrides:** "
        f"{len(ov_log.get('expired', []))}"
    )
    md.append(
        f"- **Disagreeing with live data:** "
        f"{len(ov_log.get('disagree', []))}"
    )
    fa_log = dump.get("editorial_layer", {}).get("facts", {})
    md.append(
        f"- **Active facts:** {len(fa_log.get('applied', []))}, "
        f"**Expired:** {len(fa_log.get('expired', []))}"
    )
    md.append("")

    md.append("### 4. Physical-Logic Gates")
    md.append("")
    for gname, gd in dump.get("physical_logic_gates", {}).items():
        md.append(f"- **{gname}**: `{gd.get('value')}`")
        md.append(f"    - Source: *{gd.get('source')}*")
        for k, v in gd.items():
            if k in ("value", "source"):
                continue
            md.append(f"    - {k}: `{v}`")
    md.append("")

    md.append("### 5. Engine Output")
    md.append("")
    eo = dump.get("engine_output", {})
    md.append(f"- **GRS overall:** `{eo.get('grs', {}).get('overall')}`")
    grs_d = eo.get("grs", {})
    md.append(
        f"    - Commodity: `{grs_d.get('commodity')}` · "
        f"Logistics: `{grs_d.get('logistics')}` · "
        f"Buffers: `{grs_d.get('buffers')}`"
    )
    md.append(
        f"- **Scenario probabilities:** "
        f"`{eo.get('scenario_probabilities')}`"
    )
    md.append(
        f"- **Drift vs baseline:** "
        f"`{eo.get('drift_vs_baseline_pts')} pts`"
    )
    md.append(
        f"- **Active playbook triggers:** "
        f"{len(eo.get('playbook_triggers', []))}"
    )
    for pt in eo.get("playbook_triggers", []):
        md.append(
            f"    - [{pt.get('level','').upper()}] "
            f"{pt.get('trigger')}"
        )
    md.append("")

    md.append("### 6. Source URL Manifest")
    md.append("")
    for url, keys in dump.get("source_urls", {}).items():
        md.append(f"- **{url}** → `{keys}`")
    md.append("")
    return "\n".join(md)


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
# v18 Fix 2 — fetch_price now returns (value, fetched_at). Unpack
# into parallel `prices` (floats, unchanged downstream contract) and
# `prices_ts` (timestamps used by the LAST PULL footer).
with st.spinner("Pulling live commodity feed..."):
    prices = {}
    prices_ts = {}
    for _name, _tk in TICKERS.items():
        _val, _ts = fetch_price(_tk)
        prices[_name] = _val
        prices_ts[_name] = _ts

# v18 Fix 4 — diesel HO=F fetched alongside the other commodity
# tickers. Stored as $/bbl so the crack-spread math is direct.
with st.spinner("Pulling diesel futures (HO=F)..."):
    _diesel_per_bbl, _diesel_ts = fetch_diesel_yfinance()
diesel_crack_v = diesel_crack_per_bbl(
    _diesel_per_bbl, prices.get("Brent"),
)

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

# v16 (Fix 1) — fan-out parallel intel fetch. Replaces the v15.x
# single-call ten-field prompt with one narrow neutral Perplexity
# call per metric, dispatched concurrently. Each metric is cached
# independently so a single failing metric does not poison the
# whole feed. Real-feed adapters (yfinance UFV=F for urea,
# Brent-derived jet fuel) overlay the LLM result where a public
# deterministic source is available.
with st.spinner(
    "Querying primary intelligence sources (parallel fan-out)..."
):
    intel_result = fetch_all_intel(api_key)

intel_data = dict(intel_result.get("data") or {})
intel_meta = {
    "fetched_at": intel_result.get("fetched_at"),
    "metric_meta": intel_result.get("metric_meta") or {},
    # `raw` keeps the same key so the existing debug expander wires
    # do not break. Render the structured per-metric payload
    # (value + source_hint + error) as pretty JSON so the operator
    # can audit exactly what each call returned.
    "raw": json.dumps(
        {
            k: {
                "value": m.get("value"),
                "fetched_at": m.get("fetched_at"),
                "error": m.get("error"),
                "source_hint": m.get("source_hint"),
            }
            for k, m in (intel_result.get("metric_meta") or {}).items()
        },
        indent=2,
        default=str,
    ),
    "error": (
        None if api_key else "Perplexity intel paused — no API key."
    ),
}

# Fix C-3 — explicit, named transformations of the post-fetch
# data. There are exactly two:
#
#   1. Real-feed overlays (yfinance UFV=F for urea, Brent-derived
#      jet fuel) — public deterministic sources that improve on
#      LLM retrieval where available.
#   2. Editorial layer — every hand-set value lives in
#      EDITORIAL_OVERRIDES with a primary source + expiry. The
#      `editorial_log` returned here drives the UI panel that
#      surfaces what's hand-set vs live.
#
# No silent post-fetch mutation of intel_data or prices anywhere
# else in the file. All overrides flow through these two
# functions and are auditable by the operator.
apply_realfeed_overlays(intel_data, intel_meta, prices)

# v18 Fix 4 — wire the diesel crack into intel_data so grs_compute,
# the source dump, and the threshold monitor all see it. Source is
# yfinance HO=F − Brent; surfaced with a derived source_hint.
if diesel_crack_v is not None:
    intel_data["diesel_crack_per_bbl"] = diesel_crack_v
    intel_meta.setdefault("metric_meta", {})[
        "diesel_crack_per_bbl"
    ] = {
        "value": diesel_crack_v,
        "fetched_at": _diesel_ts or
            datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": None,
        "source_hint":
            "yfinance HO=F − Brent (NY Harbor ULSD crack spread)",
        "raw": None,
    }

editorial_log = apply_editorial_layer(intel_data, prices)
editorial_facts_log = apply_editorial_facts(
    intel_data=intel_data,
    intel_meta=intel_meta,
)

# Fix C-5 — populate the live-intel cache so helium_exhausted()
# (and any other downstream gate that consults live signals) sees
# the post-fetch + post-editorial state. Mutating the existing
# dict in place keeps any imported references valid.
_LIVE_INTEL_DATA.clear()
_LIVE_INTEL_DATA.update(intel_data)

# Scenario probabilities + Global Resilience Score computed once for
# the consolidated snapshot so every section is internally consistent.
adjusted = adjust_probabilities(prices, intel_data, equity_changes)

# v15.5 — GRS is now self-calculating. The v15.2 hardcoded
# `GRS_OVERRIDE_PCT = 38.0` has been removed so the headline score
# reflects what the three clusters (Commodities, Logistics, Buffers)
# actually report on the live snapshot. Under current truth-anchor
# state — buffers at 0% (Helium exhausted, CO2 byproduct exhausted,
# OECD inv breach), Hormuz at 4 ships/day, plus live commodity
# pricing — the engine naturally lands in the Structural Failure
# tier without any "fear-based" hardcoding.
grs = grs_compute(prices, intel_data)

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
# Fix C-4 — Intel Grade is now driven by the actual live-fraction
# of intel metrics + the count of active editorial overrides, not
# by the API-key check. Three states:
#
#   LIVE     — >= 80% of intel metrics returned a live value AND
#              <= 1 editorial override is currently masking live
#              data ("masking" = an override applied where a live
#              value also came in but disagreed).
#   MIXED    — 50–79% live, OR there are active editorial overrides
#   DEGRADED — < 50% live values
#
# The badge surfaces both the tier and the literal fraction so the
# operator never has to guess how much of the dashboard is real.
_metric_meta_for_grade = (intel_meta.get("metric_meta") or {})
_total_metrics = len(_metric_meta_for_grade) or 1
_live_count = sum(
    1 for m in _metric_meta_for_grade.values()
    if m.get("value") is not None
)
_live_fraction = _live_count / _total_metrics
_active_overrides = len(editorial_log.get("applied", []))
_masking_count = len(editorial_log.get("disagree", []))

if not api_key:
    _intel_grade = "STANDBY"
    _grade_class = "intel-degraded"
elif _live_fraction >= 0.80 and _active_overrides <= 1:
    # LIVE only when nearly all metrics returned a live value AND
    # at most one editorial override is currently doing work. The
    # `_masking_count` (overrides that disagree with live data) is
    # counted as a separate signal in the editorial log; the LIVE
    # tier rejects it implicitly via the active-override gate.
    _intel_grade = "LIVE"
    _grade_class = "intel-live"
elif _live_fraction >= 0.50 or _active_overrides > 0:
    _intel_grade = "MIXED"
    _grade_class = "intel-mixed"
else:
    _intel_grade = "DEGRADED"
    _grade_class = "intel-degraded"

st.markdown(
    f'<div class="hud-subtitle">'
    f'Strategic Logistics &amp; Resource Intelligence '
    f'&nbsp;|&nbsp; Intel Grade: '
    f'<span class="{_grade_class}">{_intel_grade} '
    f'({_live_count}/{_total_metrics} live)</span>'
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

# ---------- v15.3 STRATEGIC PLANNING & ACTION ----------
# Sits directly below Strategic Outlook so the operator sees the
# narrative scenario, then the concrete actions to take *now* given
# whatever the dashboard is reading as RED or AMBER. The fired list
# is rebuilt every page load from the live snapshot.
_sp_brent = prices.get("Brent")
_sp_brent_breach = (
    (_sp_brent is not None and _sp_brent > 115)
    or OECD_INVENTORY_BREACH
)
strategic_actions = build_strategic_actions(
    prices, intel_data, _sp_brent_breach,
)
st.markdown(
    '<h3 class="hud-title">◆ Strategic Planning &amp; Action</h3>',
    unsafe_allow_html=True,
)
if strategic_actions:
    _sp_cards = []
    for _a in strategic_actions:
        _lvl = _a["level"]  # 'critical' | 'warning'
        _tag_label = "CRITICAL" if _lvl == "critical" else "WARNING"
        _sp_cards.append(
            f'<div class="strategic-action-card sa-{_lvl}">'
            f'<span class="sa-tag">{_tag_label}</span>'
            f'<div class="sa-metric">'
            f'{html.escape(_a["metric"])}</div>'
            f'<div class="sa-headline">'
            f'{html.escape(_a["headline"])}</div>'
            f'<div class="sa-body">'
            f'{html.escape(_a["body"])}</div>'
            f'</div>'
        )
    st.markdown(
        '<div class="strategic-action-grid">'
        + "".join(_sp_cards)
        + '</div>',
        unsafe_allow_html=True,
    )
    _crit_count = sum(
        1 for _a in strategic_actions if _a["level"] == "critical"
    )
    _warn_count = sum(
        1 for _a in strategic_actions if _a["level"] == "warning"
    )
    st.markdown(
        f'<div class="status-strip">PLANNING POSTURE: '
        f'<span style="color:#ff4b4b;">{_crit_count} CRITICAL</span> '
        f'&nbsp;·&nbsp; '
        f'<span style="color:#ffa500;">{_warn_count} WARNING</span> '
        f'&nbsp;|&nbsp; Actions are derived from live RED / AMBER '
        f'metrics and refresh on every page load.</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="alert-ok">● ALL CLEAR — no metric is currently '
        'in a RED or AMBER state. Continue routine monitoring; the '
        'Threshold Monitor below remains armed.</div>',
        unsafe_allow_html=True,
    )
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
                     caption_key=None, source_footer=None,
                     source_footer_kind=None):
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

    footer_html = ""
    if source_footer:
        kind_class = (source_footer_kind or "market").lower()
        footer_html = (
            f'<div class="intel-card-source-footer '
            f'source-{kind_class}">'
            f'{html.escape(source_footer)}</div>'
        )

    if price is None and change is None:
        return (
            f'<div class="intel-card">'
            f'<div class="intel-card-label">{label_safe}</div>'
            f'<div class="intel-card-value intel-card-unavail">'
            f'DATA UNAVAILABLE</div>'
            f'<div class="intel-card-delta">proxy: {proxy_safe}</div>'
            f'{context_html}'
            f'{footer_html}'
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
        f'{footer_html}'
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
# Fix 3 — resin data layer now carries the absolute Asia PP price.
# Compute the spike % at render time so the existing card UI
# ("RESIN > 40%") keeps working with no other changes.
pp_price_v = intel_data.get("asian_pp_spot_price_ton")
resin_v = pp_spike_pct(pp_price_v)
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

    # Fix 2d — per-card "LAST PULL" footer routing.
    # _market_footer: yfinance ticker → MARKET footer with the
    #   actual cache fetch timestamp, OR EDITORIAL when an override
    #   is in force for this label (e.g. Gold).
    # _intel_footer: per-metric key → INTEL footer using the
    #   intel_meta fetched_at, MARKET when an overlay populated
    #   the value (yfinance UFV=F, Brent-derived), EDITORIAL when
    #   apply_editorial_layer set the value, BASELINE when the
    #   value is None and the card will render STALE.
    def _market_footer(label, ticker):
        for ov in editorial_log.get("applied", []):
            if ov["key"] == label:
                return (
                    _format_source_footer(
                        "EDITORIAL",
                        timestamp_iso=ov.get("set_on"),
                        editorial_set_on=ov.get("set_on"),
                    ),
                    "editorial",
                )
        # v18 Fix 2 — read fetched_at from the parallel prices_ts
        # dict that the v18 fetch_price tuple-return now populates.
        ts = prices_ts.get(label)
        return (_format_source_footer("MARKET", ts), "market")

    def _intel_footer(metric_key):
        for ov in editorial_log.get("applied", []):
            if ov["key"] == metric_key:
                return (
                    _format_source_footer(
                        "EDITORIAL",
                        timestamp_iso=ov.get("set_on"),
                        editorial_set_on=ov.get("set_on"),
                    ),
                    "editorial",
                )
        meta = (intel_meta.get("metric_meta") or {}).get(
            metric_key
        ) or {}
        if meta.get("value") is None:
            return (
                _format_source_footer(
                    "BASELINE", None,
                    last_live_fetch=meta.get("fetched_at"),
                ),
                "baseline",
            )
        hint = (meta.get("source_hint") or "").lower()
        if "yfinance" in hint or "ufv=f" in hint or "derived" in hint:
            return (
                _format_source_footer(
                    "MARKET", meta.get("fetched_at"),
                ),
                "market",
            )
        return (
            _format_source_footer(
                "INTEL", meta.get("fetched_at"),
            ),
            "intel",
        )

    _brent_footer, _brent_footer_kind = _market_footer("Brent", "BZ=F")
    _ttf_footer, _ttf_footer_kind = _market_footer("TTF", "TTF=F")
    _gold_footer, _gold_footer_kind = _market_footer("Gold", "GC=F")
    _silver_footer, _silver_footer_kind = _market_footer("Silver", "SI=F")

    commodity_cards = [
        card_numeric_html(
            "BRENT CRUDE  (BZ=F)", brent_v, BASELINE["Brent"],
            "$", True, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=brent_breach,
            warning=_brent_warn,
            sparkline_series=sparkline_series.get("Brent"),
            caption_key="brent",
            source_footer=_brent_footer,
            source_footer_kind=_brent_footer_kind,
        ),
        card_numeric_html(
            "TTF GAS  (TTF=F)", ttf_v, BASELINE["TTF"],
            "€", True, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=_ttf_breach,
            warning=_ttf_warn,
            sparkline_series=sparkline_series.get("TTF"),
            caption_key="ttf",
            source_footer=_ttf_footer,
            source_footer_kind=_ttf_footer_kind,
        ),
        # v18 Fix 4 — Diesel crack spread card. Sits under TTF in
        # the Commodity Telemetry strip so the downstream-product
        # tightness sits next to the upstream gas signal it
        # complements. Baseline 25 / critical 50 in $/bbl.
        card_numeric_html(
            "DIESEL CRACK SPREAD  ($/bbl)",
            diesel_crack_v,
            25.0,
            "$", True, fmt="{:,.1f}", delta_decimals=1,
            use_baseline_fallback=False,
            breach=(
                diesel_crack_v is not None
                and diesel_crack_v > 50
            ),
            warning=(
                diesel_crack_v is not None
                and 35 < diesel_crack_v <= 50
            ),
            caption_key="diesel_crack",
            last_fetched_at=_diesel_ts,
            source_hint="yfinance HO=F − Brent (NY Harbor ULSD)",
            source_footer=_format_source_footer(
                "MARKET", _diesel_ts,
            ),
            source_footer_kind="market",
        ),
        card_numeric_html(
            "GOLD  (GC=F)", gold_v, BASELINE["Gold"],
            "$", False, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=gold_v is not None and gold_v > 4600,
            warning=_gold_warn,
            sparkline_series=sparkline_series.get("Gold"),
            caption_key="gold",
            source_footer=_gold_footer,
            source_footer_kind=_gold_footer_kind,
        ),
        card_numeric_html(
            "SILVER  (SI=F)", silver_v, BASELINE["Silver"],
            "$", False, fmt="{:,.2f}", delta_decimals=2,
            use_baseline_fallback=False,
            breach=silver_v is not None and silver_v > 75,
            warning=_silver_warn,
            sparkline_series=sparkline_series.get("Silver"),
            caption_key="silver",
            source_footer=_silver_footer,
            source_footer_kind=_silver_footer_kind,
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
    def _equity_footer(equity_ticker_key):
        # v18 Fix 2 — read fetched_at from the snapshot dict, which
        # fetch_equity_snapshot now populates inside the cache.
        snap = equity_snapshots.get(equity_ticker_key) or {}
        ts = snap.get("fetched_at")
        return _format_source_footer("MARKET", ts), "market"

    equity_cards = []
    for key in EQUITY_TICKERS:
        eq_footer, eq_kind = _equity_footer(key)
        equity_cards.append(card_equity_html(
            key, equity_snapshots[key],
            sparkline_series=sparkline_series.get(key),
            caption_key=_equity_caption_keys.get(key),
            source_footer=eq_footer,
            source_footer_kind=eq_kind,
        ))
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

    # Fix C-2 — pull last_fetched_at + source_hint out of intel_meta
    # so the stale tooltip can surface real provenance for any card
    # that ends up rendering NO LIVE DATA.
    # Fix 2d — also produce the per-card "LAST PULL" footer kwargs
    # so every intel card carries a freshness line.
    def _meta_kwargs(metric_key):
        meta_record = (
            (intel_meta.get("metric_meta") or {}).get(metric_key)
            or {}
        )
        # Routing for the footer label is the same logic the source
        # dump uses for source_of_record — kept in sync here.
        editorial_match = None
        for ov in editorial_log.get("applied", []):
            if ov["key"] == metric_key:
                editorial_match = ov
                break
        if editorial_match is not None:
            footer_text = _format_source_footer(
                "EDITORIAL",
                timestamp_iso=editorial_match.get("set_on"),
                editorial_set_on=editorial_match.get("set_on"),
            )
            footer_kind = "editorial"
        elif meta_record.get("value") is None:
            footer_text = _format_source_footer(
                "BASELINE", None,
                last_live_fetch=meta_record.get("fetched_at"),
            )
            footer_kind = "baseline"
        else:
            hint = (meta_record.get("source_hint") or "").lower()
            if (
                "yfinance" in hint or "ufv=f" in hint
                or "derived" in hint
            ):
                footer_text = _format_source_footer(
                    "MARKET", meta_record.get("fetched_at"),
                )
                footer_kind = "market"
            else:
                footer_text = _format_source_footer(
                    "INTEL", meta_record.get("fetched_at"),
                )
                footer_kind = "intel"
        return {
            "last_fetched_at": meta_record.get("fetched_at"),
            "source_hint": meta_record.get("source_hint"),
            "source_footer": footer_text,
            "source_footer_kind": footer_kind,
        }

    intel_cards.append(card_numeric_html(
        "PANAMA NEOPANAMAX  (slot $)",
        panama_v,
        INTEL_BASELINE["panama_canal_neopanamax_price"],
        "$", True, fmt="{:,.0f}",
        breach=_panama_breach,
        warning=_panama_warn,
        caption_key="panama",
        **_meta_kwargs("panama_canal_neopanamax_price"),
    ))
    intel_cards.append(card_numeric_html(
        "UREA SPOT  ($/ton)",
        urea_v,
        INTEL_BASELINE["urea_spot_price_ton"],
        "$", True, fmt="{:,.0f}",
        breach=_urea_breach,
        warning=_urea_warn,
        caption_key="urea",
        **_meta_kwargs("urea_spot_price_ton"),
    ))
    # v15.3 — Hormuz under blockade. When the live transit count is
    # at or below 4 ships/day (95%+ collapse), render as a status
    # panel with the prominent "~4 SHIPS/DAY" headline rather than
    # the numeric card. The threshold engine still sees the raw
    # value upstream, so probability + GRS calculations are unchanged.
    if hormuz_v is not None and hormuz_v <= 4:
        intel_cards.append(card_status_html(
            "HORMUZ TRANSITS",
            f"🔴 CRITICAL: ~{hormuz_v:.0f} SHIPS/DAY",
            "#ff4b4b",
            "Blockade persists; ~4 ships/day (95% collapse). "
            "US rejection of April 27th reopening offer confirmed. "
            "Crude/LNG flow rerouting via Cape; war-risk insurance "
            "premia spiking globally.",
            breach=True,
            caption_key="hormuz",
            **_meta_kwargs("hormuz_daily_transit_count"),
        ))
    else:
        intel_cards.append(card_numeric_html(
            "HORMUZ TRANSITS  (ships/day)",
            hormuz_v,
            INTEL_BASELINE["hormuz_daily_transit_count"],
            "", False, fmt="{:.0f}",
            breach=_hormuz_breach,
            warning=_hormuz_warn,
            caption_key="hormuz",
            **_meta_kwargs("hormuz_daily_transit_count"),
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
    # v15.4 truth anchor — when the data layer reports NOMINAL with
    # the FM Sugiono free-passage briefing, render with the explicit
    # "🟢 NOMINAL (Free Passage)" headline so the operator sees the
    # primary-source state at a glance.
    _malacca_v154_nominal = (
        malacca_sev == "nominal"
        and not shadow_active
        and malacca_status
    )
    if malacca_sev == "critical":
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            "CRITICAL",
            SEVERITY_COLORS["critical"],
            malacca_status or "(no status text returned)",
            breach=True,
            caption_key="malacca",
            **_meta_kwargs("malacca_severity"),
        ))
    elif _malacca_v154_nominal:
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            "🟢 NOMINAL (Free Passage)",
            SEVERITY_COLORS["nominal"],
            malacca_status,
            caption_key="malacca",
            **_meta_kwargs("malacca_severity"),
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
            **_meta_kwargs("malacca_severity"),
        ))
    elif malacca_sev is None and malacca_status is None:
        intel_cards.append(card_status_html(
            "MALACCA STATUS",
            MALACCA_BASELINE_SEVERITY.upper(),
            SEVERITY_COLORS.get(MALACCA_BASELINE_SEVERITY, "#9ca3af"),
            MALACCA_BASELINE_STATUS,
            is_baseline=True,
            caption_key="malacca",
            **_meta_kwargs("malacca_severity"),
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
            **_meta_kwargs("malacca_severity"),
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
            **_meta_kwargs("helium_spot_price_mcf"),
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
            **_meta_kwargs("helium_spot_price_mcf"),
        ))

    # CO2 card is backed by the EUROPEAN_AMMONIA_CAPACITY_PCT editorial
    # FACT (not an intel metric), so the footer reads its set_on date
    # straight from EDITORIAL_FACTS rather than going through
    # _meta_kwargs.
    _co2_fact = EDITORIAL_FACTS.get("eu_ammonia_capacity_pct", {})
    _co2_footer = _format_source_footer(
        "EDITORIAL",
        timestamp_iso=_co2_fact.get("set_on"),
        editorial_set_on=_co2_fact.get("set_on"),
    )
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
            source_footer=_co2_footer,
            source_footer_kind="editorial",
        ))
    else:
        intel_cards.append(card_status_html(
            "INDUSTRIAL CO2 BYPRODUCT",
            "NOMINAL",
            "#10b981",
            "European ammonia capacity within nominal range; food-grade "
            "CO2 byproduct supply stable.",
            caption_key="co2",
            source_footer=_co2_footer,
            source_footer_kind="editorial",
        ))

    # v18 Fix 3 — EU gas storage card. Sits next to CO2 in the
    # Logistics & Inputs grid. Live AGSI+ %; 80%+ is healthy
    # heading into winter, sub-20% is critical.
    _gas_storage_v = intel_data.get("eu_gas_storage_pct")
    _gas_breach = _gas_storage_v is not None and _gas_storage_v < 20
    _gas_warn = (
        _gas_storage_v is not None and 20 <= _gas_storage_v < 50
    )
    intel_cards.append(card_numeric_html(
        "EU GAS STORAGE  (% of capacity)",
        _gas_storage_v,
        INTEL_BASELINE["eu_gas_storage_pct"],
        "", False, fmt="{:.1f}", suffix="%", delta_decimals=1,
        breach=_gas_breach,
        warning=_gas_warn,
        caption_key="eu_gas_storage",
        **_meta_kwargs("eu_gas_storage_pct"),
    ))

    _resin_breach = resin_v is not None and resin_v > 40
    _resin_warn = resin_v is not None and 20 < resin_v <= 40
    # Fix 3 — display the computed spike pct; baseline for the
    # delta line is 0% (no spike). Source-meta routing reads from
    # the new asian_pp_spot_price_ton key.
    intel_cards.append(card_numeric_html(
        "PE/PP RESIN SPIKE  (Asia)",
        resin_v,
        0.0,
        "", True, fmt="{:.1f}", suffix="%", delta_decimals=1,
        breach=_resin_breach,
        warning=_resin_warn,
        caption_key="resin",
        **_meta_kwargs("asian_pp_spot_price_ton"),
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
        **_meta_kwargs("jet_fuel_price_ton"),
    ))

    # v15.4 truth anchor — DGFT Notification 07/2026-27 (April 10, 2026)
    # liberalised rice exports to non-EU European countries. The card
    # title flips from "INDIA RICE EXPORT BAN" to "INDIA RICE POLICY"
    # since the headline is no longer a ban; the briefing text and
    # source link surface the underlying notification.
    if rice_ban == "ACTIVE":
        intel_cards.append(card_status_html(
            "INDIA RICE POLICY", "🔴 ACTIVE / CRITICAL", "#dc2626",
            "Indian government export ban currently in force on at "
            "least one rice category. Sovereign food-policy shock "
            "active.",
            breach=True,
            caption_key="rice",
            **_meta_kwargs("india_rice_ban_status"),
        ))
    elif rice_ban == "INACTIVE":
        # v15.5 — primary-source briefing: DGFT Notif 07/2026-27.
        # Fix B — dropped "(Liberalized)" parenthetical; the detail
        # line below the badge already explains the regulatory move.
        intel_cards.append(card_status_html(
            "INDIA RICE POLICY",
            "🟢 NOMINAL",
            "#10b981",
            "DGFT Notification 07/2026-27 (April 10) liberalizes "
            "rice exports to non-EU European countries by removing "
            "Certificate of Inspection requirements.",
            caption_key="rice",
            **_meta_kwargs("india_rice_ban_status"),
        ))
    else:
        intel_cards.append(card_status_html(
            "INDIA RICE POLICY",
            RICE_BAN_BASELINE,
            "#10b981",
            "Peace-time baseline — no active export ban on file.",
            is_baseline=True,
            caption_key="rice",
            **_meta_kwargs("india_rice_ban_status"),
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

    # ----- Fix C-3: Editorial Layer panel -----
    # Surfaces what's currently hand-set vs live so the operator
    # never has to guess. Counts of applied / expired / disagreeing
    # overrides; expandable detail per entry.
    _ed_applied = editorial_log.get("applied", [])
    _ed_expired = editorial_log.get("expired", [])
    _ed_disagree = editorial_log.get("disagree", [])
    _ed_unknown = editorial_log.get("skipped_unknown", [])
    st.markdown(
        f'<div class="status-strip" '
        f'style="margin-top:0.5rem;border-left-color:#9ca3af;">'
        f'EDITORIAL LAYER: '
        f'<span style="color:#fde68a;">'
        f'{len(_ed_applied)} active</span> · '
        f'<span style="color:#9ca3af;">'
        f'{len(_ed_expired)} expired</span> · '
        f'<span style="color:#fca5a5;">'
        f'{len(_ed_disagree)} disagree with live</span>'
        f'{(" · " + str(len(_ed_unknown)) + " misconfigured") if _ed_unknown else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    with st.expander("ⓘ Editorial Layer — what's hand-set right now",
                     expanded=False):
        if _ed_applied:
            st.markdown("**Active overrides** — applied on top of "
                        "live data:")
            for ov in _ed_applied:
                disagree_flag = ""
                if any(d["key"] == ov["key"] for d in _ed_disagree):
                    disagree_flag = " 🟠 *disagrees with live*"
                st.markdown(
                    f"- **{ov['key']}** = `{ov['after']}` "
                    f"(was `{ov['before']}`){disagree_flag}  \n"
                    f"  set {ov['set_on']} by {ov['set_by']}, "
                    f"expires {ov['expires_on']}  \n"
                    f"  *{ov['rationale']}*  \n"
                    f"  Source: {ov['primary_source']}"
                )
        if _ed_expired:
            st.markdown("**Expired overrides** — auto-fell-off, "
                        "live data now drives:")
            for ov in _ed_expired:
                st.markdown(
                    f"- `{ov['key']}` (expired {ov['expired_on']}) — "
                    f"{ov.get('rationale','')}"
                )
        if _ed_unknown:
            st.markdown("**Misconfigured overrides** — key matches "
                        "neither INTEL_METRICS nor TICKERS:")
            for ov in _ed_unknown:
                st.markdown(f"- `{ov['key']}` — {ov['reason']}")
        if not (_ed_applied or _ed_expired or _ed_unknown):
            st.markdown(
                "_No editorial overrides currently configured._"
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
        # Fix 3 — resin_v is the COMPUTED spike pct (already
        # derived from intel_data["asian_pp_spot_price_ton"]); the
        # threshold engine compares it to 40%. Baseline shown when
        # data is unavailable is 0% (no spike).
        ("Resins > 40% spike", resin_v, 40, "", "gt", "%",
         0.0, "resin"),
        ("Jet Fuel > $1500/t", jet_v, 1500, "$", "gt", "",
         INTEL_BASELINE["jet_fuel_price_ton"], "jet"),
        # v18 Fix 3 — EU gas storage tripwire (low-side breach).
        ("EU Gas Storage < 20%",
         intel_data.get("eu_gas_storage_pct"), 20, "", "lt", "%",
         INTEL_BASELINE["eu_gas_storage_pct"],
         "eu_gas_storage"),
        # v18 Fix 4 — Diesel crack tripwire. Critical above $50/bbl;
        # baseline shown is the normal mid-range $25.
        ("Diesel crack > $50/bbl", diesel_crack_v, 50, "$", "gt", "",
         25.0, "diesel_crack"),
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
# v16 (Fix 1) — the raw expander now shows the structured per-metric
# fan-out result so the user can audit, for each metric, whether
# Perplexity returned a usable value, what primary-source hints
# were sent in the prompt, and which call (if any) failed. The
# payload is the smoke test for the rest of the truthfulness work.
if api_key and intel_meta.get("raw"):
    with st.expander(
        "Raw intel payload (per-metric fan-out)", expanded=False
    ):
        st.code(intel_meta["raw"], language="json")
        _meta = intel_meta.get("metric_meta") or {}
        if _meta:
            _live_count = sum(
                1 for m in _meta.values() if m.get("value") is not None
            )
            st.caption(
                f"Fan-out: {_live_count}/{len(_meta)} metrics returned "
                f"a non-null value. Cache TTL is 4 hours per metric."
            )

# ---------- SOURCE DUMP — full provenance ledger ----------
# Consolidates everything the dashboard knows about its own data
# into one auditable block. The user can copy the JSON tab and
# hand it to a downstream AI; the auditor can spot bugs like
# "card claims live but Perplexity returned null and the derived
# adapter ran" without re-fetching anything. No new network calls.
with st.expander(
    "📋 Source Dump — full provenance ledger (copy for AI audit)",
    expanded=False,
):
    _src_dump = _build_source_dump(
        prices=prices,
        intel_data=intel_data,
        intel_meta=intel_meta,
        editorial_log=editorial_log,
        editorial_facts_log=editorial_facts_log,
        grs=grs,
        adjusted=adjusted,
        actions=actions,
        intel_grade=_intel_grade,
        live_count=_live_count,
        total_metrics=_total_metrics,
        api_key_configured=bool(api_key),
        sparkline_series=sparkline_series,
    )
    _md_tab, _json_tab = st.tabs(
        ["📄 Markdown view", "🤖 JSON view (for AI audit)"]
    )
    with _md_tab:
        st.markdown(_format_source_dump_markdown(_src_dump))
    with _json_tab:
        st.code(
            _format_source_dump_json(_src_dump),
            language="json",
        )

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
