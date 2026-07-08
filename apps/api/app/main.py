from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import check_database
from app.domain.vector import check_vector_store
from app.infra.object_store import check_object_store


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
        result: dict[str, str] = {"status": "ok"}
        degraded = False

        if not settings.readiness_check_database:
            result["database"] = "skipped"
        elif check_database():
            result["database"] = "ok"
        else:
            result["database"] = "unavailable"
            degraded = True

        vector_ok = check_vector_store()
        if vector_ok is None:
            result["vector_store"] = "skipped"
        elif vector_ok:
            result["vector_store"] = "ok"
        else:
            result["vector_store"] = "unavailable"
            degraded = True

        object_ok = check_object_store()
        if object_ok is None:
            result["object_store"] = "skipped"
        elif object_ok:
            result["object_store"] = "ok"
        else:
            result["object_store"] = "unavailable"
            degraded = True

        if degraded:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            result["status"] = "degraded"
        return result

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

