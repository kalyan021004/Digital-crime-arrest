import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

from rag.knowledge_base import ScamPatternKB
from agents.graph import process_call_session
from localization.alerts import (
    generate_localized_alert,
    SUPPORTED_LANGUAGES,
)

from graph_intelligence.fraud_network import FraudNetworkGraph
from geospatial.crime_intelligence import GeoCrimeIntelligence

app = FastAPI(
    title="Digital Arrest Shield API",
    description="Real-time Digital Arrest Scam Detection",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_kb = ScamPatternKB()
_fraud_graph = FraudNetworkGraph()
_geo = GeoCrimeIntelligence()


# -------------------------------------------------
# Request Models
# -------------------------------------------------

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


# -------------------------------------------------
# Health
# -------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "supported_languages": SUPPORTED_LANGUAGES,
    }


# -------------------------------------------------
# Single Message Detection
# -------------------------------------------------

@app.post("/webhook/message")
def webhook_message(req: MessageCheckRequest):

    matches = _kb.retrieve(req.text, top_k=3)

    strong_matches = []
    confidence = 0.0

    for m in matches:

        if "score" in m:

            if m["score"] > 0.75:

                strong_matches.append(m)
                confidence = max(confidence, m["score"])

        elif "distance" in m:

            if m["distance"] < 0.85:

                strong_matches.append(m)
                confidence = max(
                    confidence,
                    1 - m["distance"]
                )

    categories = list({
        m["category"]
        for m in strong_matches
    })

    alert = ""

    if confidence >= 0.45:

        alert = generate_localized_alert(
            categories,
            confidence,
            lang=req.lang,
        )

    return {
        "confidence": round(confidence, 2),
        "matched_patterns": strong_matches,
        "alert_message": alert,
    }


# -------------------------------------------------
# IVR Session Detection
# -------------------------------------------------

@app.post("/webhook/ivr_session")
def webhook_ivr_session(req: SessionAnalyzeRequest):

    final_state = process_call_session(
        session_id=req.session_id,
        chunks=req.transcript_chunks,
        city=req.city,
        latitude=req.lat,
        longitude=req.lon,
        language=req.lang,
    )

    return {
        "session_id": final_state.get("session_id"),
        "decision": final_state.get("decision"),
        "suspicion_score": round(
            final_state.get("suspicion_score", 0.0),
            2,
        ),
        "risk_categories_seen":
            final_state.get(
                "risk_categories_seen",
                [],
            ),
        "alert_message":
            final_state.get(
                "alert_message",
                "",
            ),
        "incident_saved":
            final_state.get("decision") == "alert",
    }


# -------------------------------------------------
# Intelligence APIs
# -------------------------------------------------

@app.get("/intelligence/campaigns")
def campaigns():
    return _fraud_graph.summary()


@app.get("/intelligence/hotspots")
def hotspots(min_incidents: int = 2):

    return {
        "hotspots":
            _geo.city_hotspots(
                min_incidents=min_incidents
            )
    }