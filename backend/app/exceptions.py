"""CivicFork custom exception hierarchy and error handling."""

from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class CivicForkError(Exception):
    """Base exception for all CivicFork domain errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class ValidationError(CivicForkError):
    """Raised when request payload or data validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class PlotOutOfBoundsError(CivicForkError):
    """Raised when coordinates fall outside the supported demo area."""

    def __init__(self, message: str = "Plot location is outside the demo area bounds"):
        super().__init__(
            message=message,
            code="PLOT_OUT_OF_BOUNDS",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class SessionNotFoundError(CivicForkError):
    """Raised when an invalid or expired session_id is provided."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session not found: {session_id}",
            code="SESSION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"session_id": session_id},
        )


class MissingPrerequisiteError(CivicForkError):
    """Raised when an endpoint is called before its prerequisite workflow step."""

    def __init__(self, message: str, missing_field: Optional[str] = None):
        super().__init__(
            message=message,
            code="MISSING_PREREQUISITE",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"missing_field": missing_field} if missing_field else None,
        )


class OSMDataError(CivicForkError):
    """Raised when OpenStreetMap data loading or querying fails."""

    def __init__(self, message: str = "Failed to load or query OpenStreetMap data"):
        super().__init__(
            message=message,
            code="OSM_DATA_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class SimulationError(CivicForkError):
    """Raised when deterministic simulation scoring encounters an unrecoverable error."""

    def __init__(self, message: str = "Simulation scoring failed"):
        super().__init__(
            message=message,
            code="SIMULATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class FeasibilityError(CivicForkError):
    """Raised when scenario feasibility checking encounters an unrecoverable error."""

    def __init__(self, message: str = "Feasibility check failed"):
        super().__init__(
            message=message,
            code="FEASIBILITY_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ConfigurationError(CivicForkError):
    """Raised when configuration loading or validation fails."""

    def __init__(
        self,
        message: str = "Configuration error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="CONFIG_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class GeminiAPIError(CivicForkError):
    """Raised when external AI narrative generation fails."""

    def __init__(self, message: str = "Gemini API service unavailable or failed"):
        super().__init__(
            message=message,
            code="GEMINI_API_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ReportGenerationError(CivicForkError):
    """Raised when ReportLab PDF generation fails."""

    def __init__(self, message: str = "Failed to generate decision-support PDF report"):
        super().__init__(
            message=message,
            code="REPORT_GENERATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform error envelope handlers with the FastAPI application."""

    @app.exception_handler(CivicForkError)
    async def civicfork_exception_handler(_: Request, exc: CivicForkError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters",
                    "details": {"errors": jsonable_encoder(exc.errors())},
                },
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        code_map = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            400: "BAD_REQUEST",
            422: "VALIDATION_ERROR",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": code_map.get(exc.status_code, "HTTP_ERROR"),
                    "message": str(exc.detail),
                    "details": None,
                },
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected server error occurred",
                    "details": None,
                },
            },
        )
