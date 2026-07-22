"""
evaluate.py
===========
Rigorous evaluation of the digital arrest scam detector.

Over main.py it adds the things a technical judge looks for:
  * confusion matrix (raw TP/FP/FN/TN, not just percentages)
  * precision, recall, F1, false-positive rate, specificity
  * 95% bootstrap confidence intervals on every metric (honest small-n reporting)
  * a per-category breakdown (which scam types are missed, which legit call
    types trigger false alarms)
  * a full list of every misclassified call, so errors can be inspected

Run it AFTER building the eval set:
    python data/generate_eval_set.py
    python evaluate.py
    python evaluate.py --data data/eval_transcripts.json --bootstrap 2000

The numbers this prints are the ONLY numbers that belong in your report. Do not
quote figures from a stubbed or partial run.
"""

import argparse
import contextlib
import io
import json
import os
import random

from agents.graph import process_call_session


def classify(call):
    """Run one call through the full pipeline; return (predicted_scam, score, decision)."""
    # process_call_session prints a running line per chunk (useful for a live
    # demo, noise for a batch eval). Swallow it so the results block is clean.
    with contextlib.redirect_stdout(io.StringIO()):
        final = process_call_session(
            session_id=call["session_id"],
            chunks=call["chunks"],
            city=call.get("city"),
            latitude=call.get("latitude"),
            longitude=call.get("longitude"),
            language="en",
        )
    decision = final.get("decision", "monitor")
    predicted_scam = decision in ("warn", "alert")
    return predicted_scam, final.get("suspicion_score", 0.0), decision


def confusion(records):
    tp = sum(1 for r in records if r["actual"] and r["pred"])
    fp = sum(1 for r in records if not r["actual"] and r["pred"])
    fn = sum(1 for r in records if r["actual"] and not r["pred"])
    tn = sum(1 for r in records if not r["actual"] and not r["pred"])
    return tp, fp, fn, tn


def metrics(tp, fp, fn, tn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {
        "precision": precision, "recall": recall, "f1": f1,
        "fpr": fpr, "specificity": specificity,
    }


def bootstrap_ci(records, n_boot, seed=0):
    """
    Resample calls with replacement n_boot times; return 2.5/97.5 percentile
    bounds for each metric. This is how you report a metric honestly on a
    modest-sized test set -- it shows how much the number could move if the
    sample had been slightly different.
    """
    rng = random.Random(seed)
    keys = ["precision", "recall", "f1", "fpr", "specificity"]
    dists = {k: [] for k in keys}
    n = len(records)

    for _ in range(n_boot):
        sample = [records[rng.randrange(n)] for _ in range(n)]
        m = metrics(*confusion(sample))
        for k in keys:
            dists[k].append(m[k])

    ci = {}
    for k in keys:
        vals = sorted(dists[k])
        lo = vals[int(0.025 * n_boot)]
        hi = vals[int(0.975 * n_boot) - 1]
        ci[k] = (lo, hi)
    return ci


def per_category(records):
    """Break results down by scam_type / negative_type."""
    cats = {}
    for r in records:
        cat = r["category"]
        d = cats.setdefault(cat, {"total": 0, "correct": 0, "label": r["label"]})
        d["total"] += 1
        d["correct"] += 1 if (r["actual"] == r["pred"]) else 0
    return cats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data",
        default=os.path.join(os.path.dirname(__file__), "data", "eval_transcripts.json"),
    )
    ap.add_argument("--bootstrap", type=int, default=2000,
                    help="bootstrap resamples for confidence intervals")
    args = ap.parse_args()

    with open(args.data, encoding="utf-8") as f:
        calls = json.load(f)

    print("=" * 68)
    print(f"EVALUATION  |  {len(calls)} calls from {os.path.basename(args.data)}")
    print("=" * 68)

    records = []
    for call in calls:
        pred, score, decision = classify(call)
        actual = call["label"] == "scam"
        records.append({
            "session_id": call["session_id"],
            "label": call["label"],
            "actual": actual, "pred": pred,
            "score": score, "decision": decision,
            "category": call.get("scam_type") or call.get("negative_type") or "unknown",
            "difficulty": call.get("difficulty", ""),
        })

    tp, fp, fn, tn = confusion(records)
    m = metrics(tp, fp, fn, tn)
    ci = bootstrap_ci(records, args.bootstrap)

    print("\nConfusion matrix")
    print(f"  True Positives  (scam caught)      : {tp}")
    print(f"  False Positives (legit flagged)    : {fp}   <- the FPR numerator, keep low")
    print(f"  False Negatives (scam missed)      : {fn}")
    print(f"  True Negatives  (legit cleared)    : {tn}")

    print("\nMetrics (with 95% bootstrap CI)")
    def line(name, key):
        lo, hi = ci[key]
        print(f"  {name:12s}: {m[key]:.3f}   [{lo:.3f}, {hi:.3f}]")
    line("Precision", "precision")
    line("Recall", "recall")
    line("F1", "f1")
    line("FPR", "fpr")
    line("Specificity", "specificity")

    print("\nPer-category accuracy")
    cats = per_category(records)
    for cat in sorted(cats, key=lambda c: (cats[c]["label"], c)):
        d = cats[cat]
        print(f"  [{d['label']:5s}] {cat:22s}: {d['correct']}/{d['total']}")

    mis = [r for r in records if r["actual"] != r["pred"]]
    print(f"\nMisclassifications ({len(mis)})")
    if not mis:
        print("  none")
    for r in mis:
        kind = "FALSE NEGATIVE (missed scam)" if r["actual"] else "FALSE POSITIVE (flagged legit)"
        print(f"  {r['session_id']} [{r['category']}] {kind} "
              f"score={r['score']:.2f} decision={r['decision']}")

    print("\n" + "=" * 68)
    print("Paste this whole block into the evaluation doc. These are real numbers.")
    print("=" * 68)


if __name__ == "__main__":
    main()
