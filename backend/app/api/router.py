from fastapi import APIRouter

from app.api.routes import github, health, reviews

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(github.router, prefix="/api")
api_router.include_router(reviews.router, prefix="/api")
