from fastapi import APIRouter

from app.api.routes import github, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(github.router, prefix="/api")
