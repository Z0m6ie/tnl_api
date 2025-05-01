from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

import app.utils as utils   # unchanged

router = APIRouter(prefix="/v1", tags=["seed"])


class SeedChunkIn(BaseModel):
    campaign_id: str | None = None        # optional now
    chunk_order: int = Field(ge=0)
    seed_chunk: str = Field(..., max_length=20_000)


@router.post("/save_seed_chunk", status_code=status.HTTP_200_OK)
async def save_seed_chunk(payload: SeedChunkIn, request: Request):
    """
    • First call → omit campaign_id → create campaign, return new UUID  
    • Subsequent calls → send the UUID → append / upsert the chunk
    """
    pool = request.app.state.pool

    # 1. Resolve the campaign ID
    if payload.campaign_id:
        try:
            cid = UUID(payload.campaign_id)
        except ValueError:
            raise HTTPException(400, "Invalid campaign_id format")

        # ❒ ensure the campaign already exists
        if not await utils.campaign_exists(pool, cid):
            raise HTTPException(404, "campaign_id not found")

    else:  # create on first save
        cid = await utils.create_campaign(pool)  # returns a UUID

    # 2. UPSERT the chunk
    q = """
        INSERT INTO seed_chunks (campaign_id, chunk_order, chunk_text)
        VALUES ($1, $2, $3)
        ON CONFLICT (campaign_id, chunk_order)
        DO UPDATE SET chunk_text = EXCLUDED.chunk_text
    """
    async with pool.acquire() as conn:
        await conn.execute(q, cid, payload.chunk_order, payload.seed_chunk)

    return {"status": "OK", "campaign_id": str(cid)}


@router.get("/load_campaign/{campaign_id}")
async def load_campaign(campaign_id: str, request: Request):
    try:
        cid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(400, "Invalid campaign_id format")

    q = """
        SELECT chunk_order, chunk_text
        FROM seed_chunks
        WHERE campaign_id = $1
        ORDER BY chunk_order
    """
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch(q, cid)

    if not rows:
        raise HTTPException(404, "Campaign not found")

    return {
        "campaign_id": campaign_id,
        "chunks": [{"order": r[0], "text": r[1]} for r in rows],
    }
