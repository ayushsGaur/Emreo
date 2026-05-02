"""
Custom exception hierarchy for the Ambulance Optimizer.

Every exception maps to a specific HTTP status code and a structured
JSON response body. Nothing in the system raises bare Exception.

Structure:
    AppException (base)
    ├── NotFoundError          → 404
    │   ├── IncidentNotFoundError
    │   └── AmbulanceNotFoundError
    ├── ConflictError          → 409
    │   └── IncidentAlreadyClosedError
    ├── ValidationError        → 422
    │   └── InvalidCoordinatesError
    ├── ServiceUnavailableError → 503
    │   ├── NoAmbulanceAvailableError
    │   ├── RoutingServiceError
    │   └── SeverityModelError
    └── UnauthorizedError      → 401
"""

from typing import Any


class AppException(Exception):
    """Base class for all application exceptions."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, detail: Any = None):
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }


# ── 404 Not Found ─────────────────────────────────────────────────────────────

class NotFoundError(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found."


class IncidentNotFoundError(NotFoundError):
    error_code = "INCIDENT_NOT_FOUND"
    message = "The requested incident does not exist."


class AmbulanceNotFoundError(NotFoundError):
    error_code = "AMBULANCE_NOT_FOUND"
    message = "The requested ambulance does not exist."


# ── 409 Conflict ──────────────────────────────────────────────────────────────

class ConflictError(AppException):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource conflict."


class IncidentAlreadyClosedError(ConflictError):
    error_code = "INCIDENT_ALREADY_CLOSED"
    message = "This incident has already been closed and cannot be modified."


class AmbulanceAlreadyDispatchedError(ConflictError):
    error_code = "AMBULANCE_ALREADY_DISPATCHED"
    message = "This ambulance is already dispatched to another incident."


# ── 422 Validation ────────────────────────────────────────────────────────────

class ValidationError(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Input validation failed."


class InvalidCoordinatesError(ValidationError):
    error_code = "INVALID_COORDINATES"
    message = "Provided coordinates are outside valid geographic bounds."


class GeocodingFailedError(ValidationError):
    error_code = "GEOCODING_FAILED"
    message = "Could not resolve the provided address to coordinates."


# ── 503 Service Unavailable ───────────────────────────────────────────────────

class ServiceUnavailableError(AppException):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
    message = "A required service is temporarily unavailable."


class NoAmbulanceAvailableError(ServiceUnavailableError):
    error_code = "NO_AMBULANCE_AVAILABLE"
    message = "No ambulance units are currently available in the service area."


class RoutingServiceError(ServiceUnavailableError):
    error_code = "ROUTING_SERVICE_ERROR"
    message = "The routing service failed to compute a route."


class SeverityModelError(ServiceUnavailableError):
    error_code = "SEVERITY_MODEL_ERROR"
    message = "The severity prediction model encountered an error."


class RedisConnectionError(ServiceUnavailableError):
    error_code = "CACHE_UNAVAILABLE"
    message = "The real-time state cache is unavailable."


# ── 401 Unauthorized ──────────────────────────────────────────────────────────

class UnauthorizedError(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Invalid or missing API credentials."
