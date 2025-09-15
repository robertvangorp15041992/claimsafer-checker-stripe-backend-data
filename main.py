# This file imports the FastAPI app from the app directory
# Railway needs this to find the app when using uvicorn main:app

from app.main import app

# This makes the app available at the root level for Railway
__all__ = ["app"]
