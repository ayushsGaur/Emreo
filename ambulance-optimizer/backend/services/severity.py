"""
Severity Prediction Service

Loads the trained XGBoost model at startup and exposes a predict() method.
The model is never loaded per-request — it stays in memory.

Input:  structured incident features
Output: SeverityPriority enum + confidence score + flagged_for_review bool
"""

import joblib
import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from backend.models.incident import SeverityPriority, IncidentCreate
from backend.core.config import settings
from backend.core.exceptions import SeverityModelError
from backend.core.logging import get_logger
from ml.features import extract_features_from_row

logger = get_logger(__name__)


@dataclass
class SeverityResult:
    priority: SeverityPriority
    confidence: float
    flagged_for_review: bool
    raw_probabilities: dict[str, float]


# Priority order for mapping model output indices → enum values
PRIORITY_CLASSES = [
    SeverityPriority.P1_CRITICAL,
    SeverityPriority.P2_EMERGENT,
    SeverityPriority.P3_URGENT,
    SeverityPriority.P4_NON_URGENT,
]

# High-risk complaint keywords that always elevate to at least P2
HIGH_RISK_KEYWORDS = {
    "cardiac", "heart attack", "chest pain", "not breathing", "unconscious",
    "unresponsive", "seizure", "stroke", "choking", "drowning", "overdose",
    "severe bleeding", "gunshot", "stabbing", "major trauma",
}


class SeverityService:
    """
    Manages the ML model lifecycle and exposes prediction logic.
    Instantiated once at application startup via lifespan.
    """

    def __init__(self):
        self._model = None
        self._model_version: Optional[str] = None
        self._loaded: bool = False

    def load_model(self, model_path: Optional[Path] = None) -> None:
        """Load the model from disk. Called once at startup."""
        path = model_path or settings.MODEL_PATH

        if not path.exists():
            # logger.warning(
            #     "Severity model file not found — using rule-based fallback",
            #     model_path=str(path),
            # )
            logger.warning(
            f"Severity model file not found — using rule-based fallback | path={str(path)}"
            )
            self._loaded = False
            return

        try:
            self._model = joblib.load(path)
            self._model_version = settings.MODEL_VERSION
            self._loaded = True
            # logger.info(
            #     "Severity model loaded successfully",
            #     model_path=str(path),
            #     version=self._model_version,
            # )

            logger.info(
            f"Severity model loaded successfully | model_path={str(path)} | version={self._model_version}"
            )

        except Exception as e:
            logger.error(f"Failed to load severity model | error={str(e)}")
            self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_version(self) -> str:
        return self._model_version or "rule-based-fallback"

    def predict(self, incident: IncidentCreate) -> SeverityResult:
        """
        Predict severity priority for an incident.

        Falls back to rule-based logic if model is not loaded.
        This ensures the system keeps running even without a trained model.
        """
        if self._loaded and self._model is not None:
            return self._predict_with_model(incident)
        else:
            return self._predict_rule_based(incident)

    # def _extract_features(self, incident: IncidentCreate) -> np.ndarray:
    #     """
    #     Convert an IncidentCreate into a feature vector for the model.

    #     Features (in order — must match training):
    #       0: patient_age (0 if unknown)
    #       1: patient_conscious (1/0/-1 for true/false/unknown)
    #       2: patient_breathing (1/0/-1)
    #       3: complaint_has_high_risk_keyword (0/1)
    #       4: complaint_length (proxy for detail given)
    #     """
    #     complaint_lower = incident.complaint.lower()
    #     has_high_risk = int(
    #         any(kw in complaint_lower for kw in HIGH_RISK_KEYWORDS)
    #     )

    #     features = np.array([[
    #         incident.patient_age or 0,
    #         1 if incident.patient_conscious is True else (0 if incident.patient_conscious is False else -1),
    #         1 if incident.patient_breathing is True else (0 if incident.patient_breathing is False else -1),
    #         has_high_risk,
    #         min(len(incident.complaint), 500),
    #     ]], dtype=np.float32)

    #     return features

    def _predict_with_model(self, incident: IncidentCreate) -> SeverityResult:
        try:
            # features = self._extract_features(incident)
            features = extract_features_from_row(
             complaint=incident.complaint,
             patient_age=incident.patient_age,
             patient_conscious=incident.patient_conscious,
             patient_breathing=incident.patient_breathing,
             hour_of_day=None
            ).reshape(1, -1)
            probabilities = self._model.predict_proba(features)[0]
            predicted_idx = int(np.argmax(probabilities))
            confidence = float(probabilities[predicted_idx])
            priority = PRIORITY_CLASSES[predicted_idx]

            raw_probs = {
                cls.value: round(float(p), 4)
                for cls, p in zip(PRIORITY_CLASSES, probabilities)
            }

            flagged = confidence < settings.SEVERITY_CONFIDENCE_THRESHOLD

            # logger.info(
            #     "Severity predicted via ML model",
            #     priority=priority.value,
            #     confidence=round(confidence, 4),
            #     flagged=flagged,
            # )

            logger.info(
            f"Severity predicted via ML model | priority={priority.value} | confidence={round(confidence, 4)} | flagged={flagged}"
            )

            return SeverityResult(
                priority=priority,
                confidence=round(confidence, 4),
                flagged_for_review=flagged,
                raw_probabilities=raw_probs,
            )

        except Exception as e:
            logger.error(f"ML model prediction failed, error={str(e)}")
            raise SeverityModelError(detail=str(e))

    def _predict_rule_based(self, incident: IncidentCreate) -> SeverityResult:
        """
        Deterministic rule-based triage when the model isn't available.
        Used during development before the model is trained,
        and as a failsafe in production.
        """
        complaint_lower = incident.complaint.lower()
        has_high_risk = any(kw in complaint_lower for kw in HIGH_RISK_KEYWORDS)

        # Immediate life threat
        if not incident.patient_conscious or not incident.patient_breathing or (
            has_high_risk and (
                incident.patient_conscious is False
                or incident.patient_breathing is False
            )
        ):
            priority = SeverityPriority.P1_CRITICAL
            confidence = 0.90

        # Serious but stable
        elif has_high_risk:
            priority = SeverityPriority.P2_EMERGENT
            confidence = 0.75

        # Urgent
        elif incident.patient_age and (incident.patient_age > 70 or incident.patient_age < 5):
            priority = SeverityPriority.P3_URGENT
            confidence = 0.65

        # Non-urgent
        else:
            priority = SeverityPriority.P4_NON_URGENT
            confidence = 0.70

        # logger.info(
        #     "Severity predicted via rule-based fallback",
        #     priority=priority.value,
        #     confidence=confidence,
        # )

        logger.info(
        f"Severity predicted via rule-based fallback | priority={priority.value} | confidence={confidence}"
        )

        return SeverityResult(
            priority=priority,
            confidence=confidence,
            flagged_for_review=False,
            raw_probabilities={priority.value: confidence},
        )


# Singleton instance — imported by the lifespan and injected where needed
severity_service = SeverityService()
