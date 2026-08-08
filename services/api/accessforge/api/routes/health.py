from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from accessforge import __version__
from accessforge.db.session import database_is_ready

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "accessforge-api", "version": __version__}


@router.get("/health/ready", summary="Readiness probe", response_model=None)
async def readiness() -> dict[str, str] | JSONResponse:
    if not await database_is_ready():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "service": "accessforge-api"},
        )
    return {"status": "ready", "service": "accessforge-api", "version": __version__}
