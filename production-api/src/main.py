import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file searching parent folders
load_dotenv(find_dotenv())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.session import create_tables
from src.routes.articles import router as articles_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Auto-create tables in PostgreSQL production database
    print("Starting up ProvenPick Production API... Auto-creating database tables.")
    await create_tables()
    yield
    # Shutdown: Clean up operations (if any)
    print("Shutting down ProvenPick Production API.")

app = FastAPI(
    title="ProvenPick Production API",
    description="FastAPI Backend for the Live Public Site of ProvenPick",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration to allow React dashboards to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production, but open for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(articles_router)

@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for monitoring tools.
    """
    return {
        "status": "healthy",
        "service": "provenpick_production_api",
        "database": "connected"
    }

if __name__ == "__main__":
    import uvicorn
    # Use environment variables if set, otherwise default to port 8002
    port = int(os.environ.get("PRODUCTION_API_PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
