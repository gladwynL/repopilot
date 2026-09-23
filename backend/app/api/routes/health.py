import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.health import HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness: the process is up. Deliberately independent of external services."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def ready(request: Request) -> ReadinessResponse | JSONResponse:
    """Readiness: the database is reachable."""
    try:
        with request.app.state.db_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("ready.database_unavailable type=%s", type(exc).__name__)
        return JSONResponse(
            ReadinessResponse(status="unavailable").model_dump(),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return ReadinessResponse(status="ready")
