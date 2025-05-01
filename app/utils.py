from uuid import uuid4

async def campaign_exists(pool, cid):
    q = "SELECT 1 FROM campaigns WHERE campaign_id = $1 LIMIT 1"
    async with pool.acquire() as conn:
        return bool(await conn.fetchrow(q, cid))

async def create_campaign(pool):
    cid = uuid4()
    q = "INSERT INTO campaigns (campaign_id) VALUES ($1)"
    async with pool.acquire() as conn:
        await conn.execute(q, cid)
    return cid