import os
import uvicorn
from src.logger import logger


def run():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    reload = os.getenv("ENV", "development") == "development"

    logger.info(f"Starting AuthForge on http://{host}:{port}")
    logger.info(f"Docs available at http://localhost:{port}/docs")
    uvicorn.run("src.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()