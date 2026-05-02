"""
Model Evaluation Script

Load a saved model and evaluate it against any dataset.
Used for:
  - Post-deployment validation against real incident data
  - Comparing two model versions
  - Detecting data drift (evaluate new data, compare to training metrics)
  - Generating reports for model monitoring dashboard

Usage:
    # Evaluate saved model on test data
    python ml/evaluate.py --model ml/models/severity_v1.pkl --data ml/data/raw/incidents.csv

    # Compare two model versions
    python ml/evaluate.py --model ml/models/severity_v2.pkl --data ml/data/raw/incidents.csv --compare ml/models/severity_v1.pkl
"""

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.features import (
    PRIORITY_LABELS,
    SEVERITY_TO_INT,
    INT_TO_SEVERITY,
    FEATURE_NAMES,
    extract_features_from_df,
    encode_labels,
)


def evaluate(model_path: Path, data_path: Path, label: str = "Model") -> dict:
    print(f"\n{'='*60}")
    print(f"  Evaluating: {label}")
    print(f"  Model: {model_path}")
    print(f"  Data:  {data_path}")
    print(f"{'='*60}")

    model = joblib.load(model_path)
    df = pd.read_csv(data_path)

    X = extract_features_from_df(df)
    y_true = encode_labels(df["severity"])
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)

    acc      = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    cm       = confusion_matrix(y_true, y_pred)
    report   = classification_report(
        y_true, y_pred, target_names=PRIORITY_LABELS,
        output_dict=True, zero_division=0,
    )

    # Per-class confidence (mean predicted probability of correct class)
    correct_proba = [
        float(y_proba[i][y_true[i]]) for i in range(len(y_true))
    ]
    mean_confidence = round(float(np.mean(correct_proba)), 4)

    # Flag rate: predictions below 0.6 confidence threshold
    flag_rate = round(float(np.mean([p < 0.6 for p in correct_proba])), 4)

    print(f"\n  Overall metrics")
    print(f"  {'─'*40}")
    print(f"  Accuracy         {acc:.4f}")
    print(f"  Macro F1         {macro_f1:.4f}")
    print(f"  Mean confidence  {mean_confidence:.4f}")
    print(f"  Flag rate        {flag_rate:.4f}  (predictions below 0.60 threshold)")

    print(f"\n  Per-class breakdown")
    print(f"  {'Label':<6} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print(f"  {'─'*50}")
    for label_name in PRIORITY_LABELS:
        r = report[label_name]
        flag = ""
        if label_name == "P1" and r["recall"] < 0.85:
            flag = "  ⚠  CRITICAL: P1 recall below 0.85"
        print(f"  {label_name:<6} {r['precision']:>10.4f} {r['recall']:>10.4f} "
              f"{r['f1-score']:>10.4f} {int(r['support']):>10}{flag}")

    print(f"\n  Confusion matrix (rows=actual, cols=predicted)")
    print(f"  {'':>6}" + "".join(f"{l:>8}" for l in PRIORITY_LABELS))
    for i, row in enumerate(cm):
        print(f"  {PRIORITY_LABELS[i]:>6}" + "".join(f"{v:>8}" for v in row))

    # Feature importance if available
    if hasattr(model, "feature_importances_"):
        importance = dict(zip(FEATURE_NAMES, model.feature_importances_))
        top = sorted(importance.items(), key=lambda x: -x[1])[:8]
        print(f"\n  Top 8 features by importance")
        for feat, score in top:
            bar = "█" * int(score * 200)
            print(f"    {feat:<30} {bar} {score:.4f}")

    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "mean_confidence": mean_confidence,
        "flag_rate": flag_rate,
        "per_class": {
            label_name: {
                "precision": round(report[label_name]["precision"], 4),
                "recall":    round(report[label_name]["recall"],    4),
                "f1":        round(report[label_name]["f1-score"],  4),
            }
            for label_name in PRIORITY_LABELS
        },
        "confusion_matrix": cm.tolist(),
        "p1_recall_ok": report["P1"]["recall"] >= 0.85,
    }


def compare_models(
    model_a_path: Path,
    model_b_path: Path,
    data_path: Path,
) -> None:
    """Side-by-side comparison of two model versions."""
    results_a = evaluate(model_a_path, data_path, label=f"Model A — {model_a_path.name}")
    results_b = evaluate(model_b_path, data_path, label=f"Model B — {model_b_path.name}")

    print(f"\n{'='*60}")
    print(f"  Comparison: {model_a_path.name} vs {model_b_path.name}")
    print(f"{'='*60}")

    metrics = ["accuracy", "macro_f1", "mean_confidence", "flag_rate"]
    for m in metrics:
        va, vb = results_a[m], results_b[m]
        # For flag_rate, lower is better
        better = "A" if (va < vb if m == "flag_rate" else va > vb) else "B"
        diff = round(abs(va - vb), 4)
        arrow = "→" if diff == 0 else ("▲" if better == "B" else "▼")
        print(f"  {m:<22} A={va:.4f}  B={vb:.4f}  {arrow}  Δ{diff:.4f}  (better: {better})")

    print(f"\n  Recommendation:")
    if results_b["macro_f1"] > results_a["macro_f1"] and results_b["p1_recall_ok"]:
        print(f"  ✓  Deploy Model B ({model_b_path.name}) — better F1 and P1 recall is safe")
    elif not results_b["p1_recall_ok"]:
        print(f"  ✗  Keep Model A — Model B has insufficient P1 recall (safety risk)")
    else:
        print(f"  =  Models are comparable — keep current deployment (Model A)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",   type=Path, required=True)
    parser.add_argument("--data",    type=Path, default=Path("ml/data/raw/incidents.csv"))
    parser.add_argument("--compare", type=Path, default=None,
                        help="Second model to compare against --model")
    parser.add_argument("--output",  type=Path, default=None,
                        help="Save evaluation JSON to this path")
    args = parser.parse_args()

    if args.compare:
        compare_models(args.model, args.compare, args.data)
    else:
        results = evaluate(args.model, args.data)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\n  Saved to {args.output}")
