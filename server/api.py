"""
PHASE 11: Client-Facing Web API (this is your deployment layer)
--------------------------------------------------------------------
Gap addressed: "WhatsApp / IVR / Mobile integration -- Partially: MCP makes
this possible, but you haven't built those clients."

This FastAPI server is what you actually deploy to a machine/cloud service.
It's the HTTP front door that:
  - WhatsApp Business API webhooks can POST to
  - An IVR system (e.g. Exotel/Twilio call flow) can POST call transcripts to
  - A mobile app can call directly

It wraps the SAME underlying pipeline (LangGraph + RAG) you already built --
this file adds no new "intelligence", it just exposes what you have over HTTP
so real clients can reach it. This is also literally "how do I deploy this
project" from earlier: run this file with a production server (uvicorn/
gunicorn) behind a domain, and you have a deployed service.

Run locally:
    uvicorn server.api:app --host 0.0.0.0 --port 8000 --reload

Then:
    curl -X POST http://localhost:8000/webhook/message \
      -H "Content-Type: application/json" \
      -d '{"text": "do not disconnect the call or you will be arrested", "lang": "hi"}'
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from rag.knowledge_base import ScamPatternKB
from agents.graph import process_call_session
from agents.nodes import SUSPICIOUS_KEYWORDS
from localization.alerts import generate_localized_alert, SUPPORTED_LANGUAGES
from graph_intelligence.fraud_network import FraudNetworkGraph
from geospatial.crime_intelligence import GeoCrimeIntelligence

app = FastAPI(
    title="Digital Arrest Shield API",
    description="Real-time digital-arrest scam detection service",
    version="1.0.0",
)

_kb = ScamPatternKB()
_fraud_graph = FraudNetworkGraph()          # in-memory demo store; swap for a real DB in production
_geo_intel = GeoCrimeIntelligence()          # same


# ---------- Request/response models ----------

class MessageCheckRequest(BaseModel):
    text: str
    lang: str = "en"


class SessionAnalyzeRequest(BaseModel):
    session_id: str
    transcript_chunks: List[str]
    lang: str = "en"
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


# ---------- Core detection endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok", "supported_languages": SUPPORTED_LANGUAGES}


@app.post("/webhook/message")
def webhook_message(req: MessageCheckRequest):
    """
    Single-message check -- what a WhatsApp bot or SMS gateway would call
    when a user forwards one suspicious message for a quick verdict.
    """
    text_lower = req.text.lower()
    keyword_score = min(sum(w for kw, w in SUSPICIOUS_KEYWORDS.items() if kw in text_lower), 1.0)
    matches = _kb.retrieve(req.text, top_k=3)
    strong_matches = [m for m in matches if m["distance"] < 0.85]

    categories = list({m["category"] for m in strong_matches})
    confidence = max(keyword_score, 1 - min((m["distance"] for m in strong_matches), default=1.0))

    alert = ""
    if confidence >= 0.45:
        alert = generate_localized_alert(categories, confidence, lang=req.lang)

    return {
        "confidence": round(confidence, 2),
        "matched_patterns": strong_matches,
        "alert_message": alert,
    }


@app.post("/webhook/ivr_session")
def webhook_ivr_session(req: SessionAnalyzeRequest):
    """
    Full multi-chunk call analysis -- what an IVR/call-recording pipeline
    would call once a call session's transcript (partial or complete) is ready.
    Also logs ALERT-level incidents into the fraud network graph and geo intel
    layers so cross-victim patterns and hotspots can be detected.
    """
    final_state = process_call_session(req.session_id, req.transcript_chunks)

    localized_alert = ""
    if final_state["decision"] in ("warn", "alert"):
        localized_alert = generate_localized_alert(
            final_state.get("risk_categories_seen", []),
            final_state.get("suspicion_score", 0.0),
            lang=req.lang,
        )

    if final_state["decision"] == "alert" and final_state.get("incident_report"):
        _fraud_graph.add_incident(final_state["incident_report"])
        if req.city and req.lat is not None and req.lon is not None:
            _geo_intel.add_incident(
                req.session_id, req.lat, req.lon, req.city,
                final_state["suspicion_score"], final_state["risk_categories_seen"],
            )

    return {
        "session_id": req.session_id,
        "suspicion_score": round(final_state.get("suspicion_score", 0.0), 2),
        "decision": final_state.get("decision"),
        "risk_categories_seen": final_state.get("risk_categories_seen", []),
        "alert_message": localized_alert,
    }


# ---------- Intelligence / dashboard endpoints (for law-enforcement side) ----------

@app.get("/intelligence/campaigns")
def get_campaigns():
    """Suspected coordinated fraud campaigns detected across all logged incidents so far."""
    return _fraud_graph.summary()


@app.get("/intelligence/hotspots")
def get_hotspots(min_incidents: int = 2):
    """City-level fraud hotspots detected across all logged incidents so far."""
    return {"hotspots": _geo_intel.city_hotspots(min_incidents=min_incidents)}
