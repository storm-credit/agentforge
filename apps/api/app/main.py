from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import check_database


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    @app.get("/readyz", tags=["system"])
    def readyz(response: Response) -> dict[str, str]:
        if not settings.readiness_check_database:
            return {"status": "ok", "database": "skipped"}

        if check_database():
            return {"status": "ok", "database": "ok"}

        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": "unavailable"}

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

