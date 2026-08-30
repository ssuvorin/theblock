from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    connections,
    drafts,
    followups,
    health,
    imports,
    interactions,
    opportunities,
    people,
    query,
)
from app.config import Settings
from app.database import Database
from app.models import Base
from app.services.demo_seed import DemoSeeder


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()
    database = Database(runtime_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(database.engine)
        if runtime_settings.seed_demo_data:
            with database.session_factory() as session:
                DemoSeeder(session, runtime_settings).seed()
        yield
        database.engine.dispose()

    application = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.database = database
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for router in (
        health.router,
        auth.router,
        connections.router,
        imports.router,
        opportunities.router,
        query.router,
        people.router,
        interactions.router,
        drafts.router,
        followups.router,
    ):
        application.include_router(router)
    return application


app = create_app()
