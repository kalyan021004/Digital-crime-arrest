"""
Regression tests for the compound risk scoring logic.

These deliberately stub out the RAG knowledge base so they run in
milliseconds without chromadb / sentence-transformers / torch. The scoring
logic is pure arithmetic over state -- it should be testable without loading
a 130MB embedding model.

Run:  python -m pytest tests/ -v
  or: python tests/test_scoring.py
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _install_stubs():
    """
    Stub the heavy imports in agents.nodes before it is imported.

    agents/nodes.py instantiates ScamPatternKB() at module import time, which
    would load an embedding model and hit Chroma. For scoring tests we only
    need the arithmetic, so we replace the KB and the Mongo collection.
    """
    kb_mod = types.ModuleType("rag.knowledge_base")

    class _StubKB:
        def retrieve(self, query, top_k=2):
            return []

    kb_mod.ScamPatternKB = _StubKB
    sys.modules["rag.knowledge_base"] = kb_mod

    mongo_mod = types.ModuleType("db.mongo")

    class _StubCollection:
        def __init__(self):
            self.saved = []

        def update_one(self, filt, update, upsert=False):
            self.saved.append(update.get("$set", {}))

        def find(self, filt=None):
            return iter(self.saved)

    mongo_mod.incident_collection = _StubCollection()
    mongo_mod.MONGO_AVAILABLE = False
    mongo_mod.INCIDENT_COLLECTION_NAME = "incident_reports"
    sys.modules["db.mongo"] = mongo_mod


_install_stubs()

from agents.nodes import compound_risk_correlator, decision_node  # noqa: E402


class TestScoreDoesNotRatchet(unittest.TestCase):
    """
    The bug: compound_bonus was re-added on EVERY chunk, so once two risk
    categories had been seen the score climbed +0.15 per chunk regardless of
    what was actually said. Any long-enough call eventually crossed the 0.75
    alert threshold on no new evidence at all.

    Since false-positive rate is the headline metric for this project, this is
    the single most important behaviour to pin down.
    """

    def test_score_is_stable_when_no_new_evidence_arrives(self):
        state = {
            "risk_categories_seen": ["authority_impersonation", "financial_pressure"],
            "matched_patterns": [],
            "matched_pattern_evidence": [],
            "keyword_suspicion_score": 0.0,
            "suspicion_score": 0.55,
            "transcript_chunks": ["a", "b", "c"],
            "current_chunk": "c",
        }

        # Ten silent chunks: nothing matches, no keywords fire.
        for _ in range(10):
            out = compound_risk_correlator(state)
            state.update(out)

        self.assertLessEqual(
            state["suspicion_score"], 0.55 + 1e-9,
            "Score grew without any new evidence -- the ratchet bug is back.",
        )
        self.assertEqual(
            decision_node(state)["decision"], "warn",
            "A stable 0.55 score must stay at 'warn', never escalate to 'alert'.",
        )

    def test_ten_quiet_chunks_never_reach_alert(self):
        """End-to-end version: a call that trips two categories once, then goes quiet."""
        state = {
            "risk_categories_seen": [],
            "matched_patterns": [],
            "matched_pattern_evidence": [],
            "keyword_suspicion_score": 0.30,
            "suspicion_score": 0.0,
            "transcript_chunks": ["opening"],
            "current_chunk": "opening",
        }
        # One chunk with two categories, mimicking a brief ambiguous moment.
        state["matched_patterns"] = [
            {"id": "SP001", "pattern_name": "A", "category": "authority_impersonation", "score": 0.40},
            {"id": "SP004", "pattern_name": "B", "category": "financial_pressure", "score": 0.35},
        ]
        state.update(compound_risk_correlator(state))

        # Then twenty chunks of ordinary conversation.
        state["matched_patterns"] = []
        state["keyword_suspicion_score"] = 0.0
        for _ in range(20):
            state.update(compound_risk_correlator(state))

        self.assertNotEqual(
            decision_node(state)["decision"], "alert",
            f"Quiet call escalated to alert (score={state['suspicion_score']:.2f}). "
            "This is exactly the false positive the FPR metric penalises.",
        )

    def test_genuine_escalation_still_works(self):
        """Guard against over-correcting: real accumulating evidence must still alert."""
        state = {
            "risk_categories_seen": [],
            "matched_patterns": [],
            "matched_pattern_evidence": [],
            "keyword_suspicion_score": 0.0,
            "suspicion_score": 0.0,
            "transcript_chunks": [],
            "current_chunk": "",
        }

        escalating = [
            ("authority_impersonation", "SP002", 0.80),
            ("isolation_and_threat", "SP003", 0.85),
            ("financial_pressure", "SP004", 0.88),
        ]
        for i, (cat, pid, score) in enumerate(escalating):
            state["transcript_chunks"] = state["transcript_chunks"] + [f"chunk{i}"]
            state["current_chunk"] = f"chunk{i}"
            state["matched_patterns"] = [
                {"id": pid, "pattern_name": pid, "category": cat, "score": score}
            ]
            state["keyword_suspicion_score"] = 0.3
            state.update(compound_risk_correlator(state))

        self.assertEqual(
            decision_node(state)["decision"], "alert",
            f"A textbook 3-stage digital arrest scam failed to alert "
            f"(score={state['suspicion_score']:.2f}).",
        )

    def test_score_never_decreases(self):
        """Monotonicity: a case file only strengthens."""
        state = {
            "risk_categories_seen": ["authority_impersonation"],
            "matched_patterns": [],
            "matched_pattern_evidence": [],
            "keyword_suspicion_score": 0.0,
            "suspicion_score": 0.62,
            "transcript_chunks": ["x"],
            "current_chunk": "x",
        }
        state.update(compound_risk_correlator(state))
        self.assertGreaterEqual(state["suspicion_score"], 0.62)


class TestEvidenceAccumulation(unittest.TestCase):
    """
    The bug: action_node read state["matched_patterns"], which rag_retrieval
    overwrites every chunk. Evidence from earlier chunks was silently dropped,
    so incident reports cited only the final chunk -- bad for the
    'auditability for legal admissibility' criterion, and it weakened the
    fraud-network graph, which links incidents by shared pattern IDs.
    """

    def test_evidence_accumulates_across_chunks(self):
        state = {
            "risk_categories_seen": [],
            "matched_patterns": [],
            "matched_pattern_evidence": [],
            "keyword_suspicion_score": 0.0,
            "suspicion_score": 0.0,
            "transcript_chunks": [],
            "current_chunk": "",
        }

        for i, pid in enumerate(["SP001", "SP002", "SP003"]):
            state["transcript_chunks"] = state["transcript_chunks"] + [f"chunk{i}"]
            state["current_chunk"] = f"chunk{i}"
            state["matched_patterns"] = [
                {"id": pid, "pattern_name": pid, "category": "authority_impersonation", "score": 0.80}
            ]
            state.update(compound_risk_correlator(state))

        ids = [e["id"] for e in state["matched_pattern_evidence"]]
        self.assertEqual(
            ids, ["SP001", "SP002", "SP003"],
            "Evidence from earlier chunks was lost -- only the last chunk survived.",
        )

    def test_evidence_is_not_duplicated(self):
        """The same pattern matching repeatedly should be cited once."""
        state = {
            "risk_categories_seen": [],
            "matched_patterns": [
                {"id": "SP002", "pattern_name": "X", "category": "authority_impersonation", "score": 0.9}
            ],
            "matched_pattern_evidence": [],
            "keyword_suspicion_score": 0.0,
            "suspicion_score": 0.0,
            "transcript_chunks": ["a"],
            "current_chunk": "a",
        }
        for _ in range(5):
            state.update(compound_risk_correlator(state))

        self.assertEqual(
            len(state["matched_pattern_evidence"]), 1,
            "Repeated matches of the same pattern should not be cited multiple times.",
        )

    def test_evidence_records_provenance(self):
        """Each cited pattern must say which chunk triggered it."""
        state = {
            "risk_categories_seen": [],
            "matched_patterns": [
                {"id": "SP003", "pattern_name": "Threat", "category": "isolation_and_threat", "score": 0.91}
            ],
            "matched_pattern_evidence": [],
            "keyword_suspicion_score": 0.0,
            "suspicion_score": 0.0,
            "transcript_chunks": ["one", "two"],
            "current_chunk": "two",
        }
        state.update(compound_risk_correlator(state))

        ev = state["matched_pattern_evidence"][0]
        self.assertEqual(ev["chunk_index"], 1)
        self.assertEqual(ev["chunk_text"], "two")
        self.assertEqual(ev["pattern_name"], "Threat")


if __name__ == "__main__":
    unittest.main(verbosity=2)
