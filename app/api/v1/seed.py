from fastapi import APIRouter, Request, HTTPException, status, Body
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
import json  
from typing import List 

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


# ---------- models ----------
class RuntimeStateIn(BaseModel):
    campaign_id: str
    assistant_id: str
    thread_id: str
    state_json: dict | None = None

# ---------- routes ----------
@router.post("/save_runtime_state", status_code=200)
async def save_runtime_state(payload: RuntimeStateIn, request: Request):
    pool = request.app.state.pool
    q = """
    INSERT INTO runtime_states (campaign_id, assistant_id, thread_id, state_json)
    VALUES ($1, $2, $3,
            coalesce(nullif($4, '{}'::jsonb),
                    '{"story_so_far":"","character_sheet":{"name":""}}'::jsonb))
    ON CONFLICT (campaign_id) DO UPDATE
    SET assistant_id = EXCLUDED.assistant_id,
        thread_id    = EXCLUDED.thread_id,
        state_json   = jsonb_strip_nulls(
                        jsonb_concat(
                          runtime_states.state_json,
                          (
                              SELECT jsonb_object_agg(key, value)
                              FROM jsonb_each(EXCLUDED.state_json)
                              WHERE value IS NOT NULL
                                AND value::text NOT IN ('""', '[]', '{}')
                          )
                        )
                    ),
        updated_at   = now();
    """
    async with pool.acquire() as conn:
        await conn.execute(q, 
                           payload.campaign_id, 
                           payload.assistant_id,
                           payload.thread_id, 
                           json.dumps(payload.state_json or {}))
    return {"status": "OK"}

@router.get("/load_runtime_state/{campaign_id}")
async def load_runtime_state(campaign_id: str, request: Request):
    pool = request.app.state.pool
    async with pool.acquire() as conn:           # ← mirror pattern
        row = await conn.fetchrow(
            "SELECT assistant_id, thread_id, state_json FROM runtime_states WHERE campaign_id=$1",
            campaign_id)
    if not row:
        raise HTTPException(404, "runtime_state not found")
    return dict(row)

@router.post("/bulk_embed", status_code=200)
async def bulk_embed(payload: list[dict], request: Request):
    pool = request.app.state.pool
    # 👇 cast parameter 3 to vector
    q = """
        INSERT INTO embeddings (campaign_id, chunk, embedding)
        VALUES ($1, $2, $3::vector)
    """
    async with pool.acquire() as conn:
        await conn.executemany(
            q,
            [(
                row["campaign_id"],
                row["chunk"],
                "[" + ",".join(str(x) for x in row["embedding"]) + "]"  # 👈 text‑encode
            ) for row in payload]
        )
    return {"status": "OK"}

class EmbeddingQuery(BaseModel):
    campaign_id: str
    embedding: List[float]
    top_k: int = 8

@router.post("/query_embeddings", status_code=200)
async def query_embeddings(payload: EmbeddingQuery, request: Request):
    async with request.app.state.pool.acquire() as conn:
        # ✅ Convert list[float] to string for SQL casting into vector type
        emb_str = "[" + ",".join(str(x) for x in payload.embedding) + "]"
        q = """
            SELECT id, chunk
            FROM embeddings
            WHERE campaign_id = $1
            ORDER BY embedding <#> $2::vector
            LIMIT $3
        """
        rows = await conn.fetch(q, payload.campaign_id, emb_str, payload.top_k)
        return [{"id": row["id"], "chunk": row["chunk"]} for row in rows]

@router.post("/match_chunks", status_code=200)
async def match_chunks(payload: EmbeddingQuery, request: Request):
    return await query_embeddings(payload, request)