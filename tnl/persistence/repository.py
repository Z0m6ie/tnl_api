"""Campaign persistence repository - wraps existing FastAPI endpoints."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests
import tiktoken

from ..llm import LLMClient
from ..models.campaign import CampaignState

logger = logging.getLogger(__name__)

# Default to deployed API, can be overridden
DEFAULT_BASE_URL = "https://tnl-api-blue-snow-1079.fly.dev"
EMBED_MODEL = "text-embedding-3-small"


class CampaignRepository:
    """
    Repository for campaign persistence.

    Wraps the existing FastAPI endpoints in app/api/v1/seed.py.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.base_url = (base_url or os.getenv("SUPABASE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_base = f"{self.base_url}/v1"
        self.llm_client = llm_client or LLMClient()
        self._tokenizer = None

    @property
    def tokenizer(self):
        """Lazy load tokenizer."""
        if self._tokenizer is None:
            self._tokenizer = tiktoken.encoding_for_model(EMBED_MODEL)
        return self._tokenizer

    def save_seed_chunk(
        self,
        chunk_order: int,
        seed_chunk: str,
        campaign_id: Optional[str] = None,
    ) -> str:
        """
        Save a seed chunk to the database.

        Args:
            chunk_order: Order index of this chunk (0-4)
            seed_chunk: The narrative chunk text
            campaign_id: Campaign ID (omit for first chunk to create new campaign)

        Returns:
            The campaign ID (created on first call)
        """
        payload = {
            "chunk_order": chunk_order,
            "seed_chunk": seed_chunk,
        }
        if campaign_id:
            payload["campaign_id"] = campaign_id

        response = requests.post(
            f"{self.api_base}/save_seed_chunk",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        data = response.json()
        saved_id = data.get("campaign_id")

        # Also store embedding for context retrieval
        self._embed_and_store(saved_id, seed_chunk)

        return saved_id

    def load_campaign_chunks(self, campaign_id: str) -> List[Dict[str, Any]]:
        """
        Load all seed chunks for a campaign.

        Args:
            campaign_id: The campaign UUID

        Returns:
            List of chunk dicts with 'order' and 'text' keys
        """
        response = requests.get(f"{self.api_base}/load_campaign/{campaign_id}")
        response.raise_for_status()
        return response.json().get("chunks", [])

    def save_runtime_state(
        self,
        campaign_id: str,
        state: CampaignState,
    ) -> None:
        """
        Save the current campaign state.

        Args:
            campaign_id: The campaign UUID
            state: The campaign state to save
        """
        # Build state dict compatible with existing schema
        state_json = {
            "campaign_id": campaign_id,
            "phase": state.phase.value,
            "genre": state.genre,
            "tone": state.tone,
            "story_type": state.story_type,
            "character_sheet": state.character_sheet.model_dump(),
            "seed_chunks": state.seed_chunks,
            "inventory": state.inventory,
            "abilities": state.abilities,
            "locations": state.discovered_locations,
            "key_people": state.known_npcs,
            "world_events": state.active_events,
            "message_history": state.message_history[-50:],  # Keep last 50 messages
            # Simulation layer
            "simulation": state.simulation.model_dump() if state.simulation else None,
            "current_location": state.current_location,
            "current_turn": state.current_turn,
        }

        response = requests.post(
            f"{self.api_base}/save_runtime_state",
            json={
                "campaign_id": campaign_id,
                "assistant_id": "",  # No longer used
                "thread_id": "",  # No longer used
                "state_json": state_json,
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    def load_runtime_state(self, campaign_id: str) -> Optional[CampaignState]:
        """
        Load a campaign's runtime state.

        Args:
            campaign_id: The campaign UUID

        Returns:
            CampaignState if found, None otherwise
        """
        try:
            response = requests.get(f"{self.api_base}/load_runtime_state/{campaign_id}")
            response.raise_for_status()
            data = response.json()

            state_json = data.get("state_json")
            if isinstance(state_json, str):
                state_json = json.loads(state_json)

            if not state_json:
                return None

            return CampaignState.from_saved(state_json)

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def query_similar_chunks(
        self,
        campaign_id: str,
        query_text: str,
        top_k: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Find similar chunks using embedding similarity.

        Args:
            campaign_id: The campaign UUID
            query_text: Text to find similar chunks for
            top_k: Number of results to return

        Returns:
            List of matching chunks with similarity scores
        """
        # Generate embedding for query
        query_embed = self.llm_client.embed(query_text)

        response = requests.post(
            f"{self.api_base}/match_chunks",
            json={
                "campaign_id": campaign_id,
                "embedding": query_embed,
                "top_k": top_k,
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def _chunk_text(self, text: str, max_tokens: int = 600) -> List[str]:
        """Split text into token-limited chunks."""
        ids = self.tokenizer.encode(text)
        chunks = []
        for i in range(0, len(ids), max_tokens):
            chunk_ids = ids[i : i + max_tokens]
            chunks.append(self.tokenizer.decode(chunk_ids))
        return chunks

    def _embed_and_store(self, campaign_id: str, text: str) -> None:
        """Embed text chunks and store in database."""
        chunks = self._chunk_text(text)
        if not chunks:
            return

        embeddings = self.llm_client.embed_batch(chunks)
        rows = [
            {"campaign_id": campaign_id, "chunk": chunk, "embedding": emb}
            for chunk, emb in zip(chunks, embeddings)
        ]

        try:
            response = requests.post(
                f"{self.api_base}/bulk_embed",
                json=rows,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.warning(f"Failed to store embeddings: {e}")
