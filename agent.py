"""
VulnBot Agent v3.0 — Real LLM Integration
Gemini LLM is deliberately vulnerable to prompt injection.
Ageniz is the ONLY security layer.
"""

import os
import json
import time
import httpx
import google.generativeai as genai
from dotenv import load_dotenv
from ageniz_sdk.core import AgenizSDK

load_dotenv()

# ── Gemini ─────────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

# ── Config ─────────────────────────────────────────────────────────────────
ORACLE_URL = os.getenv("ORACLE_URL", "https://ageniz-backend.onrender.com")

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


# ── Layer state mapping ────────────────────────────────────────────────────
LAYER_INDEX_MAP = {
    "spend_cap_verified_per_txn":    0,
    "spend_cap_verified_daily":      0,
    "spend_cap_global_unknown":      1,
    "heuristics_burner":             2,
    "heuristics_unverified_cap":     2,
    "heuristics_trusted_cap":        2,
    "heuristics_trusted_daily_cap":  2,
    "ml_scoring":                    3,
    "approved":                      4,
}


def build_layer_states(status: str, layer_hit: str, wallet_tier: str) -> list:
    is_verified = (wallet_tier == "VERIFIED")

    if status in ["SUCCESS", "SAFE"]:
        if is_verified:
            return ["pass", "skip", "skip", "pass", "pass"]
        else:
            return ["skip", "pass", "pass", "pass", "pass"]

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

        parsed = json.loads(raw_text)

        return {
            "recipient":   parsed.get("recipient"),
            "amount_algo": parsed.get("amount_algo"),
            "intent":      parsed.get("intent", "unknown"),
            "llm_raw":     raw_text
        }

    except json.JSONDecodeError as e:
        print(f"[VulnBot] ❌ Gemini JSON parse error: {e}")
        return {"recipient": None, "amount_algo": None, "intent": "parse_error", "error": str(e)}
    except Exception as e:
        print(f"[VulnBot] ❌ Gemini error: {e}")
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
            print(f"[VulnBot] ⚠️  No amount specified — using {keyword} default: {default} ALGO")
            return default

    print(f"[VulnBot] ⚠️  Fallback to global default: {DEFAULT_AMOUNT} ALGO")
    return DEFAULT_AMOUNT


def fetch_premium_data(tx_id: str) -> dict:
    """
    Agent redeeming its TxID at the remote Vendor API — true x402 flow.
    """
    print(f"\n[VulnBot] 🤖 Hit Paywall! Presenting on-chain receipt to Vendor...")
    print(f"[VulnBot] 📦 TxID Receipt: {tx_id[:20]}...")

    base_url   = ORACLE_URL.rstrip('/')
    vendor_url = f"{base_url}/api/v1/premium-data"

    try:
        response = httpx.get(
            vendor_url,
            headers={"x-payment-receipt": tx_id},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json().get("data", {})
            temp      = data.get("temperature", "?")
            condition = data.get("condition", "?")
            print(f"[VulnBot] 🌦️  Data Received: {temp}, {condition}!")
            print(f"[VulnBot] ✅ x402 flow complete — premium resource unlocked!\n")
            return {"success": True, "data": data}
        else:
            error_detail = response.json().get("detail", "Vendor rejected payment")
            print(f"[VulnBot] ❌ Vendor rejected receipt (HTTP {response.status_code}): {error_detail}")
            return {"success": False, "reason": error_detail}

    except Exception as e:
        print(f"[VulnBot] ❌ Network error connecting to Vendor: {e}")
        return {"success": False, "reason": f"Network Error: {str(e)}"}


def process_agent_request(prompt: str) -> dict:
    t_start = time.time()

    print(f"\n{'='*60}")
    print(f"[VulnBot] 🤖 New Request: '{prompt}'")
    print(f"{'='*60}")

    # ── Step 1: Gemini extracts intent ─────────────────────────────
    print(f"[VulnBot] 🧠 Sending to Gemini LLM for intent extraction...")
    parsed      = parse_prompt_with_gemini(prompt)
    recipient   = parsed.get("recipient")
    amount_algo = parsed.get("amount_algo")
    intent      = parsed.get("intent", "unknown")

    print(f"[VulnBot] 🧠 Gemini extracted → recipient: {recipient[:12] if recipient else 'None'}... | amount: {amount_algo} ALGO | intent: {intent}")

    if intent == "parse_error":
        print(f"[VulnBot] ❌ LLM parsing failed — aborting")
        return {
            "status": "ERROR",
            "reason": f"LLM parsing failed: {parsed.get('error', 'unknown')}",
            "score":  None,
            "layer_states": ["skip", "skip", "skip", "skip", "fail"],
            "layer_info": {"layer_hit": "parse_error", "reason": "Gemini failed to parse intent"}
        }

    if not recipient or intent == "no_payment":
        print(f"[VulnBot] ℹ️  No payment intent detected — skipping firewall")
        return {
            "status":     "NO_INTENT",
            "reason":     "No payment intent detected.",
            "llm_intent": intent,
            "score":      None,
            "layer_states": ["skip", "skip", "skip", "skip", "skip"],
            "layer_info": {}
        }

    # ── Step 2: Resolve amount ──────────────────────────────────────
    final_amount = resolve_amount(amount_algo, prompt)

    # ── Step 3: Ageniz firewall ─────────────────────────────────────
    print(f"\n[VulnBot] 🛡️  Routing to Ageniz Firewall: {final_amount} ALGO → {recipient[:16]}...")
    print(f"[VulnBot] ⏳ Awaiting Oracle ML attestation + Algorand settlement...")

    t_ageniz = time.time()
    result    = firewall.pay(recipient=recipient, amount_algo=final_amount, context=prompt)
    t_ageniz_elapsed = time.time() - t_ageniz

    # ── Step 4: Attach LLM context ──────────────────────────────────
    result["llm_extracted"] = {
        "recipient":     recipient,
        "amount_algo":   final_amount,
        "intent":        intent,
        "amount_source": "gemini" if amount_algo else "default"
    }

    debug       = result.get("debug") or {}
    layer_hit   = debug.get("layer", "")
    wallet_tier = debug.get("wallet_tier", "UNKNOWN")
    status      = result.get("status", "ERROR")

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

    result["layer_states"] = build_layer_states(status, layer_hit, wallet_tier)

    if status == "SUCCESS":
        tx_id = result.get("tx_id")
        print(f"\n[VulnBot] ✅ Ageniz approved in {t_ageniz_elapsed:.1f}s!")
        print(f"[VulnBot] ⛓️  Block finalized on Algorand! TxID: {tx_id[:20]}...")
        print(f"[VulnBot] 🔗 Explorer: https://testnet.explorer.perawallet.app/tx/{tx_id}")

        # ── Step 5: x402 data fetch ─────────────────────────────────
        data_result            = fetch_premium_data(tx_id)
        result["premium_data"] = data_result.get("data") if data_result["success"] else None
        result["data_fetched"] = data_result["success"]
        result["data_error"]   = data_result.get("reason") if not data_result["success"] else None

    elif status in ["BLOCKED", "QUARANTINE", "ANOMALY"]:
        print(f"\n[VulnBot] 🛡️  Ageniz BLOCKED transaction in {t_ageniz_elapsed:.1f}s!")
        print(f"[VulnBot] 🚨 Reason: {debug.get('reason', 'Anomaly detected')}")

    total_elapsed = time.time() - t_start
    print(f"\n[VulnBot] ⏱️  Total request time: {total_elapsed:.2f}s")
    print(f"{'='*60}\n")

    return result