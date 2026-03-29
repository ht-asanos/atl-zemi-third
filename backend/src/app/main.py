from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.config import settings
from app.exceptions import AppException, app_exception_handler
from app.routers import (
    admin_review,
    admin_training_progressions,
    admin_youtube,
    feedback,
    foods,
    goals,
    logs,
    plans,
    profiles,
    recipes,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from supabase import acreate_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.supabase = await acreate_client(settings.supabase_url, settings.supabase_anon_key)
    if settings.supabase_service_role_key:
        app.state.service_supabase = await acreate_client(settings.supabase_url, settings.supabase_service_role_key)
    else:
        app.state.service_supabase = None
    yield


app = FastAPI(title="Bouldering App Backend", lifespan=lifespan)

app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(goals.router)
app.include_router(plans.router)
app.include_router(foods.router)
app.include_router(logs.router)
app.include_router(feedback.router)
app.include_router(recipes.router)
app.include_router(admin_review.router)
app.include_router(admin_youtube.router)
app.include_router(admin_training_progressions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
