"""
PHASE 4b: Nodes
----------------
Each node is a plain Python function: (state) -> partial state update.
This is the core LangGraph mental model -- a node is NOT a class, not an
"agent" with hidden magic, just a function that reads state and returns
the fields it wants to change.

We have 5 nodes, mirroring the case study pipeline:
  1. suspicion_filter        - cheap keyword/heuristic pre-filter
  2. rag_retrieval            - semantic match against known scam patterns (RAG)
  3. compound_risk_correlator - combines signals across chunks (multi-signal reasoning)
  4. decision_node            - routes to monitor / warn / alert based on score
  5. action_node              - generates the victim alert + incident report (via MCP tools)
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from localization.alerts import generate_localized_alert
from rag.knowledge_base import ScamPatternKB
from agents.state import ScamDetectionState
from db.mongo import incident_collection

# Shared KB instance (loaded once, reused across all node calls)
_kb = ScamPatternKB()

# Cheap keyword signals used for the first-pass filter (Node 1).
# In production you'd replace/augment this with a small trained classifier.
SUSPICIOUS_KEYWORDS = {
    "customs": 0.2, "cbi": 0.25, "enforcement directorate": 0.25, "police": 0.15,
    "arrest": 0.25, "warrant": 0.2, "parcel": 0.15, "aadhaar": 0.1, "illegal": 0.15,
    "do not disconnect": 0.35, "cannot disconnect": 0.35, "confidential investigation": 0.3,
    "digital arrest": 0.4, "verification account": 0.3, "refunded": 0.15,
    "transfer": 0.15, "security deposit": 0.2, "lookout notice": 0.25, "non-bailable": 0.25,
}


def suspicion_filter(state: ScamDetectionState) -> dict:
    """Node 1: fast, cheap keyword heuristic. Runs on every chunk before anything expensive."""
    text = state["current_chunk"].lower()
    score = 0.0
    for kw, weight in SUSPICIOUS_KEYWORDS.items():
        if kw in text:
            score += weight
    score = min(score, 1.0)
    return {"keyword_suspicion_score": score}


def rag_retrieval(state: ScamDetectionState) -> dict:
    """Node 2: retrieve nearest known scam patterns from the RAG knowledge base."""
    matches = _kb.retrieve(state["current_chunk"], top_k=2)
    # With cosine distance (0 = identical, 1 = no similarity), a real semantic
    # overlap with a known scam pattern typically lands well under 0.85.
    # Text with zero shared vocabulary sits exactly at distance 1.0.
    strong_matches = [m for m in matches if m["score"] > 0.75]
    return {"matched_patterns": strong_matches}


def compound_risk_correlator(state: ScamDetectionState) -> dict:
    """
    Node 3: THE key multi-signal reasoning step.
    No single phrase proves a scam. But authority impersonation + isolation/threat +
    financial pressure occurring TOGETHER across the conversation is the diagnostic
    combination documented in real digital-arrest cases. This node tracks which
    risk categories have appeared so far across the whole session, not just this chunk.
    """
    seen = set(state.get("risk_categories_seen", []))
    for m in state.get("matched_patterns", []):
        seen.add(m["category"])

    # Base score blends the keyword filter with RAG match confidence
    base = state.get("keyword_suspicion_score", 0.0)
    if state.get("matched_patterns"):
        rag_confidence = max(m["score"] for m in state["matched_patterns"])  # cosine distance is already 0..1
        base = max(base, rag_confidence)

    # Compound bonus: reward co-occurrence of distinct risk categories across the session
    compound_bonus = 0.15 * (len(seen) - 1) if len(seen) > 1 else 0.0

    # Running score is cumulative but capped at 1.0; never decreases (a case file only strengthens)
    prior = state.get("suspicion_score", 0.0)
    new_score = min(1.0, max(prior, base) + compound_bonus)

    return {
        "risk_categories_seen": list(seen),
        "suspicion_score": new_score,
    }


def decision_node(state: ScamDetectionState) -> dict:
    """Node 4: routing decision based on cumulative suspicion score."""
    score = state.get("suspicion_score", 0.0)
    if score >= 0.75:
        decision = "alert"
    elif score >= 0.45:
        decision = "warn"
    else:
        decision = "monitor"
    return {"decision": decision}


def action_node(state: ScamDetectionState) -> dict:

    decision = state.get("decision", "monitor")
    categories = state.get("risk_categories_seen", [])
    score = state.get("suspicion_score", 0.0)

    alert_message = ""

    if decision in ("warn", "alert"):
        lang = state.get("language", "en")

        alert_message = generate_localized_alert(
        risk_categories=categories,
        confidence=score,
        lang=lang
    )

    incident_report = {}

    if decision == "alert":

        incident_report = {

    "session_id": state["session_id"],

    "confidence": score,

    "city": state.get("city"),

    "latitude": state.get("latitude"),

    "longitude": state.get("longitude"),

    "matched_pattern_ids": [
        m["id"]
        for m in state.get("matched_patterns", [])
    ],

    "risk_categories": categories,

    "transcript_snapshot": state.get("transcript_chunks", [])
    }
        # Save permanently
        incident_collection.update_one(
        {"session_id": incident_report["session_id"]},
        {"$set": incident_report},
        upsert=True
        )
    return {
        "alert_message": alert_message,
        "incident_report": incident_report,
    }