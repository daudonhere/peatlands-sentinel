from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes.views import router as views_router
from app.routes.api.peatlands import router as peatlands_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lifecycle startup hook
    yield
    # Lifecycle shutdown hook


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Mount local assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount routes
app.include_router(views_router)
app.include_router(peatlands_router)
