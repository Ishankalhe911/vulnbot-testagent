"""
VulnBot Agent v3.0 — Real LLM Integration
Gemini LLM is deliberately vulnerable to prompt injection.
Ageniz is the ONLY security layer.
"""

import os
import json
import httpx
import google.generativeai as genai
from dotenv import load_dotenv
from ageniz_sdk.core import AgenizSDK

load_dotenv()

# ── Gemini ─────────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

# ── Config ─────────────────────────────────────────────────────────────────
ORACLE_URL        = os.getenv("ORACLE_URL", "https://ageniz-backend.onrender.com")
OPENWEATHER_KEY   = os.getenv("OPENWEATHER_API_KEY", "")
WEATHER_CITY      = "Mumbai"

VENDOR_DEFAULTS = {
    "weather": 1.0,
    "traffic": 1.0,
    "server":  2.0,
    "data":    1.0,
    "api":     1.0,
}
DEFAULT_AMOUNT = 1.0

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

# ── Ageniz SDK ─────────────────────────────────────────────────────────────
firewall = AgenizSDK(
    wallet_mnemonic=os.getenv("DEPLOYER_MNEMONIC"),
    ageniz_api_key=os.getenv("AGENIZ_API_KEY"),
    app_id=int(os.getenv("APP_ID", 0)),
    oracle_url=ORACLE_URL
)
firewall.opt_in()


# ── Layer state mapping — covers every Oracle layer string ─────────────────
LAYER_INDEX_MAP = {
    # L0 — verified vendor cap breach
    "spend_cap_verified_per_txn":    0,
    "spend_cap_verified_daily":      0,
    # L1 — global unknown daily cap
    "spend_cap_global_unknown":      1,
    # L2 — heuristics
    "heuristics_burner":             2,
    "heuristics_unverified_cap":     2,
    "heuristics_trusted_cap":        2,
    "heuristics_trusted_daily_cap":  2,
    # L3 — ML scoring
    "ml_scoring":                    3,
    # L4 — signature / blockchain
    "approved":                      4,
}


def build_layer_states(status: str, layer_hit: str, wallet_tier: str) -> list:
    """
    Returns a 5-element list of "pass" | "fail" | "skip"
    covering every possible Oracle outcome properly.
    """
    is_verified = (wallet_tier == "VERIFIED")

    # ── 1. SUCCESS ROUTING ──
    if status in ["SUCCESS", "SAFE"]:
        if is_verified:
            # TSA PreCheck: L0 passes, L1/L2 bypassed, L3/L4 pass
            return ["pass", "skip", "skip", "pass", "pass"]
        else:
            # Unknown but safe: L0 skipped, L1-L4 pass
            return ["skip", "pass", "pass", "pass", "pass"]

    # ── 2. FAILURE ROUTING ──
    # If the transaction is QUARANTINED, it's always an ML failure (L3)
    if status in ["QUARANTINE", "ANOMALY"]:
        blocked_idx = 3
    else:
        blocked_idx = LAYER_INDEX_MAP.get(layer_hit.lower(), 4)

    states = []
    for i in range(5):
        if i > blocked_idx:
            states.append("skip")
        elif i == blocked_idx:
            states.append("fail")
        else:
            # Passed layers before the block
            if is_verified:
                if i == 0: states.append("pass")
                elif i in [1, 2]: states.append("skip")
                else: states.append("pass")
            else:
                if i == 0: states.append("skip")
                else: states.append("pass")
                
    return states
   


def parse_prompt_with_gemini(prompt: str) -> dict:
    try:
        full_prompt = f"{AGENT_SYSTEM_PROMPT}\n\nUser message: {prompt}"
        response    = model.generate_content(full_prompt)
        raw_text    = response.text.strip()

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
        return {"recipient": None, "amount_algo": None, "intent": "parse_error", "error": str(e)}
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return {"recipient": None, "amount_algo": None, "intent": "parse_error", "error": str(e)}


def resolve_amount(amount_algo, prompt: str) -> float:
    if amount_algo:
        try:
            amount = float(amount_algo)
            if amount > 0:
                return amount
        except (ValueError, TypeError):
            pass

    prompt_lower = prompt.lower()
    for keyword, default in VENDOR_DEFAULTS.items():
        if keyword in prompt_lower:
            print(f"⚠️  No amount — using {keyword} default: {default} ALGO")
            return default

    print(f"⚠️  Fallback to global default: {DEFAULT_AMOUNT} ALGO")
    return DEFAULT_AMOUNT


def fetch_premium_data(tx_id: str) -> dict:
    """
    Real x402 flow — fetch live weather data using TxID as payment receipt.
    Falls back to mock if OPENWEATHER_API_KEY not set.
    """
    try:
        print(f"📦 [x402] Verifying receipt: {tx_id[:16]}...")

        if not OPENWEATHER_KEY:
            print("⚠️  OPENWEATHER_API_KEY not set — using mock data")
            return _mock_weather(tx_id)

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
            data = {
                "city":          raw["name"],
                "country":       raw["sys"]["country"],
                "temperature":   f"{raw['main']['temp']}°C",
                "feels_like":    f"{raw['main']['feels_like']}°C",
                "condition":     raw["weather"][0]["description"].title(),
                "humidity":      f"{raw['main']['humidity']}%",
                "wind_speed":    f"{raw['wind']['speed']} m/s",
                "visibility":    f"{raw.get('visibility', 0) // 1000} km",
                "data_source":   "OpenWeatherMap (Live)",
                "x402_receipt":  tx_id[:20] + "...",
                "agent_message": f"Live weather for {raw['name']} — paid & verified via Ageniz x402"
            }
            print(f"✅ Real weather data fetched for {raw['name']}")
            return {"success": True, "data": data}

        else:
            print(f"⚠️ Weather API {response.status_code} — falling back to mock")
            return _mock_weather(tx_id)

    except Exception as e:
        print(f"❌ Weather fetch error: {e} — falling back to mock")
        return _mock_weather(tx_id)


def _mock_weather(tx_id: str) -> dict:
    return {
        "success": True,
        "data": {
            "city":          "Mumbai",
            "temperature":   "31°C",
            "condition":     "Partly Cloudy",
            "humidity":      "78%",
            "wind_speed":    "14 km/h",
            "data_source":   "Mock (set OPENWEATHER_API_KEY for live data)",
            "x402_receipt":  tx_id[:20] + "...",
            "agent_message": "Payment verified — add OPENWEATHER_API_KEY for real weather"
        }
    }


def process_agent_request(prompt: str) -> dict:
    print(f"\n🤖 VulnBot received: '{prompt}'")

    # Step 1 — Gemini extracts intent
    parsed      = parse_prompt_with_gemini(prompt)
    recipient   = parsed.get("recipient")
    amount_algo = parsed.get("amount_algo")
    intent      = parsed.get("intent", "unknown")

    print(f"   Extracted: recipient={recipient} | amount={amount_algo} | intent={intent}")

    if intent == "parse_error":
        return {
            "status": "ERROR",
            "reason": f"LLM parsing failed: {parsed.get('error', 'unknown')}",
            "score":  None,
            "layer_states": ["skip", "skip", "skip", "skip", "fail"],
            "layer_info": {"layer_hit": "parse_error", "reason": "Gemini failed to parse intent"}
        }

    if not recipient or intent == "no_payment":
        return {
            "status":     "NO_INTENT",
            "reason":     "No payment intent detected.",
            "llm_intent": intent,
            "score":      None,
            "layer_states": ["skip", "skip", "skip", "skip", "skip"],
            "layer_info": {}
        }

    # Step 2 — Resolve amount
    final_amount = resolve_amount(amount_algo, prompt)
    print(f"🛡️  Routing to Ageniz: {final_amount} ALGO → {recipient}")

    # Step 3 — Ageniz validates + executes
    result = firewall.pay(recipient=recipient, amount_algo=final_amount, context=prompt)

    # Attach LLM context
    result["llm_extracted"] = {
        "recipient":     recipient,
        "amount_algo":   final_amount,
        "intent":        intent,
        "amount_source": "gemini" if amount_algo else "default"
    }

    # Extract debug info
    debug       = result.get("debug") or {}
    layer_hit   = debug.get("layer", "")
    wallet_tier = debug.get("wallet_tier", "UNKNOWN")
    status      = result.get("status", "ERROR")

    # Build layer_info for frontend heuristic details
    result["layer_info"] = {
        "layer_hit":       layer_hit,
        "wallet_tier":     wallet_tier,
        "vendor_name":     debug.get("vendor_name", "unknown"),
        "reason":          debug.get("reason", ""),
        "balance_algo":    debug.get("balance_algo"),
        "unique_senders":  debug.get("unique_senders"),
        "wallet_age_days": debug.get("wallet_age_days"),
        "ml_confidence":   result.get("score"),
        "effective_cap":   debug.get("effective_cap_algo"),
    }

    # Build layer_states covering every possible outcome
    result["layer_states"] = build_layer_states(status, layer_hit, wallet_tier)

    print(f"   Layer hit: '{layer_hit}' | Status: {status} | States: {result['layer_states']}")

    # Step 4 — Fetch real data if payment succeeded
    if status == "SUCCESS":
        tx_id       = result.get("tx_id")
        data_result = fetch_premium_data(tx_id)
        result["premium_data"] = data_result.get("data") if data_result["success"] else None
        result["data_fetched"] = data_result["success"]
        result["data_error"]   = data_result.get("reason") if not data_result["success"] else None

    return result