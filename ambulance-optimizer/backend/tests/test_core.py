"""
Backend test suite — dispatcher logic and severity prediction.

Tests are structured to be runnable without a live database
by using mocks where needed, and with a test DB for integration tests.

Run: pytest backend/tests/ -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.models.incident import SeverityPriority, IncidentCreate, AmbulanceType
from backend.services.severity import SeverityService, SeverityResult
from backend.services.resource import ResourceAllocationService, AllocationResult
from backend.services.routing import haversine_km


# ── Severity Service Tests ────────────────────────────────────────────────────

class TestSeverityRulesBased:
    """Test the rule-based fallback — works without any trained model."""

    def setup_method(self):
        self.service = SeverityService()
        # Don't load model — test fallback only
        self.service._loaded = False

    def _make_incident(self, complaint, age=None, conscious=None, breathing=None):
        return IncidentCreate(
            caller_name="Test Caller",
            caller_phone="9876543210",
            complaint=complaint,
            latitude=30.7333,
            longitude=76.7794,
            patient_age=age,
            patient_conscious=conscious,
            patient_breathing=breathing,
        )

    def test_cardiac_arrest_is_p1(self):
        incident = self._make_incident(
            "patient not breathing, cardiac arrest suspected",
            conscious=False,
            breathing=False,
        )
        result = self.service.predict(incident)
        assert result.priority == SeverityPriority.P1_CRITICAL
        assert result.confidence > 0.8

    def test_chest_pain_is_p2(self):
        incident = self._make_incident("severe chest pain radiating to arm", age=55)
        result = self.service.predict(incident)
        assert result.priority in (SeverityPriority.P1_CRITICAL, SeverityPriority.P2_EMERGENT)

    def test_elderly_patient_is_at_least_p3(self):
        incident = self._make_incident("patient fell, possible hip fracture", age=75)
        result = self.service.predict(incident)
        assert result.priority in (
            SeverityPriority.P1_CRITICAL,
            SeverityPriority.P2_EMERGENT,
            SeverityPriority.P3_URGENT,
        )

    def test_minor_complaint_is_p4(self):
        incident = self._make_incident(
            "minor cut on finger, small amount of bleeding",
            age=25,
            conscious=True,
            breathing=True,
        )
        result = self.service.predict(incident)
        assert result.priority == SeverityPriority.P4_NON_URGENT

    def test_result_has_required_fields(self):
        incident = self._make_incident("headache", age=30)
        result = self.service.predict(incident)
        assert isinstance(result, SeverityResult)
        assert result.priority in list(SeverityPriority)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.flagged_for_review, bool)


# ── Haversine Distance Tests ──────────────────────────────────────────────────

class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_km(30.0, 76.0, 30.0, 76.0) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self):
        # Chandigarh to Delhi — approx 250km
        result = haversine_km(30.7333, 76.7794, 28.6139, 77.2090)
        assert 240 < result < 270

    def test_symmetry(self):
        a = haversine_km(30.0, 76.0, 28.0, 77.0)
        b = haversine_km(28.0, 77.0, 30.0, 76.0)
        assert a == pytest.approx(b, rel=1e-6)


# ── Resource Allocation Tests ─────────────────────────────────────────────────

class TestResourceAllocation:
    def setup_method(self):
        self.service = ResourceAllocationService()

    def _make_ambulance(self, lat, lng, amb_type="ALS", status="available"):
        amb = MagicMock()
        amb.id = "test-amb-id"
        amb.unit_number = "AMB-01"
        amb.latitude = lat
        amb.longitude = lng
        amb.ambulance_type = amb_type
        amb.status = status
        amb.last_location_update = None
        return amb

    def test_closer_ambulance_scores_higher(self):
        incident_lat, incident_lng = 30.7333, 76.7794

        close_amb  = self._make_ambulance(30.74, 76.78)
        far_amb    = self._make_ambulance(30.80, 76.85)

        close_score = self.service._score_ambulance(
            close_amb, incident_lat, incident_lng, AmbulanceType.ALS
        )
        far_score = self.service._score_ambulance(
            far_amb, incident_lat, incident_lng, AmbulanceType.ALS
        )

        assert close_score is not None
        assert far_score is not None
        assert close_score > far_score

    def test_als_scores_higher_for_p1(self):
        incident_lat, incident_lng = 30.7333, 76.7794

        als_amb = self._make_ambulance(30.74, 76.78, "ALS")
        bls_amb = self._make_ambulance(30.74, 76.78, "BLS")  # same location

        als_score = self.service._score_ambulance(
            als_amb, incident_lat, incident_lng, AmbulanceType.ALS
        )
        bls_score = self.service._score_ambulance(
            bls_amb, incident_lat, incident_lng, AmbulanceType.ALS
        )

        assert als_score > bls_score

    def test_out_of_range_returns_none(self):
        # Ambulance 1000km away
        score = self.service._score_ambulance(
            self._make_ambulance(40.0, 90.0),
            30.7333, 76.7794,
            AmbulanceType.ALS,
        )
        assert score is None

    @pytest.mark.asyncio
    async def test_raises_when_no_ambulances(self):
        from core.exceptions import NoAmbulanceAvailableError

        db_mock = AsyncMock()
        with patch(
            "services.resource.AmbulanceRepository.list_available",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with pytest.raises(NoAmbulanceAvailableError):
                await self.service.find_best_unit(
                    db=db_mock,
                    incident_lat=30.7333,
                    incident_lng=76.7794,
                    severity=SeverityPriority.P1_CRITICAL,
                )
