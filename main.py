"""
VulnBot FastAPI Backend
Receives prompts from frontend, processes through agent,
returns Ageniz firewall verdict.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import process_agent_request, firewall,fetch_premium_data
app = FastAPI(
    title="VulnBot — Secured by Ageniz",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    prompt: str
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main endpoint. Receives prompt, returns firewall verdict.
    """
    result = process_agent_request(request.prompt)

    # 🔥 THE FIX: Attach the weather data to the payload if the payment succeeded!
    if result.get("status") == "SUCCESS" and "tx_id" in result:
        # Fetch the data using the transaction ID
        weather_response = fetch_premium_data(result["tx_id"])
        
        # Inject the actual data dictionary into the result so the frontend can read it
        result["premium_data"] = weather_response.get("data")

    return {"firewall_verdict": result}

@app.get("/status")
async def agent_status():
    """Returns current agent wallet status and reputation."""
    return firewall.get_status()

@app.get("/health")
async def health():
    return {
        "status":  "online",
        "agent":   "VulnBot v2.0",
        "firewall": "Ageniz v2.0",
        "app_id":  firewall.app_id
    }
