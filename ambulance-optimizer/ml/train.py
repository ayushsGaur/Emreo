"""
Severity Model Training Pipeline

End-to-end training script:
  1. Load and validate raw incident data
  2. Feature engineering via features.py (same code used in production)
  3. Stratified train/val/test split (preserving class ratios)
  4. Baseline model for comparison (majority class)
  5. XGBoost training with hyperparameter grid search
  6. Stratified k-fold cross-validation
  7. Full evaluation: accuracy, per-class precision/recall/F1, confusion matrix
  8. MLflow experiment tracking — every run is logged
  9. Save best model as .pkl for backend to load

Usage:
    # Generate data first if needed:
    python ml/data_generator.py --samples 5000

    # Train:
    python ml/train.py

    # Train with custom data:
    python ml/train.py --data ml/data/raw/my_data.csv --experiment my-experiment

MLflow UI:
    mlflow ui --port 5001
    open http://localhost:5001
"""

import argparse
import json
import sys
import warnings
from pathlib import Path
from datetime import datetime, timezone

import joblib
import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from xgboost import XGBClassifier

# Add project root to path so ml/ modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.features import (
    FEATURE_NAMES,
    SEVERITY_TO_INT,
    INT_TO_SEVERITY,
    extract_features_from_df,
    encode_labels,
    decode_labels,
)

warnings.filterwarnings("ignore", category=UserWarning)

# ── Constants ─────────────────────────────────────────────────────────────────

PRIORITY_LABELS = ["P1", "P2", "P3", "P4"]
MODEL_OUTPUT_DIR = Path("ml/models")
REPORT_OUTPUT_DIR = Path("ml/reports")
MLFLOW_EXPERIMENT = "severity-prediction"

# XGBoost hyperparameter search space
PARAM_GRID = [
    {
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "gamma": 0.1,
    },
    {
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.08,
        "subsample": 0.85,
        "colsample_bytree": 0.75,
        "min_child_weight": 5,
        "gamma": 0.2,
    },
    {
        "n_estimators": 150,
        "max_depth": 7,
        "learning_rate": 0.15,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 2,
        "gamma": 0.0,
    },
]


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_and_validate(data_path: Path) -> pd.DataFrame:
    """Load CSV, validate required columns exist, report basic stats."""
    print(f"\n{'='*60}")
    print(f"  Loading data from {data_path}")
    print(f"{'='*60}")

    if not data_path.exists():
        print(f"\nData file not found: {data_path}")
        print("Generating synthetic data first...")
        from ml.data_generator import generate_dataset
        MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df = generate_dataset(5000)
        df.to_csv(data_path, index=False)
        print(f"Generated and saved to {data_path}")
    else:
        df = pd.read_csv(data_path)

    required = {"complaint", "patient_age", "patient_conscious",
                "patient_breathing", "severity"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Validate severity values
    invalid = set(df["severity"].unique()) - set(SEVERITY_TO_INT.keys())
    if invalid:
        raise ValueError(f"Invalid severity values found: {invalid}")

    print(f"\nDataset loaded: {len(df):,} records, {df.shape[1]} columns")
    print(f"\nClass distribution:")
    dist = df["severity"].value_counts().sort_index()
    for sev, count in dist.items():
        bar = "█" * int(count / len(df) * 40)
        print(f"  {sev}  {bar}  {count:>5} ({count/len(df)*100:.1f}%)")

    print(f"\nMissing values:")
    nulls = df[list(required)].isnull().sum()
    for col, n in nulls.items():
        status = "✓" if n == 0 else f"⚠  {n} missing"
        print(f"  {col:<22} {status}")

    return df


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_model(
    model,
    X: np.ndarray,
    y_true: np.ndarray,
    split_name: str,
    log_to_mlflow: bool = True,
) -> dict:
    """Compute and log a full set of evaluation metrics."""
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X) if hasattr(model, "predict_proba") else None

    acc      = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    macro_p  = precision_score(y_true, y_pred, average="macro", zero_division=0)
    macro_r  = recall_score(y_true, y_pred, average="macro", zero_division=0)

    # Per-class metrics (critical: P1 recall must be high)
    report = classification_report(
        y_true, y_pred,
        target_names=PRIORITY_LABELS,
        output_dict=True,
        zero_division=0,
    )

    cm = confusion_matrix(y_true, y_pred)

    metrics = {
        f"{split_name}_accuracy":      round(acc, 4),
        f"{split_name}_macro_f1":      round(macro_f1, 4),
        f"{split_name}_macro_precision": round(macro_p, 4),
        f"{split_name}_macro_recall":   round(macro_r, 4),
    }

    # Per-class breakdown
    for label in PRIORITY_LABELS:
        if label in report:
            metrics[f"{split_name}_{label}_precision"] = round(report[label]["precision"], 4)
            metrics[f"{split_name}_{label}_recall"]    = round(report[label]["recall"],    4)
            metrics[f"{split_name}_{label}_f1"]        = round(report[label]["f1-score"],  4)

    if log_to_mlflow:
        mlflow.log_metrics(metrics)

    return {
        "metrics": metrics,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }


def print_evaluation(results: dict, split_name: str) -> None:
    """Pretty-print evaluation results to console."""
    m = results["metrics"]
    print(f"\n  {split_name.upper()} RESULTS")
    print(f"  {'─'*40}")
    print(f"  Accuracy      {m[f'{split_name}_accuracy']:.4f}")
    print(f"  Macro F1      {m[f'{split_name}_macro_f1']:.4f}")
    print(f"  Macro Prec    {m[f'{split_name}_macro_precision']:.4f}")
    print(f"  Macro Recall  {m[f'{split_name}_macro_recall']:.4f}")
    print(f"\n  Per-class breakdown:")
    print(f"  {'Label':<6} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"  {'─'*40}")
    for label in PRIORITY_LABELS:
        p = m.get(f"{split_name}_{label}_precision", 0)
        r = m.get(f"{split_name}_{label}_recall", 0)
        f = m.get(f"{split_name}_{label}_f1", 0)
        # Flag if P1 recall is dangerously low
        flag = " ⚠  LOW P1 RECALL" if label == "P1" and r < 0.85 else ""
        print(f"  {label:<6} {p:>10.4f} {r:>10.4f} {f:>10.4f}{flag}")

    print(f"\n  Confusion matrix (rows=actual, cols=predicted):")
    cm = results["confusion_matrix"]
    print(f"  {'':>6}" + "".join(f"{l:>8}" for l in PRIORITY_LABELS))
    for i, row in enumerate(cm):
        print(f"  {PRIORITY_LABELS[i]:>6}" + "".join(f"{v:>8}" for v in row))


# ── Cross-Validation ──────────────────────────────────────────────────────────

def cross_validate(
    params: dict,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
) -> dict[str, float]:
    """
    Stratified k-fold CV to get unbiased performance estimates.
    Returns mean ± std for key metrics across folds.
    """
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    fold_metrics: dict[str, list] = {
        "accuracy": [], "macro_f1": [], "p1_recall": []
    }

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        model = XGBClassifier(
            **params,
            objective="multi:softprob",
            num_class=4,
            eval_metric="mlogloss",
            use_label_encoder=False,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_tr, y_tr, verbose=False)
        y_pred = model.predict(X_val)

        fold_metrics["accuracy"].append(accuracy_score(y_val, y_pred))
        fold_metrics["macro_f1"].append(f1_score(y_val, y_pred, average="macro", zero_division=0))

        # P1 recall per fold (most safety-critical metric)
        p1_mask = (y_val == 0)
        if p1_mask.sum() > 0:
            p1_recall = recall_score(
                y_val[p1_mask],
                y_pred[p1_mask],
                labels=[0], average="micro", zero_division=0
            )
            fold_metrics["p1_recall"].append(p1_recall)

        print(f"    Fold {fold+1}/{n_splits}: acc={fold_metrics['accuracy'][-1]:.4f}  "
              f"macro_f1={fold_metrics['macro_f1'][-1]:.4f}")

    return {
        "cv_accuracy_mean":  round(float(np.mean(fold_metrics["accuracy"])), 4),
        "cv_accuracy_std":   round(float(np.std(fold_metrics["accuracy"])),  4),
        "cv_macro_f1_mean":  round(float(np.mean(fold_metrics["macro_f1"])), 4),
        "cv_macro_f1_std":   round(float(np.std(fold_metrics["macro_f1"])),  4),
        "cv_p1_recall_mean": round(float(np.mean(fold_metrics["p1_recall"])), 4) if fold_metrics["p1_recall"] else 0.0,
    }


# ── Main Training Pipeline ────────────────────────────────────────────────────

def train(data_path: Path, experiment_name: str, model_version: str) -> None:

    # ── 1. Load data ──────────────────────────────────────────────
    df = load_and_validate(data_path)

    # ── 2. Feature engineering ────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Feature Engineering")
    print(f"{'='*60}")
    X = extract_features_from_df(df)
    y = encode_labels(df["severity"])
    print(f"  Feature matrix: {X.shape[0]:,} samples × {X.shape[1]} features")
    print(f"  Features: {', '.join(FEATURE_NAMES)}")

    # ── 3. Train / Val / Test split (stratified) ──────────────────
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=42
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.15, stratify=y_trainval, random_state=42
    )
    print(f"\n  Split sizes:")
    print(f"    Train  {len(X_train):>6,} ({len(X_train)/len(X)*100:.1f}%)")
    print(f"    Val    {len(X_val):>6,} ({len(X_val)/len(X)*100:.1f}%)")
    print(f"    Test   {len(X_test):>6,} ({len(X_test)/len(X)*100:.1f}%)")

    # ── 4. Baseline ───────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Baseline: Majority Class Classifier")
    print(f"{'='*60}")
    baseline = DummyClassifier(strategy="most_frequent", random_state=42)
    baseline.fit(X_train, y_train)
    baseline_acc = accuracy_score(y_test, baseline.predict(X_test))
    print(f"  Baseline test accuracy: {baseline_acc:.4f}")
    print(f"  (Our model must beat this — otherwise, something is wrong)")

    # ── 5. MLflow setup ───────────────────────────────────────────
    mlflow.set_experiment(experiment_name)

    best_run_id = None
    best_val_f1 = -1.0
    best_params = None
    best_cv_metrics = None

    print(f"\n{'='*60}")
    print(f"  Hyperparameter Search ({len(PARAM_GRID)} configurations)")
    print(f"{'='*60}")

    for i, params in enumerate(PARAM_GRID):
        config_label = f"config-{i+1}"
        print(f"\n  [{config_label}] params: {json.dumps(params)}")

        with mlflow.start_run(run_name=config_label) as run:

            # Log parameters
            mlflow.log_params(params)
            mlflow.log_param("n_features", X.shape[1])
            mlflow.log_param("n_training_samples", len(X_train))
            mlflow.log_param("feature_names", ",".join(FEATURE_NAMES))

            # ── 6. Train ──────────────────────────────────────────
            model = XGBClassifier(
                **params,
                objective="multi:softprob",
                num_class=4,
                eval_metric="mlogloss",
                use_label_encoder=False,
                early_stopping_rounds=20,
                random_state=42,
                n_jobs=-1,
            )
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
            print(f"    Best iteration: {model.best_iteration}")

            # ── 7. Cross-validation on train+val ──────────────────
            print(f"    Running {5}-fold cross-validation...")
            cv_metrics = cross_validate(params, X_trainval, y_trainval)
            mlflow.log_metrics(cv_metrics)
            print(f"    CV macro F1: {cv_metrics['cv_macro_f1_mean']:.4f} "
                  f"± {cv_metrics['cv_macro_f1_std']:.4f}")
            print(f"    CV P1 recall: {cv_metrics['cv_p1_recall_mean']:.4f}  "
                  f"{'✓ OK' if cv_metrics['cv_p1_recall_mean'] >= 0.85 else '⚠  BELOW THRESHOLD'}")

            # ── 8. Evaluate on val set ────────────────────────────
            val_results = evaluate_model(model, X_val, y_val, "val")
            print_evaluation(val_results, "val")

            val_f1 = val_results["metrics"]["val_macro_f1"]

            # ── Track best ────────────────────────────────────────
            if val_f1 > best_val_f1:
                best_val_f1  = val_f1
                best_run_id  = run.info.run_id
                best_params  = params
                best_cv_metrics = cv_metrics
                print(f"    ★ New best! val_macro_f1={val_f1:.4f}")

            mlflow.log_metric("baseline_accuracy", baseline_acc)

    # ── 9. Final evaluation on held-out test set ──────────────────
    print(f"\n{'='*60}")
    print(f"  Final Evaluation — Best Config on Test Set")
    print(f"{'='*60}")
    print(f"  Best val macro F1: {best_val_f1:.4f}")
    print(f"  Best params: {json.dumps(best_params)}")

    with mlflow.start_run(run_name=f"BEST-{model_version}") as final_run:
        # Retrain best config on full train+val for maximum data utilisation
        final_model = XGBClassifier(
            **best_params,
            objective="multi:softprob",
            num_class=4,
            eval_metric="mlogloss",
            use_label_encoder=False,
            random_state=42,
            n_jobs=-1,
        )
        final_model.fit(X_trainval, y_trainval, verbose=False)

        # Evaluate on test set (never seen during training or selection)
        test_results = evaluate_model(final_model, X_test, y_test, "test")
        print_evaluation(test_results, "test")

        # Log everything
        mlflow.log_params(best_params)
        mlflow.log_params({
            "model_version": model_version,
            "n_total_samples": len(X),
            "n_features": X.shape[1],
            "baseline_accuracy": round(baseline_acc, 4),
        })
        if best_cv_metrics:
            mlflow.log_metrics(best_cv_metrics)
        mlflow.log_metric("baseline_accuracy", baseline_acc)

        # Feature importance
        importance = final_model.feature_importances_
        importance_dict = {
            FEATURE_NAMES[i]: round(float(importance[i]), 6)
            for i in range(len(FEATURE_NAMES))
        }
        top_features = sorted(importance_dict.items(), key=lambda x: -x[1])

        print(f"\n  Feature importance (top 10):")
        for feat, score in top_features[:10]:
            bar = "█" * int(score * 200)
            print(f"    {feat:<30} {bar} {score:.4f}")

        mlflow.log_dict(importance_dict, "feature_importance.json")
        mlflow.xgboost.log_model(final_model, "model")

        # ── 10. Save model artifact ───────────────────────────────
        MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        model_path = MODEL_OUTPUT_DIR / f"severity_{model_version}.pkl"
        joblib.dump(final_model, model_path)
        print(f"\n  Model saved: {model_path}")
        mlflow.log_artifact(str(model_path))

        # Save training report
        REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "model_version": model_version,
            "data_path": str(data_path),
            "n_samples": int(len(X)),
            "n_features": int(X.shape[1]),
            "feature_names": FEATURE_NAMES,
            "best_params": best_params,
            "cv_metrics": best_cv_metrics,
            "test_metrics": test_results["metrics"],
            "confusion_matrix": test_results["confusion_matrix"],
            "feature_importance": importance_dict,
            "baseline_accuracy": round(baseline_acc, 4),
            "mlflow_run_id": final_run.info.run_id,
        }
        report_path = REPORT_OUTPUT_DIR / f"training_report_{model_version}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        mlflow.log_artifact(str(report_path))
        print(f"  Report saved: {report_path}")

        # ── 11. Safety check ──────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"  Safety Checks")
        print(f"{'='*60}")
        p1_recall = test_results["metrics"].get("test_P1_recall", 0)
        p1_ok = p1_recall >= 0.85
        beats_baseline = test_results["metrics"]["test_accuracy"] > baseline_acc

        print(f"  P1 (Critical) recall ≥ 0.85:  {'✓  PASS' if p1_ok else '✗  FAIL'} ({p1_recall:.4f})")
        print(f"  Beats baseline accuracy:        {'✓  PASS' if beats_baseline else '✗  FAIL'}")

        if not p1_ok:
            print(f"\n  ⚠  WARNING: P1 recall is below safety threshold.")
            print(f"     The model may miss critical life-threatening incidents.")
            print(f"     Consider: more P1 training data, lower classification threshold,")
            print(f"     or adjusting class weights before deploying.")
        else:
            print(f"\n  ✓  Model passes all safety checks. Ready for deployment.")
            print(f"     Copy {model_path} to backend/ml/models/ and restart the server.")

        print(f"\n  MLflow run ID: {final_run.info.run_id}")
        print(f"  View results:  mlflow ui --port 5001")
        print(f"{'='*60}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the severity prediction model")
    parser.add_argument(
        "--data", type=Path,
        default=Path("ml/data/raw/incidents.csv"),
        help="Path to training CSV",
    )
    parser.add_argument(
        "--experiment", type=str,
        default=MLFLOW_EXPERIMENT,
        help="MLflow experiment name",
    )
    parser.add_argument(
        "--version", type=str,
        default="v1",
        help="Model version tag (e.g. v1, v2)",
    )
    args = parser.parse_args()

    train(
        data_path=args.data,
        experiment_name=args.experiment,
        model_version=args.version,
    )
