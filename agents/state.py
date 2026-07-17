"""
PHASE 4a: State Schema
------------------------
LangGraph passes a single "state" object between nodes. Every node reads some
fields and writes/updates others. Defining this clearly up front is the most
important design step in any LangGraph project -- get the state schema right
and the graph logic becomes simple; get it wrong and nodes fight each other.

Think of `session_state` as the "case file" for one phone call that keeps
growing as more transcript chunks arrive.
"""

from typing import TypedDict, List, Dict, Any


class ScamDetectionState(TypedDict, total=False):
    session_id: str
    language: str

    # The full transcript received so far (chunks accumulate as the "call" progresses)
    transcript_chunks: List[str]

    # The newest chunk being processed in this pass through the graph
    current_chunk: str

    # Output of Node 1 (suspicion filter): quick heuristic score 0.0-1.0
    keyword_suspicion_score: float

    # Output of Node 2 (RAG retrieval): matched known scam patterns
    matched_patterns: List[Dict[str, Any]]

    # Output of Node 3 (compound risk correlation): categories of risk seen so far
    # e.g. {"authority_impersonation", "isolation_and_threat", "financial_pressure"}
    risk_categories_seen: List[str]

    # Running, cumulative confidence that this session is a scam (0.0-1.0)
    suspicion_score: float

    # Final decision made by the graph: "monitor" | "warn" | "alert"
    decision: str

    # Human-readable alert message generated for the (simulated) victim
    alert_message: str

    # Structured report for a (simulated) authority / NCRB-style log
    incident_report: Dict[str, Any]
    city: str
    latitude: float
    longitude: float
