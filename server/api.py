import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

from rag.knowledge_base import ScamPatternKB
from agents.graph import process_call_session
from agents.nodes import SUSPICIOUS_KEYWORDS, RAG_MATCH_THRESHOLD
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

from db.mongo import incident_collection  # noqa: E402

_kb = ScamPatternKB()
_fraud_graph = FraudNetworkGraph()
_geo = GeoCrimeIntelligence()


def _hydrate_fraud_graph():
    """
    Rebuild the in-memory fraud graph from persisted incidents at startup.

    The graph itself is an in-memory NetworkX structure, so without this it
    started EMPTY on every restart -- /intelligence/campaigns would report zero
    campaigns even with hundreds of incidents sitting in the database. Incidents
    were being persisted and then never read back.
    """
    count = 0
    for incident in incident_collection.find():
        _fraud_graph.add_incident(incident)
        count += 1
    if count:
        print(f"[api] Hydrated fraud graph with {count} persisted incident(s)")
    return count


_hydrate_fraud_graph()


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
    """
    Single-message check -- what a WhatsApp bot or SMS gateway would call
    when a user forwards one suspicious message for a quick verdict.
    """
    # The Qdrant retriever always returns "score" (cosine similarity), so the
    # old `elif "distance"` branch was unreachable. Using the shared
    # RAG_MATCH_THRESHOLD keeps this endpoint, the LangGraph pipeline and the
    # MCP server judging the same text identically -- previously each used its
    # own hard-coded cutoff.
    text_lower = req.text.lower()
    keyword_score = min(
        sum(w for kw, w in SUSPICIOUS_KEYWORDS.items() if kw in text_lower),
        1.0,
    )

    matches = _kb.retrieve(req.text, top_k=3)
    strong_matches = [m for m in matches if m["score"] > RAG_MATCH_THRESHOLD]

    categories = list({m["category"] for m in strong_matches})

    # Blend the cheap keyword signal with RAG confidence, mirroring node 1 +
    # node 2 in the pipeline. The previous version ignored keywords entirely,
    # so this endpoint was strictly less sensitive than the graph it fronts.
    confidence = max(
        keyword_score,
        max((m["score"] for m in strong_matches), default=0.0),
    )

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
    """
    Full multi-chunk call analysis -- what an IVR/call-recording pipeline
    would call once a call session's transcript (partial or complete) is ready.

    Location is passed straight into the pipeline, so action_node geo-tags the
    incident when it writes it. Because db/mongo.py and GeoCrimeIntelligence now
    share one collection, /intelligence/hotspots picks these up automatically --
    no separate _geo.add_incident() call is needed.
    """

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