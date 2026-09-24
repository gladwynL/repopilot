from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.api.routes import auth, github, health, reviews

api_router = APIRouter()
# Public: liveness/readiness probes and the sign-in flow.
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api")
# Application endpoints require a signed-in, allowlisted user when AUTH_ENABLED=true.
protected = [Depends(require_user)]
api_router.include_router(github.router, prefix="/api", dependencies=protected)
api_router.include_router(reviews.router, prefix="/api", dependencies=protected)
