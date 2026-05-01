"""v18+ Part 3 — Daily projection-log snapshot.

Runs from GitHub Actions on a 23:00 UTC cron. Computes the same
GRS + probability matrix the live dashboard does, then appends one
CSV row to projection_log.csv at the repo root. The repo commit is
the audit trail — Streamlit Cloud's filesystem is ephemeral on
redeploy, so a daily-committed file in the repo is the only place
the trace survives.

This script is intentionally self-contained: it re-implements the
fetch + compute logic in 200-ish lines rather than importing from
dashboard.py, because dashboard.py runs Streamlit rendering as
module-level side effects and is awkward to import in a CI context.
The trade-off is duplication; the win is no Streamlit dependency
and a script that runs in 30 seconds on a clean Ubuntu image.

Inputs:
  PERPLEXITY_API_KEY   — required; the per-metric Perplexity
                          fan-out is the same as the dashboard.
  AGSI_API_KEY         — optional; AGSI+ direct gas-storage feed.
Outputs:
  projection_log.csv (in repo root) — one row appended per run.
Exit code:
  0 on success
  non-zero on fatal error (missing CSV, write failure, etc.)
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests
import yfinance as yf


# ============================================================
# Constants — DUPLICATED from dashboard.py. Keep in sync.
# ============================================================
# When dashboard.py's editorial layer / engine changes, mirror
# the change here. The drift risk is real but contained because
# both files live in the same repo and any rule change should be
# a single PR touching both.

BASE_PROBS = {
    "Best Case": 5.0,
    "Slow Normalization": 15.0,
    "Base Case": 50.0,
    "Tail Risk": 30.0,
}

INTEL_BASELINE = {
    "panama_canal_neopanamax_price": 1_500_000.0,
    "urea_spot_price_ton": 320.0,
    "hormuz_daily_transit_count": 80.0,
    "helium_spot_price_mcf": 400.0,
    "asian_pp_spot_price_ton": 1000.0,
    "jet_fuel_price_ton": 850.0,
    "eu_gas_storage_pct": 80.0,
}

# Editorial overrides (mirrors EDITORIAL_OVERRIDES in dashboard.py).
# Each entry: (intel_key | price_label, value, expires_on).
EDITORIAL_OVERRIDES = [
    ("intel", "india_rice_ban_status", "INACTIVE",  date(2026, 7, 10)),
    ("intel", "malacca_severity",      "nominal",    date(2026, 5, 28)),
    ("intel", "malacca_ships_waiting", 80,           date(2026, 5, 28)),
    ("intel", "hormuz_daily_transit_count", 4,       date(2026, 5, 14)),
    ("price", "Gold",                   4571.0,      date(2026, 5, 14)),
]

# Editorial fallbacks (target_intel_key when live is null).
EDITORIAL_FALLBACKS = [
    ("panama_canal_neopanamax_price", 385_000.0, date(2026, 5, 28)),
]

# Editorial facts (module-global flags).
EDITORIAL_FACTS = [
    ("oecd_inventory_below_min", True,  date(2026, 5, 14)),
    ("eu_ammonia_capacity_pct",  35.0,  date(2026, 5, 21)),
]

QATAR_HELIUM_FORCE_MAJEURE_DATE = date(2026, 3, 2)
HELIUM_BOIL_OFF_DAYS = 48
EUROPEAN_AMMONIA_THRESHOLD_PCT = 40.0

PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"


# ============================================================
# Lightweight fetchers — reuse same primary sources as dashboard.
# ============================================================

def fetch_yfinance_close(ticker):
    try:
        h = yf.Ticker(ticker).history(period="2d", interval="1d")
        if h.empty:
            return None
        return float(h["Close"].iloc[-1])
    except Exception:
        return None


def fetch_agsi_eu_storage_pct(api_key):
    if not api_key:
        return None
    try:
        resp = requests.get(
            "https://agsi.gie.eu/api",
            params={"country": "eu", "date": "latest"},
            headers={"x-key": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        rows = resp.json().get("data") or []
        if not rows:
            return None
        return float(rows[0].get("full"))
    except Exception:
        return None


def fetch_perplexity_metric(api_key, question, expected="number",
                            recency_days=7):
    """One narrow metric, one Perplexity call. Returns float | str |
    None depending on `expected` ('number' / 'enum' / 'string').
    Failures collapse silently to None — the snapshot is honest
    about what couldn't be fetched."""
    if not api_key:
        return None
    user_prompt = (
        f"{question} If no primary source within the last "
        f"{recency_days} days, return null. Return ONLY a JSON "
        'object {"value": <value>}. No prose, no markdown, no '
        "citations."
    )
    try:
        resp = requests.post(
            PERPLEXITY_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": PERPLEXITY_MODEL,
                "messages": [
                    {"role": "system", "content":
                        'You return ONLY a JSON object '
                        '{"value": ...}.'},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        body = resp.json()
        content = body["choices"][0]["message"]["content"].strip()
        # Handle code-fenced or plain JSON.
        if content.startswith("```"):
            content = content.strip("`").strip()
            if content.startswith("json"):
                content = content[4:].strip()
        import json as _json
        parsed = _json.loads(content)
        v = parsed.get("value")
        if v is None:
            return None
        if expected == "number":
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        return v
    except Exception:
        return None


# ============================================================
# Engine — abbreviated mirror of grs_compute + adjust_probabilities.
# ============================================================

def metric_health(value, baseline, crit, inverted=False):
    if value is None:
        return None
    v = float(value)
    if inverted:
        if v >= baseline:
            return 100.0
        if v <= crit:
            return 0.0
        return (v - crit) / (baseline - crit) * 100.0
    if v <= baseline:
        return 100.0
    if v >= crit:
        return 0.0
    return (1.0 - (v - baseline) / (crit - baseline)) * 100.0


def avg_or_none(parts):
    cleaned = [p for p in parts if p is not None]
    return sum(cleaned) / len(cleaned) if cleaned else None


def grs_compute_basic(prices, intel, oecd_breach, eu_ammonia_pct):
    # Commodity cluster
    brent_h = metric_health(prices.get("Brent"), 100.0, 130.0)
    ttf_h = metric_health(prices.get("TTF"), 52.0, 80.0)
    urea_h = metric_health(intel.get("urea_spot_price_ton"), 320.0, 800.0)
    diesel_h = metric_health(
        intel.get("diesel_crack_per_bbl"), 25.0, 50.0,
    )
    commodity = avg_or_none([brent_h, ttf_h, urea_h, diesel_h])

    # Logistics cluster
    sev = intel.get("malacca_severity")
    if sev == "critical":
        malacca_h = 0.0
    elif sev == "elevated":
        malacca_h = 30.0
    else:
        malacca_h = 100.0
    hormuz_h = metric_health(
        intel.get("hormuz_daily_transit_count"), 80.0, 20.0,
        inverted=True,
    )
    panama_h = metric_health(
        intel.get("panama_canal_neopanamax_price"),
        385_000.0, 1_000_000.0,
    )
    logistics = avg_or_none([malacca_h, hormuz_h, panama_h])

    # Buffers cluster
    days = (date.today() - QATAR_HELIUM_FORCE_MAJEURE_DATE).days
    boil_off = HELIUM_BOIL_OFF_DAYS
    depletion = boil_off * 2
    if days <= 0:
        helium_h = 100.0
    elif days >= depletion:
        helium_h = 0.0
    elif days <= boil_off:
        helium_h = 100.0 - (days / boil_off) * 50.0
    else:
        helium_h = 50.0 - ((days - boil_off) / boil_off) * 50.0
    live_helium = intel.get("helium_spot_price_mcf")
    if live_helium is not None and live_helium < 1000:
        helium_h = max(helium_h, 60.0)

    cap = eu_ammonia_pct
    threshold = EUROPEAN_AMMONIA_THRESHOLD_PCT
    if cap >= 100.0:
        co2_h = 100.0
    elif cap <= 0.0:
        co2_h = 0.0
    elif cap >= threshold:
        co2_h = 50.0 + ((cap - threshold) / (100.0 - threshold)) * 50.0
    else:
        co2_h = (cap / threshold) * 50.0

    gas_storage_h = None
    gas_pct = intel.get("eu_gas_storage_pct")
    if gas_pct is not None:
        v = float(gas_pct)
        if v >= 80:
            gas_storage_h = 100.0
        elif v <= 20:
            gas_storage_h = 0.0
        else:
            gas_storage_h = ((v - 20.0) / 60.0) * 100.0

    oecd_h = 0.0 if oecd_breach else 100.0

    parts = [
        (helium_h, 0.30),
        (co2_h, 0.30),
        (gas_storage_h, 0.20),
        (oecd_h, 0.20),
    ]
    cleaned = [(v, w) for v, w in parts if v is not None]
    if cleaned:
        total_w = sum(w for _, w in cleaned)
        buffers = sum(v * w for v, w in cleaned) / total_w
    else:
        buffers = None

    overall = avg_or_none([commodity, logistics, buffers])
    return {
        "overall": overall,
        "commodity": commodity,
        "logistics": logistics,
        "buffers": buffers,
    }


def adjust_probabilities_basic(prices, intel, helium_exhausted,
                               oecd_breach, co2_breach):
    if intel.get("malacca_severity") == "critical":
        return {
            "Best Case": 0.0, "Slow Normalization": 0.0,
            "Base Case": 0.0, "Tail Risk": 100.0,
        }
    p = dict(BASE_PROBS)
    brent = prices.get("Brent")
    ttf = prices.get("TTF")
    if brent is not None and brent > 130:
        p["Tail Risk"] += 10; p["Base Case"] -= 10
    elif brent is not None and brent > 115:
        p["Tail Risk"] += 5; p["Base Case"] -= 5
    elif brent is not None and brent < 90:
        p["Best Case"] += 5; p["Tail Risk"] -= 5
    elif brent is not None and brent < 95:
        p["Best Case"] += 3; p["Tail Risk"] -= 3
    if ttf is not None and ttf > 80:
        p["Tail Risk"] += 8; p["Base Case"] -= 4; p["Slow Normalization"] -= 4
    elif ttf is not None and ttf > 65:
        p["Tail Risk"] += 4; p["Base Case"] -= 4
    elif ttf is not None and ttf < 50:
        p["Slow Normalization"] += 4; p["Tail Risk"] -= 4
    urea = intel.get("urea_spot_price_ton")
    if urea is not None and urea > 800:
        p["Tail Risk"] += 6; p["Base Case"] -= 4; p["Best Case"] -= 2
    elif urea is not None and urea > 600:
        p["Tail Risk"] += 3; p["Base Case"] -= 3
    elif urea is not None and urea < 500:
        p["Slow Normalization"] += 4; p["Tail Risk"] -= 4
    hormuz = intel.get("hormuz_daily_transit_count")
    if hormuz is not None and hormuz < 20:
        p["Tail Risk"] += 12; p["Base Case"] -= 8; p["Best Case"] -= 4
    elif hormuz is not None and hormuz < 30:
        p["Tail Risk"] += 5; p["Base Case"] += 3
        p["Best Case"] -= 4; p["Slow Normalization"] -= 4
    elif hormuz is not None and hormuz > 60:
        p["Best Case"] += 5; p["Tail Risk"] -= 5
    elif hormuz is not None and hormuz > 30:
        p["Slow Normalization"] += 4; p["Tail Risk"] -= 4
    if intel.get("india_rice_ban_status") == "ACTIVE":
        p["Tail Risk"] += 18; p["Base Case"] -= 8
        p["Best Case"] -= 5; p["Slow Normalization"] -= 5
    if helium_exhausted:
        p["Tail Risk"] += 8; p["Base Case"] -= 4; p["Slow Normalization"] -= 4
    if oecd_breach:
        p["Tail Risk"] += 8; p["Base Case"] -= 4; p["Slow Normalization"] -= 4
    if co2_breach:
        p["Tail Risk"] += 6; p["Base Case"] -= 3; p["Slow Normalization"] -= 3
    for k in p:
        p[k] = max(0.0, p[k])
    total = sum(p.values())
    if total > 0:
        for k in p:
            p[k] = round(p[k] / total * 100, 1)
    return p


# ============================================================
# Main snapshot routine
# ============================================================

def main():
    today = date.today()
    perplexity_key = os.environ.get("PERPLEXITY_API_KEY")
    agsi_key = os.environ.get("AGSI_API_KEY")

    # Yfinance prices.
    prices = {
        "Brent":  fetch_yfinance_close("BZ=F"),
        "TTF":    fetch_yfinance_close("TTF=F"),
        "Gold":   fetch_yfinance_close("GC=F"),
        "Silver": fetch_yfinance_close("SI=F"),
    }
    diesel_per_gal = fetch_yfinance_close("HO=F")
    diesel_per_bbl = (
        diesel_per_gal * 42.0 if diesel_per_gal is not None else None
    )

    # Perplexity intel — mirror the per-metric fan-out from the
    # dashboard, with the same neutral phrasing.
    intel = {
        "panama_canal_neopanamax_price": fetch_perplexity_metric(
            perplexity_key,
            "What is the most recent Panama Canal Authority (ACP) "
            "reported average auction slot price for Neopanamax "
            "vessels in US dollars? Use the latest publicly "
            "reported figure from the last 30 days.",
            "number", recency_days=30,
        ),
        "urea_spot_price_ton": (
            fetch_yfinance_close("UFV=F")
            or fetch_perplexity_metric(
                perplexity_key,
                "What is the current global urea spot price in US "
                "dollars per metric tonne?",
                "number",
            )
        ),
        "hormuz_daily_transit_count": fetch_perplexity_metric(
            perplexity_key,
            "What is the current Strait of Hormuz daily ship "
            "transit count?",
            "number",
        ),
        "helium_spot_price_mcf": fetch_perplexity_metric(
            perplexity_key,
            "What is the current global helium spot price in US "
            "dollars per Mcf?",
            "number",
        ),
        "malacca_severity": fetch_perplexity_metric(
            perplexity_key,
            "What is the current Strait of Malacca traffic severity? "
            "Output exactly one of: nominal, elevated, critical.",
            "string",
        ),
        "india_rice_ban_status": fetch_perplexity_metric(
            perplexity_key,
            "Is an Indian government rice export ban currently in "
            "force? Output exactly ACTIVE or INACTIVE.",
            "string",
        ),
        "eu_gas_storage_pct": (
            fetch_agsi_eu_storage_pct(agsi_key)
            or fetch_perplexity_metric(
                perplexity_key,
                "What is the current EU gas storage fill level as a "
                "percentage of capacity, per the latest AGSI+ "
                "report?",
                "number",
            )
        ),
        "diesel_crack_per_bbl": (
            diesel_per_bbl - prices["Brent"]
            if diesel_per_bbl is not None and prices["Brent"] is not None
            else None
        ),
    }

    # Apply editorial overrides (overlay live data per fact).
    overrides_applied = 0
    for kind, key, value, expires_on in EDITORIAL_OVERRIDES:
        if expires_on < today:
            continue
        if kind == "intel":
            intel[key] = value
        else:
            prices[key] = value
        overrides_applied += 1

    # Apply editorial fallbacks (only when live is null).
    for key, value, expires_on in EDITORIAL_FALLBACKS:
        if expires_on < today:
            continue
        if intel.get(key) is None:
            intel[key] = value
            overrides_applied += 1

    # Editorial facts.
    facts_applied = 0
    oecd_breach = False
    eu_ammonia_pct = 50.0
    for key, value, expires_on in EDITORIAL_FACTS:
        if expires_on < today:
            continue
        facts_applied += 1
        if key == "oecd_inventory_below_min":
            oecd_breach = bool(value)
        elif key == "eu_ammonia_capacity_pct":
            eu_ammonia_pct = float(value)
    co2_breach = eu_ammonia_pct < EUROPEAN_AMMONIA_THRESHOLD_PCT
    days = (today - QATAR_HELIUM_FORCE_MAJEURE_DATE).days
    helium_live = intel.get("helium_spot_price_mcf")
    helium_exhausted = (
        days >= HELIUM_BOIL_OFF_DAYS
        and not (helium_live is not None and helium_live < 1000)
    )

    # Compute GRS + probabilities.
    grs = grs_compute_basic(prices, intel, oecd_breach, eu_ammonia_pct)
    probs = adjust_probabilities_basic(
        prices, intel, helium_exhausted, oecd_breach, co2_breach,
    )
    dominant = max(probs, key=probs.get) if probs else "?"

    # AI Storage countdown.
    days_to_eoy = (date(2026, 12, 31) - today).days

    # Compose CSV row.
    row = {
        "date": today.isoformat(),
        "grs_overall":   _fmt(grs.get("overall")),
        "grs_commodity": _fmt(grs.get("commodity")),
        "grs_logistics": _fmt(grs.get("logistics")),
        "grs_buffers":   _fmt(grs.get("buffers")),
        "prob_best":  _fmt(probs.get("Best Case")),
        "prob_slow":  _fmt(probs.get("Slow Normalization")),
        "prob_base":  _fmt(probs.get("Base Case")),
        "prob_tail":  _fmt(probs.get("Tail Risk")),
        "dominant_scenario": dominant,
        "brent":  _fmt(prices.get("Brent")),
        "ttf":    _fmt(prices.get("TTF")),
        "urea":   _fmt(intel.get("urea_spot_price_ton")),
        "diesel_crack":  _fmt(intel.get("diesel_crack_per_bbl")),
        "hormuz": _fmt(intel.get("hormuz_daily_transit_count")),
        "panama": _fmt(intel.get("panama_canal_neopanamax_price")),
        "helium": _fmt(intel.get("helium_spot_price_mcf")),
        "ammonia_pct":     _fmt(eu_ammonia_pct),
        "ai_storage_days": str(max(0, days_to_eoy)),
        "active_overrides": str(overrides_applied),
        "active_facts":     str(facts_applied),
    }

    # Append to projection_log.csv.
    repo_root = Path(__file__).resolve().parent.parent
    log_path = repo_root / "projection_log.csv"
    if not log_path.exists():
        sys.stderr.write(
            f"FATAL: projection_log.csv missing at {log_path}\n"
        )
        sys.exit(2)
    with open(log_path, "r", encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split(",")
    with open(log_path, "a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([row.get(c, "") for c in header])

    print(
        f"snapshot OK · {today.isoformat()} · GRS "
        f"{row['grs_overall']}% · Lead {dominant}",
    )


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


if __name__ == "__main__":
    main()
