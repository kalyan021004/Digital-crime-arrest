"""
PHASE 6: End-to-End Demo + Evaluation
----------------------------------------
This is the script you run for your hackathon demo. It:
  1. Loads all sample call transcripts (data/sample_transcripts.json)
  2. Runs each one through the LangGraph pipeline, chunk by chunk (simulating a live call)
  3. Prints the running suspicion score and final decision for each call
  4. Computes precision / recall / false-positive-rate against the known labels

This directly demonstrates the metrics your problem statement asks for:
"Digital arrest scam detection precision and recall ... false positive rate
for citizen-facing tools (must be very low)."
"""

import json
import os
from agents.graph import process_call_session

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_transcripts.json")


def run_demo():
    with open(DATA_PATH) as f:
        calls = json.load(f)

    results = []
    print("=" * 70)
    print("DIGITAL ARREST SCAM SHIELD -- Live Call Monitoring Demo")
    print("=" * 70)

    for call in calls:
        print(f"\n--- Session {call['session_id']} (true label: {call['label']}) ---")
        final_state = process_call_session(
            session_id=call["session_id"],
            chunks=call["chunks"],
            city=call.get("city"),
            latitude=call.get("latitude"),
            longitude=call.get("longitude"),
        )

        predicted_scam = final_state["decision"] in ("warn", "alert")
        actual_scam = call["label"] == "scam"

        results.append({
            "session_id": call["session_id"],
            "actual_scam": actual_scam,
            "predicted_scam": predicted_scam,
            "decision": final_state["decision"],
            "final_score": final_state["suspicion_score"],
        })

    print("\n" + "=" * 70)
    print("EVALUATION METRICS")
    print("=" * 70)
    print_metrics(results)
    return results


def print_metrics(results):
    tp = sum(1 for r in results if r["actual_scam"] and r["predicted_scam"])
    fp = sum(1 for r in results if not r["actual_scam"] and r["predicted_scam"])
    fn = sum(1 for r in results if r["actual_scam"] and not r["predicted_scam"])
    tn = sum(1 for r in results if not r["actual_scam"] and not r["predicted_scam"])

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    print(f"  True Positives:  {tp}   (scams correctly flagged)")
    print(f"  False Positives: {fp}   (legit calls wrongly flagged -- must stay low)")
    print(f"  False Negatives: {fn}   (scams missed)")
    print(f"  True Negatives:  {tn}   (legit calls correctly cleared)")
    print()
    print(f"  Precision: {precision:.2f}")
    print(f"  Recall:    {recall:.2f}")
    print(f"  F1 Score:  {f1:.2f}")
    print(f"  False Positive Rate: {fpr:.2f}")

    print("\n  Per-session results:")
    for r in results:
        flag = "✓" if r["actual_scam"] == r["predicted_scam"] else "✗ MISCLASSIFIED"
        print(f"    {r['session_id']}: actual={r['actual_scam']}, "
              f"predicted={r['predicted_scam']} (score={r['final_score']:.2f}) {flag}")


if __name__ == "__main__":
    run_demo()
