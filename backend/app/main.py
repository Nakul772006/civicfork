"""FastAPI entry point and application lifecycle configuration for CivicFork."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import api_router
from app.config_loader import load_app_config
from app.exceptions import register_exception_handlers
from app.services.osm_service import get_osm_service
from app.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("civicfork")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown tasks."""
    logger.info("Initializing CivicFork backend (%s v%s)", settings.app_name, settings.app_version)
    logger.info("Demo area: %s", settings.demo_area)
    logger.info("OSM data directory: %s", settings.osm_data_dir)
    logger.info("Config directory: %s", settings.config_dir)

    # Load and validate YAML configurations at startup
    load_app_config()

    # Load and index cached OSM datasets at startup
    get_osm_service()

    yield

    logger.info("Shutting down CivicFork backend...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Municipality-only urban policy impact simulation and decision-support platform.",
        lifespan=lifespan,
    )

    # Configure CORS middleware for frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized error handlers
    register_exception_handlers(app)

    # Mount REST API routes
    app.include_router(api_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
