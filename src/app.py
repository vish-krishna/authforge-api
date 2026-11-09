from contextlib import asynccontextmanager
from fastapi import FastAPI
# from src.api.v1 import register_application_routes
from src.config.secrets import SECRETS
# from src.core.error_handler import register_error_handlers
from src.db import close_db, connect_db, create_all_tables
from src.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Fetch AWS secrets asynchronously
    SECRETS.load_secrets()

    # 2. Establish DB pool with the fetched credentials
    await connect_db()

    await create_all_tables()  # Optional: Create tables if they don't exist (for dev/testing)

    logger.info("Application startup complete.")
    logger.debug("debug Application startup complete.")
    yield

    # 3. Clean teardown
    await close_db()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AuthForge",
        lifespan=lifespan,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Registered once at boot time, not during lifespan
    # register_application_routes(app)
    # register_error_handlers(app)

    return app


app = create_app()