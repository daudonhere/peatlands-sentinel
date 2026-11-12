from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes.views import router as views_router
from app.routes.api.peatlands import router as peatlands_router
from app.routes.api.analysis import router as analysis_router
from app.routes.api.insights import router as insights_router
from app.services.storage import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    from app.services import cog as _cog

    _cog._executor.shutdown(wait=False)


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(views_router)
app.include_router(peatlands_router)
app.include_router(analysis_router)
app.include_router(insights_router)
