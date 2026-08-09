from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from accessforge import __version__
from accessforge.api.routes import (
    assets,
    auth,
    consents,
    designs,
    exports,
    health,
    measurements,
    model_providers,
    observations,
    projects,
    requirements,
    risk,
    templates,
)
from accessforge.core.config import get_settings
from accessforge.db.session import initialize_database

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await initialize_database()
    yield


app = FastAPI(
    title="AccessForge API",
    version=__version__,
    summary="Private project foundation for AccessForge",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


def problem_response(
    status_code: int, title: str, detail: str, instance: str | None = None
) -> JSONResponse:
    body: dict[str, str | int] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    return JSONResponse(
        status_code=status_code, content=body, media_type="application/problem+json"
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return problem_response(exc.status_code, "Request failed", detail, str(request.url.path))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, _: RequestValidationError) -> JSONResponse:
    return problem_response(
        422, "Validation failed", "One or more request fields are invalid.", str(request.url.path)
    )


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {"service": "accessforge-api", "version": __version__, "status": "ok"}


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(consents.router)
app.include_router(observations.router)
app.include_router(measurements.router)
app.include_router(assets.router)
app.include_router(model_providers.router)
app.include_router(requirements.router)
app.include_router(templates.router)
app.include_router(designs.router)
app.include_router(risk.router)
app.include_router(exports.router)
