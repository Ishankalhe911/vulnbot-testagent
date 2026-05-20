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
genai.configure(api_key="AIzaSyD6sHgYAlcdaIdTnvZLKMSJ3X_Qc7Xpw6I")
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
firewall = AgenizSDK(
    wallet_mnemonic=os.getenv("DEPLOYER_MNEMONIC"),
    ageniz_api_key="agz_live_471f5co1gu47n59f29olaa",
    app_id=int(os.getenv("APP_ID", 0)),
    oracle_url=ORACLE_URL
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

def fetch_premium_data(tx_id: str) -> dict:
    """
    After payment confirmed, fetch the actual resource using TxID as receipt.
    This completes the x402 flow.
    """
    try:
        print(f"📦 Fetching premium data with receipt: {tx_id}")
        response = httpx.get(
            f"{ORACLE_URL}/api/v1/premium-data",
            headers={"x-payment-receipt": tx_id},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Premium data received")
            return {
                "success": True,
                "data":    data
            }
        else:
            print(f"❌ Data fetch failed: {response.status_code}")
            return {
                "success": False,
                "reason":  f"API returned status {response.status_code}"
            }

    except Exception as e:
        print(f"❌ Data fetch error: {e}")
        return {
            "success": False,
            "reason":  str(e)
        }

def process_agent_request(prompt: str) -> dict:
    """
    Main agent logic.
    1. Gemini LLM parses prompt (can be tricked)
    2. Amount resolved (default if missing)
    3. Ageniz validates payment (cannot be tricked)
    4. If payment succeeds, fetch premium data using TxID
    """
    print(f"\n🤖 VulnBot received: '{prompt}'")

    # ── Step 1: Gemini extracts intent ────────────────────────────
    parsed = parse_prompt_with_gemini(prompt)
    print(f"   Extracted: recipient={parsed.get('recipient')} | amount={parsed.get('amount_algo')} | intent={parsed.get('intent')}")

    recipient   = parsed.get("recipient")
    amount_algo = parsed.get("amount_algo")
    intent      = parsed.get("intent", "unknown")

    # Handle parse errors
    if intent == "parse_error":
        return {
            "status": "ERROR",
            "reason": f"LLM parsing failed: {parsed.get('error', 'unknown')}",
            "score":  None
        }

    # No payment intent
    if not recipient or intent == "no_payment":
        return {
            "status":     "NO_INTENT",
            "reason":     "No payment intent found. Try: 'buy weather data' or 'pay for server cost'",
            "llm_intent": intent,
            "score":      None
        }

    # ── Step 2: Resolve amount ─────────────────────────────────────
    final_amount = resolve_amount(amount_algo, prompt)
    print(f"🛡️  Routing to Ageniz: {final_amount} ALGO → {recipient}")

    # ── Step 3: Ageniz validates + executes ────────────────────────
    result = firewall.pay(
        recipient=recipient,
        amount_algo=final_amount,
        context=prompt
    )

    # Add LLM context
    result["llm_extracted"] = {
        "recipient":     recipient,
        "amount_algo":   final_amount,
        "intent":        intent,
        "amount_source": "gemini" if amount_algo else "default"
    }

    # ── Step 4: If payment succeeded, fetch premium data ──────────
    if result.get("status") == "SUCCESS":
        tx_id       = result.get("tx_id")
        data_result = fetch_premium_data(tx_id)

        result["premium_data"] = data_result.get("data") if data_result["success"] else None
        result["data_fetched"] = data_result["success"]
        result["data_error"]   = data_result.get("reason") if not data_result["success"] else None

    return result