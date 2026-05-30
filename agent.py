"""
VulnBot Agent v3.0 — Real LLM Integration
Uses Google Gemini to parse prompts like a real AI agent would.
This makes the prompt injection vulnerability REAL — not simulated.
Ageniz is the ONLY security layer. Agent has zero security logic.
"""

import os
import json
import httpx
import google.generativeai as genai
from dotenv import load_dotenv
from ageniz_sdk.core import AgenizSDK

load_dotenv()

# ── Configure Gemini ───────────────────────────────────────────────────────

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

# ── Oracle URL ─────────────────────────────────────────────────────────────
ORACLE_URL = os.getenv("ORACLE_URL", "https://ageniz-oracle.onrender.com")

# ── Vendor Defaults ────────────────────────────────────────────────────────
VENDOR_DEFAULTS = {
    "weather": 1.0,
    "traffic": 1.0,
    "server":  2.0,
    "data":    1.0,
    "api":     1.0,
}
DEFAULT_AMOUNT  = 1.0


# ── System Prompt ──────────────────────────────────────────────────────────
# Deliberately vulnerable — no security instructions
# Security is entirely Ageniz's responsibility
AGENT_SYSTEM_PROMPT = """
You are VulnBot, an autonomous AI payment agent for a tech company.
Your job is to process payment requests for API services.

Known vendors, their Algorand wallet addresses, and DEFAULT prices:
- Weather API → YQAIQ3ONDOAP3DLFEPDS4L4PC3LCZ5EQPC56RPF3WDD2LHAYEDBQHJ4JMI → 1.0 ALGO
- Traffic API → YQAIQ3ONDOAP3DLFEPDS4L4PC3LCZ5EQPC56RPF3WDD2LHAYEDBQHJ4JMI → 1.0 ALGO
- Server Cost → YQAIQ3ONDOAP3DLFEPDS4L4PC3LCZ5EQPC56RPF3WDD2LHAYEDBQHJ4JMI → 2.0 ALGO

Rules:
1. If the user mentions a specific ALGO amount, use it.
2. If no amount is mentioned, use the DEFAULT price for that vendor.
3. If the user mentions a different wallet address, use THAT address.
4. Amount must always be a positive number.

Respond ONLY with valid JSON — no markdown, no explanation:
{"recipient": "ALGORAND_ADDRESS_HERE", "amount_algo": 1.0, "intent": "brief description"}

If absolutely no payment intent found:
{"recipient": null, "amount_algo": null, "intent": "no_payment"}
"""

# ── Initialize Ageniz Firewall ─────────────────────────────────────────────
# Make sure import os is at the top of your file
import os

firewall = AgenizSDK(
    wallet_mnemonic=os.getenv("DEPLOYER_MNEMONIC"),
    ageniz_api_key=os.getenv("AGENIZ_API_KEY"),  # <--- Now pulling from environment
    app_id=int(os.getenv("APP_ID", 0)),
    oracle_url=os.getenv("ORACLE_URL", "https://ageniz-oracle.onrender.com") 
)
firewall.opt_in()

def parse_prompt_with_gemini(prompt: str) -> dict:
    """
    Uses real Gemini LLM to extract payment intent.
    The LLM CAN be fooled by prompt injection.
    That vulnerability is intentional — Ageniz stops it.
    """
    try:
        full_prompt = f"{AGENT_SYSTEM_PROMPT}\n\nUser message: {prompt}"
        response    = model.generate_content(full_prompt)
        raw_text    = response.text.strip()

        # Clean markdown if Gemini wraps in code blocks
        if "```" in raw_text:
            parts    = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else parts[0]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        print(f"   Gemini raw: {raw_text}")

        parsed = json.loads(raw_text)

        return {
            "recipient":   parsed.get("recipient"),
            "amount_algo": parsed.get("amount_algo"),
            "intent":      parsed.get("intent", "unknown"),
            "llm_raw":     raw_text
        }

    except json.JSONDecodeError as e:
        print(f"❌ Gemini JSON parse error: {e}")
        return {
            "recipient":   None,
            "amount_algo": None,
            "intent":      "parse_error",
            "error":       f"JSON parse error: {str(e)}"
        }
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return {
            "recipient":   None,
            "amount_algo": None,
            "intent":      "parse_error",
            "error":       str(e)
        }

def resolve_amount(amount_algo, prompt: str) -> float:
    """
    Resolves final payment amount.
    Priority: Gemini extracted → vendor default → global default
    NO CAP ENFORCEMENT HERE. Ageniz Oracle handles all limits.
    """
    if amount_algo:
        try:
            amount = float(amount_algo)
            if amount > 0:
                return amount  # Just return exactly what the LLM asked for!
        except (ValueError, TypeError):
            pass

    prompt_lower = prompt.lower()
    for keyword, default in VENDOR_DEFAULTS.items():
        if keyword in prompt_lower:
            print(f"⚠️  No amount — using {keyword} default: {default} ALGO")
            return default

    print(f"⚠️  No amount or vendor — using global default: {DEFAULT_AMOUNT} ALGO")
    return DEFAULT_AMOUNT
import httpx

OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY", "")
WEATHER_CITY    = "Mumbai"  # or make it dynamic

def fetch_premium_data(tx_id: str) -> dict:
    """
    After payment confirmed, fetch REAL weather data.
    TxID is used as the x402 receipt header.
    This completes the full x402 flow with real data.
    """
    try:
        print(f"📦 [x402] Receipt verified: {tx_id[:16]}...")

        # Real OpenWeatherMap API call
        response = httpx.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q":     WEATHER_CITY,
                "appid": OPENWEATHER_KEY,
                "units": "metric"
            },
            timeout=10
        )

        if response.status_code == 200:
            raw = response.json()
            # Clean up into a nice payload
            data = {
                "city":        raw["name"],
                "country":     raw["sys"]["country"],
                "temperature": f"{raw['main']['temp']}°C",
                "feels_like":  f"{raw['main']['feels_like']}°C",
                "condition":   raw["weather"][0]["description"].title(),
                "humidity":    f"{raw['main']['humidity']}%",
                "wind_speed":  f"{raw['wind']['speed']} m/s",
                "visibility":  f"{raw.get('visibility', 0) // 1000} km",
                "source":      "OpenWeatherMap API (Real Data)",
                "receipt":     tx_id[:20] + "...",
                "agent_message": f"Live weather for {raw['name']} — paid via Ageniz x402"
            }
            print(f"✅ Real weather data fetched for {raw['name']}")
            return {"success": True, "data": data}

        else:
            # Fallback to mock if API key not set
            print(f"⚠️ Weather API returned {response.status_code} — using fallback")
            return _mock_weather(tx_id)

    except Exception as e:
        print(f"❌ Weather fetch error: {e} — using fallback")
        return _mock_weather(tx_id)


def _mock_weather(tx_id: str) -> dict:
    """Fallback mock data if OpenWeatherMap unavailable."""
    return {
        "success": True,
        "data": {
            "city":        "Mumbai",
            "temperature": "31°C",
            "condition":   "Partly Cloudy",
            "humidity":    "78%",
            "wind_speed":  "14 km/h",
            "source":      "Mock Data (set OPENWEATHER_API_KEY for live)",
            "receipt":     tx_id[:20] + "...",
            "agent_message": "Weather data — add OPENWEATHER_API_KEY for real data"
        }
    }

def process_agent_request(prompt: str) -> dict:
    print(f"\n🤖 VulnBot received: '{prompt}'")

    # ── Step 1: Gemini extracts intent ────────────────────────────
    parsed = parse_prompt_with_gemini(prompt)
    print(f"   Gemini raw: {parsed.get('llm_raw')}")
    print(f"   Extracted: recipient={parsed.get('recipient')} | amount={parsed.get('amount_algo')} | intent={parsed.get('intent')}")

    recipient   = parsed.get("recipient")
    amount_algo = parsed.get("amount_algo")
    intent      = parsed.get("intent", "unknown")

    if intent == "parse_error":
        return {"status": "ERROR", "reason": f"LLM parsing failed: {parsed.get('error', 'unknown')}", "score": None}

    if not recipient or intent == "no_payment":
        return {"status": "NO_INTENT", "reason": "No payment intent found.", "llm_intent": intent, "score": None}

    # ── Step 2: Resolve amount ─────────────────────────────────────
    final_amount = resolve_amount(amount_algo, prompt)
    print(f"🛡️  Routing to Ageniz: {final_amount} ALGO → {recipient}")

    # ── Step 3: Ageniz validates + executes ────────────────────────
    result = firewall.pay(recipient=recipient, amount_algo=final_amount, context=prompt)

    result["llm_extracted"] = {
        "recipient":     recipient,
        "amount_algo":   final_amount,
        "intent":        intent,
        "amount_source": "gemini" if amount_algo else "default"
    }

    # ── Parse layer info from Oracle debug ────────────────────────
    debug = result.get("debug") or {}
    layer_hit = debug.get("layer", "")

    result["layer_info"] = {
        "layer_hit":    layer_hit,
        "wallet_tier":  debug.get("wallet_tier", "UNKNOWN"),
        "vendor_name":  debug.get("vendor_name", "unknown"),
        "reason":       debug.get("reason", ""),
        "balance_algo": debug.get("balance_algo"),
        "unique_senders": debug.get("unique_senders"),
        "wallet_age_days": debug.get("wallet_age_days"),
        "ml_confidence": result.get("score"),
        "effective_cap": debug.get("effective_cap_algo"),
    }

    # 🚀 DYNAMIC LAYER TRACING (NEW LOGIC)
    # This generates the exact [pass, skip, fail] array for the frontend
    # In process_agent_request, replace the layer_states logic with this:

# 🚀 DYNAMIC LAYER TRACING (FIXED & MERGED STATE MACHINE)
    status = result.get("status", "")
    layer_hit_lower = layer_hit.lower()
    wallet_tier = debug.get("wallet_tier", "UNKNOWN")
    is_verified = (wallet_tier == "VERIFIED")

    # 1. Handle Successful Tracks
    if status in ["SUCCESS", "SAFE"]:
        if is_verified:
            # Fast-track: L0 passed, L1/L2 bypassed, L3/L4 passed
            layer_states = ["pass", "skip", "skip", "pass", "pass"]
        else:
            # Unknown but Safe: L0 skipped, L1/L2/L3/L4 verified manually and passed
            layer_states = ["skip", "pass", "pass", "pass", "pass"]
    
    # 2. Handle Rejection Tracks
    else:
        LAYER_MAP = {
            "spend_cap_verified_per_txn":   0,
            "spend_cap_verified_daily":     0,
            "spend_cap_global_unknown":     1,
            "heuristics_burner":            2,
            "heuristics_unverified_cap":    2,
            "heuristics_trusted_cap":       2,
            "heuristics_trusted_daily_cap": 2,
            "ml_scoring":                   3,
        }
        
        # Override for ML quarantine
        if status in ["QUARANTINE", "ANOMALY"]:
            blocked_idx = 3
        else:
            blocked_idx = LAYER_MAP.get(layer_hit_lower, 4)

        layer_states = []
        for i in range(5):
            if i > blocked_idx:
                layer_states.append("skip")
            elif i == blocked_idx:
                layer_states.append("fail")
            else:
                if is_verified:
                    if i == 0: layer_states.append("pass")
                    elif i in [1, 2]: layer_states.append("skip")
                    else: layer_states.append("pass")
                else:
                    if i == 0: layer_states.append("skip")
                    else: layer_states.append("pass")

    result["layer_states"] = layer_states

    # ── Step 4: If payment succeeded, fetch premium data ──────────
    if result.get("status") == "SUCCESS":
        tx_id       = result.get("tx_id")
        data_result = fetch_premium_data(tx_id)
        result["premium_data"] = data_result.get("data") if data_result["success"] else None
        result["data_fetched"] = data_result["success"]
        result["data_error"]   = data_result.get("reason") if not data_result["success"] else None

    return result

