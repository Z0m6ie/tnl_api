"""OpenAI Chat Completions client wrapper."""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Type, TypeVar

import certifi
import openai
from pydantic import BaseModel, ValidationError

# Fix SSL certificate issues on Windows
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Wrapper around OpenAI Chat Completions API.

    Provides structured output support and retry logic.
    """

    def __init__(
        self,
        model: str = "gpt-5.2",
        api_key: Optional[str] = None,
        max_retries: int = 3,
    ):
        self.model = model
        self.max_retries = max_retries
        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 1000,
        temperature: float = 0.8,
    ) -> str:
        """
        Generate a text response.

        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            context: Optional conversation history
            max_tokens: Maximum response tokens
            temperature: Sampling temperature

        Returns:
            The generated text response
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if context:
            messages.extend(context)

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=max_tokens,
            temperature=temperature,
        )

        return response.choices[0].message.content or ""

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> T:
        """
        Generate a structured response matching a Pydantic schema.

        Uses OpenAI's JSON mode with schema enforcement.

        Args:
            prompt: The user prompt
            schema: Pydantic model class for the expected response
            system_prompt: Optional system instructions
            context: Optional conversation history
            max_tokens: Maximum response tokens
            temperature: Sampling temperature

        Returns:
            Parsed Pydantic model instance

        Raises:
            ValidationError: If response doesn't match schema after retries
        """
        messages = []

        # Build system prompt with schema
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_system = (system_prompt or "") + f"\n\nRespond with valid JSON matching this schema:\n{schema_json}"
        messages.append({"role": "system", "content": full_system})

        if context:
            messages.extend(context)

        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)
                return schema.model_validate(data)

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
                last_error = e
            except ValidationError as e:
                logger.warning(f"Validation error on attempt {attempt + 1}: {e}")
                last_error = e
                # Add clarification for next attempt
                messages.append({
                    "role": "assistant",
                    "content": content if "content" in dir() else "{}"
                })
                messages.append({
                    "role": "user",
                    "content": f"The response didn't match the required schema. Error: {e}. Please try again with valid JSON."
                })

        raise ValidationError.from_exception_data(
            title=schema.__name__,
            line_errors=[],
        ) if last_error is None else last_error

    def embed(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed
            model: Embedding model to use

        Returns:
            Embedding vector
        """
        response = self.client.embeddings.create(model=model, input=[text])
        return response.data[0].embedding

    def embed_batch(
        self, texts: List[str], model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Embedding model to use

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        response = self.client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in response.data]
