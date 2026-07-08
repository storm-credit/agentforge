from fastapi import APIRouter

from app.api.v1 import agents, audit, eval as eval_api, knowledge, runs

api_router = APIRouter()
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(eval_api.router, prefix="/eval", tags=["eval"])

