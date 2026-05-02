"""
Feature Engineering Pipeline

This file is the single source of truth for how raw incident data
becomes model-ready feature vectors.

Critical design rule:
  The EXACT same transformations must run during training AND inference.
  If they diverge, predictions will be wrong in production (training-serving skew).

  Solution: this module is imported by BOTH train.py AND backend/services/severity.py.
  One definition, two consumers — skew is impossible.

Features produced:
  Numerical (6):
    patient_age_norm        — age normalized 0-1 (clipped at 100)
    patient_conscious       — 1/0/-1 (true/false/unknown)
    patient_breathing       — 1/0/-1 (true/false/unknown)
    complaint_length_norm   — character count / 500
    hour_of_day_sin         — cyclic encoding of hour (sin component)
    hour_of_day_cos         — cyclic encoding of hour (cos component)

  Binary keyword flags (16):
    has_kw_cardiac, has_kw_breathing, has_kw_unconscious, has_kw_trauma,
    has_kw_chest_pain, has_kw_seizure, has_kw_stroke, has_kw_bleeding,
    has_kw_allergy, has_kw_overdose, has_kw_elderly_risk,
    has_kw_fracture, has_kw_burn, has_kw_diabetic,
    has_kw_fever, has_kw_choking

Total: 22 features
"""

import math
import numpy as np
import pandas as pd
from typing import Union, Optional


# ── Keyword groups ────────────────────────────────────────────────────────────
# Each group is a set of substrings. A flag = 1 if ANY substring is found.

KEYWORD_GROUPS: dict[str, list[str]] = {
    "cardiac":      ["cardiac", "heart attack", "no pulse", "arrest"],
    "breathing":    ["not breathing", "difficulty breathing", "airway", "choking",
                     "turning blue", "cannot breathe"],
    "unconscious":  ["unconscious", "unresponsive", "no response", "collapsed",
                     "not responding"],
    "trauma":       ["trauma", "accident", "gunshot", "stabbing", "explosion",
                     "crush", "hanging", "electrocution"],
    "chest_pain":   ["chest pain", "chest tightness", "chest pressure"],
    "seizure":      ["seizure", "convulsion", "fitting", "epilepsy"],
    "stroke":       ["stroke", "face drooping", "slurred speech", "arm weakness",
                     "sudden numbness"],
    "bleeding":     ["bleeding", "hemorrhage", "blood loss", "laceration", "wound"],
    "allergy":      ["allergic", "allergy", "anaphylaxis", "hives", "swelling throat"],
    "overdose":     ["overdose", "poisoning", "ingested", "drug", "toxic"],
    "elderly_risk": ["elderly", "old age", "nursing home", "falls elderly"],
    "fracture":     ["fracture", "broken", "dislocated", "sprain"],
    "burn":         ["burn", "scalded", "fire"],
    "diabetic":     ["diabetic", "diabetes", "sugar", "hypoglycemia", "insulin"],
    "fever":        ["fever", "high temperature", "febrile", "pyrexia"],
    "choking":      ["choking", "foreign body", "swallowed", "stuck in throat"],
}

FEATURE_NAMES = (
    ["patient_age_norm", "patient_conscious", "patient_breathing",
     "complaint_length_norm", "hour_of_day_sin", "hour_of_day_cos"]
    + [f"has_kw_{k}" for k in KEYWORD_GROUPS.keys()]
)

SEVERITY_TO_INT = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
INT_TO_SEVERITY = {v: k for k, v in SEVERITY_TO_INT.items()}


# ── Core transformation ───────────────────────────────────────────────────────

def extract_features_from_row(
    complaint: str,
    patient_age: Optional[Union[int, float]],
    patient_conscious: Optional[Union[int, bool]],
    patient_breathing: Optional[Union[int, bool]],
    hour_of_day: Optional[int] = None,
) -> np.ndarray:
    """
    Transform a single incident's raw fields into a feature vector.

    Parameters match what we have at dispatch time — no future information.
    Returns a 1D numpy array of length len(FEATURE_NAMES).
    """
    complaint_lower = complaint.lower().strip()

    # ── Numerical features ────────────────────────────────────────
    age_norm = float(np.clip((patient_age or 0) / 100.0, 0.0, 1.0))

    # Encode conscious/breathing as ternary: 1 = yes, 0 = no, -1 = unknown
    def encode_bool(val) -> float:
        if val is None:
            return -1.0
        if isinstance(val, bool):
            return 1.0 if val else 0.0
        return float(np.clip(val, -1.0, 1.0))

    conscious_enc = encode_bool(patient_conscious)
    breathing_enc = encode_bool(patient_breathing)
    length_norm   = min(len(complaint_lower) / 500.0, 1.0)

    # Cyclic hour encoding — 23:00 and 00:00 should be "close"
    hour = int(hour_of_day or 12)
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)

    numerical = [age_norm, conscious_enc, breathing_enc,
                 length_norm, hour_sin, hour_cos]

    # ── Keyword flags ─────────────────────────────────────────────
    flags = [
        float(any(kw in complaint_lower for kw in keywords))
        for keywords in KEYWORD_GROUPS.values()
    ]

    return np.array(numerical + flags, dtype=np.float32)


def extract_features_from_df(df: pd.DataFrame) -> np.ndarray:
    """
    Vectorised transformation for training — processes entire DataFrame at once.
    Each row in df must have: complaint, patient_age, patient_conscious,
    patient_breathing, hour_of_day.
    """
    rows = []
    for _, row in df.iterrows():
        vec = extract_features_from_row(
            complaint=str(row.get("complaint", "")),
            patient_age=row.get("patient_age"),
            patient_conscious=row.get("patient_conscious"),
            patient_breathing=row.get("patient_breathing"),
            hour_of_day=row.get("hour_of_day"),
        )
        rows.append(vec)

    X = np.vstack(rows)
    return X


def encode_labels(severity_series: pd.Series) -> np.ndarray:
    """Map severity strings (P1-P4) to integer class indices (0-3)."""
    return severity_series.map(SEVERITY_TO_INT).values


def decode_labels(int_array: np.ndarray) -> list[str]:
    """Map integer predictions back to severity strings."""
    return [INT_TO_SEVERITY[i] for i in int_array]
