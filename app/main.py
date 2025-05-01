from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

from app.api.v1 import seed
from app.core.config import get_settings

app = FastAPI(title="TNL Seed API")

# --- Health check ---------------------------------------------------------
@app.get("/health", include_in_schema=False)
async def health():
    # If you like, add a lightweight DB ping here
    # await app.state.pool.execute("SELECT 1")
    return {"status": "ok"}
# --------------------------------------------------------------------------

app.include_router(seed.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    settings = get_settings()
    print("Connecting to Supabase DB:", settings.database_url)
    app.state.pool = await asyncpg.create_pool(
        settings.database_url, min_size=1, max_size=5
    )

@app.on_event("shutdown")
async def shutdown():
    await app.state.pool.close()