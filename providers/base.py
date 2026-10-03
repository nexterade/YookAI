"""Provider abstraction used by YookAI."""

from abc import ABC, abstractmethod
from typing import Iterator


class BaseProvider(ABC):
    """Common interface implemented by every YookAI AI provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider identifier used by YookAI."""
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[dict]:
        """Return the provider's available models in normalized dictionary form."""
        raise NotImplementedError

    @abstractmethod
    def stream_chat(self, messages, model, **kwargs) -> Iterator[dict]:
        """Stream a chat completion as normalized chunks.

        Chunks use one of these forms:
        ``{"type": "reasoning", "content": "..."}``,
        ``{"type": "content", "content": "..."}``,
        ``{"type": "done"}``, or
        ``{"type": "error", "message": "..."}``.
        """
        raise NotImplementedError

    @abstractmethod
    def stop_chat(self, request_id) -> bool:
        """Request cancellation of an active stream identified by request_id."""
        raise NotImplementedError
