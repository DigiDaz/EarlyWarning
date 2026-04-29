import json
import re
from datetime import datetime

import requests
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Global Supply Chain Contagion HUD",
    page_icon="\U0001F6E1",
    layout="wide",
    initial_sidebar_state="expanded",
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
    [data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 1rem;
    }
    [data-testid="stMetricLabel"] {
        color: #9ca3af;
        font-family: 'Courier New', monospace;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-size: 0.75rem;
    }
    [data-testid="stMetricValue"] {
        color: #e5e7eb;
        font-family: 'Courier New', monospace;
        font-size: 1.75rem;
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
    .status-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        height: 100%;
    }
    .status-card-label {
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-size: 0.75rem;
        margin-bottom: 0.5rem;
    }
    .status-card-value {
        font-size: 1.5rem;
        font-weight: bold;
        letter-spacing: 2px;
        margin-bottom: 0.4rem;
    }
    .status-card-detail {
        font-size: 0.78rem;
        color: #9ca3af;
        line-height: 1.3;
    }
    .status-card-unavail {
        font-size: 1.1rem;
        color: #6b7280;
        letter-spacing: 1px;
        margin-bottom: 0.4rem;
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

INTEL_BASELINE = {
    "panama_canal_neopanamax_price": 1_500_000.0,
    "urea_spot_price_ton": 360.0,
    "hormuz_daily_transit_count": 50.0,
    "helium_spot_price_mcf": 350.0,
    "asian_pe_pp_resin_spike": 0.0,
    "jet_fuel_price_ton": 700.0,
}

BASE_PROBS = {
    "Best Case": 10.0,
    "Slow Normalization": 18.0,
    "Base Case": 42.0,
    "Tail Risk": 30.0,
}

PROB_COLORS = {
    "Best Case": "#10b981",
    "Slow Normalization": "#3b82f6",
    "Base Case": "#eab308",
    "Tail Risk": "#dc2626",
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
    "helium_spot_price_mcf, asian_pe_pp_resin_spike, jet_fuel_price_ton, "
    "india_rice_ban_status. "
    "Numeric values only for the numeric keys. No markdown, no prose."
)


@st.cache_data(ttl=60)
def fetch_price(ticker: str) -> float | None:
    """
    Pull raw close price directly from yfinance. No multipliers, no
    transforms, no synthetic data — whatever Yahoo returns is what
    the dashboard displays.
    """
    try:
        data = yf.Ticker(ticker).history(period="2d", interval="1d")
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception:
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


@st.cache_data(ttl=900, show_spinner=False)
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


def adjust_probabilities(prices: dict, intel: dict | None = None) -> dict:
    intel = intel or {}

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

    for k in probs:
        probs[k] = max(0.0, probs[k])
    total = sum(probs.values())
    if total > 0:
        for k in probs:
            probs[k] = round(probs[k] / total * 100, 1)
    return probs


def evaluate_playbook(prices: dict, intel: dict | None = None) -> list[dict]:
    actions = []
    intel = intel or {}
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

    return actions


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


def render_status_card(col, label, value_text, value_color, detail):
    """Generic qualitative card. value_text=None → DATA UNAVAILABLE."""
    with col:
        if value_text is None:
            st.markdown(
                f'<div class="status-card">'
                f'<div class="status-card-label">{label}</div>'
                f'<div class="status-card-unavail">DATA UNAVAILABLE</div>'
                f'<div class="status-card-detail">{detail or ""}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            return
        st.markdown(
            f'<div class="status-card" style="border-color: {value_color};">'
            f'<div class="status-card-label">{label}</div>'
            f'<div class="status-card-value" style="color: {value_color};">'
            f'● {value_text}</div>'
            f'<div class="status-card-detail">{detail or ""}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------- SIDEBAR: API key & controls ----------
with st.sidebar:
    st.markdown(
        '<h3 class="hud-title" style="font-size:0.95rem;">◆ INTEL FEED</h3>',
        unsafe_allow_html=True,
    )
    api_key = st.text_input(
        "Perplexity API Key",
        type="password",
        help="Used only in-session to query api.perplexity.ai. Not persisted.",
        placeholder="pplx-...",
    )

    refresh_intel = st.button("Refresh Intel", use_container_width=True)
    if refresh_intel:
        fetch_perplexity_intel.clear()

    if not api_key:
        st.warning(
            "Enter a Perplexity API key to enable non-ticker intelligence "
            "(Panama, urea, Hormuz, Malacca, helium, PE/PP resins, jet "
            "fuel, India rice ban). Commodity feed will continue without it.",
            icon="⚠️",
        )

    st.markdown(
        '<div style="font-size:0.7rem;color:#6b7280;margin-top:1rem;">'
        "Intel cache: 15 min. Click Refresh Intel to force a new query.</div>",
        unsafe_allow_html=True,
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
    f'BASELINE: April 2026 pre-crisis &nbsp;|&nbsp; '
    f'INTEL: {intel_status}</div>',
    unsafe_allow_html=True,
)

# ---------- COMMODITY FEED ----------
with st.spinner("Pulling live commodity feed..."):
    prices = {name: fetch_price(tk) for name, tk in TICKERS.items()}

st.markdown('<h3 class="hud-title">◆ Commodity Telemetry</h3>',
            unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)


def metric_panel(col, label, price, baseline_value, currency, bearish_on_rise,
                 fmt="{:,.2f}"):
    with col:
        if price is None:
            st.metric(label, "—", "feed offline")
            return
        delta = price - baseline_value
        delta_pct = (delta / baseline_value) * 100 if baseline_value else 0.0
        delta_str = f"{delta:+,.2f} ({delta_pct:+.1f}%)"
        color = "inverse" if bearish_on_rise else "normal"
        st.metric(
            label=label,
            value=f"{currency}{fmt.format(price)}",
            delta=delta_str,
            delta_color=color,
        )


metric_panel(c1, "BRENT CRUDE  (BZ=F)", prices["Brent"], BASELINE["Brent"], "$", True)
metric_panel(c2, "TTF GAS  (TTF=F)", prices["TTF"], BASELINE["TTF"], "€", True)
# Gold/Silver: raw yfinance Close, no multipliers, baseline kept at the
# pre-crisis $2,300 / $28 reference levels for delta math.
metric_panel(c3, "GOLD  (GC=F)", prices["Gold"], BASELINE["Gold"], "$", False)
metric_panel(c4, "SILVER  (SI=F)", prices["Silver"], BASELINE["Silver"], "$", False)

st.markdown("&nbsp;", unsafe_allow_html=True)

# ---------- PERPLEXITY INTEL ----------
st.markdown(
    '<h3 class="hud-title">◆ Logistics & Inputs Intel '
    '<span class="intel-tag">PERPLEXITY</span></h3>',
    unsafe_allow_html=True,
)

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


def intel_panel(col, label, value, baseline_value, currency, bearish_on_rise,
                fmt="{:,.0f}", suffix="", delta_decimals=0):
    """Numeric intel card. value=None → 'DATA UNAVAILABLE'.
    Upstream parsing already converts 0 / negatives to None so we never
    show, alert on, or score a placeholder zero."""
    with col:
        if value is None:
            st.metric(label, "DATA UNAVAILABLE")
            return
        delta = value - baseline_value
        delta_fmt = f"{{:+,.{delta_decimals}f}}"
        delta_part = delta_fmt.format(delta)
        if baseline_value:
            delta_pct = (delta / baseline_value) * 100
            delta_str = f"{delta_part}{suffix} ({delta_pct:+.1f}%)"
        else:
            delta_str = f"{delta_part}{suffix} (vs 0 baseline)"
        color = "inverse" if bearish_on_rise else "normal"
        st.metric(
            label=label,
            value=f"{currency}{fmt.format(value)}{suffix}",
            delta=delta_str,
            delta_color=color,
        )


# Row 1 — chokepoints & primary inputs
i1, i2, i3, i4 = st.columns(4)
intel_panel(
    i1, "PANAMA NEOPANAMAX  (slot $)",
    intel_data.get("panama_canal_neopanamax_price"),
    INTEL_BASELINE["panama_canal_neopanamax_price"],
    "$", True, fmt="{:,.0f}",
)
intel_panel(
    i2, "UREA SPOT  ($/ton)",
    intel_data.get("urea_spot_price_ton"),
    INTEL_BASELINE["urea_spot_price_ton"],
    "$", True, fmt="{:,.0f}",
)
# Hormuz: lower transit count is the bearish event, so delta_color stays
# "normal" (a negative delta will display in red automatically).
intel_panel(
    i3, "HORMUZ TRANSITS  (ships/day)",
    intel_data.get("hormuz_daily_transit_count"),
    INTEL_BASELINE["hormuz_daily_transit_count"],
    "", False, fmt="{:.0f}",
)

malacca_sev = intel_data.get("malacca_severity")
malacca_status = intel_data.get("malacca_status")
if malacca_sev is None and malacca_status is None:
    render_status_card(i4, "MALACCA STATUS", None, None,
                       "Perplexity returned no usable status for this strait.")
else:
    sev = malacca_sev or "nominal"
    render_status_card(
        i4,
        "MALACCA STATUS",
        sev.upper(),
        SEVERITY_COLORS.get(sev, "#9ca3af"),
        malacca_status or "(no status text returned)",
    )

# Row 2 — strategic blind-spot inputs
j1, j2, j3, j4 = st.columns(4)
intel_panel(
    j1, "HELIUM SPOT  ($/Mcf)",
    intel_data.get("helium_spot_price_mcf"),
    INTEL_BASELINE["helium_spot_price_mcf"],
    "$", True, fmt="{:,.0f}",
)
intel_panel(
    j2, "PE/PP RESIN SPIKE  (Asia)",
    intel_data.get("asian_pe_pp_resin_spike"),
    INTEL_BASELINE["asian_pe_pp_resin_spike"],
    "", True, fmt="{:.1f}", suffix="%", delta_decimals=1,
)
intel_panel(
    j3, "JET FUEL  ($/ton)",
    intel_data.get("jet_fuel_price_ton"),
    INTEL_BASELINE["jet_fuel_price_ton"],
    "$", True, fmt="{:,.0f}",
)

rice_ban = intel_data.get("india_rice_ban_status")
if rice_ban == "ACTIVE":
    render_status_card(
        j4,
        "INDIA RICE EXPORT BAN",
        "ACTIVE",
        "#dc2626",
        "Indian government export ban currently in force on at least one "
        "rice category. Sovereign food-policy shock active.",
    )
elif rice_ban == "INACTIVE":
    render_status_card(
        j4,
        "INDIA RICE EXPORT BAN",
        "INACTIVE",
        "#10b981",
        "No active Indian rice export ban currently in force.",
    )
else:
    render_status_card(
        j4,
        "INDIA RICE EXPORT BAN",
        None,
        None,
        "Perplexity did not return a usable ACTIVE/INACTIVE flag.",
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

st.markdown("&nbsp;", unsafe_allow_html=True)

# ---------- PROBABILITY MATRIX & THRESHOLDS ----------
left, right = st.columns([1.2, 1])

with left:
    st.markdown('<h3 class="hud-title">◆ Scenario Probability Matrix</h3>',
                unsafe_allow_html=True)
    adjusted = adjust_probabilities(prices, intel_data)
    for label in ["Best Case", "Slow Normalization", "Base Case", "Tail Risk"]:
        render_prob_bar(label, adjusted[label], BASE_PROBS[label])

    drift = sum(abs(adjusted[k] - BASE_PROBS[k]) for k in BASE_PROBS) / 2
    notes = []
    if intel_data.get("malacca_severity") == "critical":
        notes.append('<span style="color:#dc2626;">'
                     'MALACCA OVERRIDE — TAIL RISK MAX</span>')
    if intel_data.get("india_rice_ban_status") == "ACTIVE":
        notes.append('<span style="color:#dc2626;">'
                     'RICE BAN — STAPLES SHOCK</span>')
    drift_note = (" &nbsp;|&nbsp; " + " &nbsp;·&nbsp; ".join(notes)) if notes else ""
    st.markdown(
        f'<div class="status-strip">SCENARIO DRIFT vs BASELINE: '
        f'<span style="color:#00ffd1;">{drift:.1f} pts</span>{drift_note}</div>',
        unsafe_allow_html=True,
    )

with right:
    st.markdown('<h3 class="hud-title">◆ Threshold Monitor</h3>',
                unsafe_allow_html=True)
    urea_v = intel_data.get("urea_spot_price_ton")
    hormuz_v = intel_data.get("hormuz_daily_transit_count")
    panama_v = intel_data.get("panama_canal_neopanamax_price")
    helium_v = intel_data.get("helium_spot_price_mcf")
    resin_v = intel_data.get("asian_pe_pp_resin_spike")
    jet_v = intel_data.get("jet_fuel_price_ton")
    malacca_sev = intel_data.get("malacca_severity")
    rice_ban_v = intel_data.get("india_rice_ban_status")

    thresholds = [
        ("Brent > $130", prices["Brent"], 130, "$", "gt", ""),
        ("Brent > $115", prices["Brent"], 115, "$", "gt", ""),
        ("TTF > €80", prices["TTF"], 80, "€", "gt", ""),
        ("TTF > €65", prices["TTF"], 65, "€", "gt", ""),
        ("Gold > $4600", prices["Gold"], 4600, "$", "gt", ""),
        ("Silver > $75", prices["Silver"], 75, "$", "gt", ""),
        ("Urea > $800/t", urea_v, 800, "$", "gt", ""),
        ("Urea > $600/t", urea_v, 600, "$", "gt", ""),
        ("Hormuz < 30/day", hormuz_v, 30, "", "lt", ""),
        ("Hormuz < 20/day", hormuz_v, 20, "", "lt", ""),
        ("Panama slot > $2.5M", panama_v, 2_500_000, "$", "gt", ""),
        ("Panama slot > $4.0M", panama_v, 4_000_000, "$", "gt", ""),
        ("Helium > $2000/Mcf", helium_v, 2000, "$", "gt", ""),
        ("Resins > 40% spike", resin_v, 40, "", "gt", "%"),
        ("Jet Fuel > $1500/t", jet_v, 1500, "$", "gt", ""),
    ]
    for name, val, thr, cur, op, sfx in thresholds:
        if val is None:
            status = '<span style="color:#6b7280;">— DATA UNAVAILABLE</span>'
            live = "—"
        else:
            breached = (op == "gt" and val > thr) or (op == "lt" and val < thr)
            if breached:
                status = '<span style="color:#dc2626;">● BREACHED</span>'
            else:
                status = '<span style="color:#10b981;">● NOMINAL</span>'
            if cur:
                live = f"{cur}{val:,.0f}{sfx}"
            else:
                live = f"{val:,.1f}{sfx}" if sfx == "%" else f"{val:.0f}"
        st.markdown(
            f'<div class="prob-bar-container" style="display:flex;'
            f'justify-content:space-between;font-family:Courier New,monospace;'
            f'font-size:0.8rem;">'
            f'<span style="color:#9ca3af;">{name}</span>'
            f'<span style="color:#9ca3af;">live: {live}</span>'
            f'<span>{status}</span></div>',
            unsafe_allow_html=True,
        )

    # Malacca qualitative threshold row
    if malacca_sev is None:
        m_status = '<span style="color:#6b7280;">— DATA UNAVAILABLE</span>'
        m_live = "—"
    elif malacca_sev == "critical":
        m_status = '<span style="color:#dc2626;">● BREACHED (CRITICAL)</span>'
        m_live = "critical"
    elif malacca_sev == "elevated":
        m_status = '<span style="color:#eab308;">● ELEVATED</span>'
        m_live = "elevated"
    else:
        m_status = '<span style="color:#10b981;">● NOMINAL</span>'
        m_live = "nominal"
    st.markdown(
        f'<div class="prob-bar-container" style="display:flex;'
        f'justify-content:space-between;font-family:Courier New,monospace;'
        f'font-size:0.8rem;">'
        f'<span style="color:#9ca3af;">Malacca severity</span>'
        f'<span style="color:#9ca3af;">live: {m_live}</span>'
        f'<span>{m_status}</span></div>',
        unsafe_allow_html=True,
    )

    # India rice ban qualitative threshold row
    if rice_ban_v is None:
        r_status = '<span style="color:#6b7280;">— DATA UNAVAILABLE</span>'
        r_live = "—"
    elif rice_ban_v == "ACTIVE":
        r_status = '<span style="color:#dc2626;">● BREACHED (ACTIVE)</span>'
        r_live = "ACTIVE"
    else:
        r_status = '<span style="color:#10b981;">● NOMINAL</span>'
        r_live = "INACTIVE"
    st.markdown(
        f'<div class="prob-bar-container" style="display:flex;'
        f'justify-content:space-between;font-family:Courier New,monospace;'
        f'font-size:0.8rem;">'
        f'<span style="color:#9ca3af;">India rice ban</span>'
        f'<span style="color:#9ca3af;">live: {r_live}</span>'
        f'<span>{r_status}</span></div>',
        unsafe_allow_html=True,
    )

st.markdown("&nbsp;", unsafe_allow_html=True)

# ---------- PLAYBOOK ----------
actions = evaluate_playbook(prices, intel_data)
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
