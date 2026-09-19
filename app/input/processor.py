"""Abstract base class for input processors."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

from app.input.schemas import ProcessingResult


class InputProcessor(ABC):
    """Abstract interface for all text and media processors."""

    @abstractmethod
    def process_text(self, text: str, context: Optional[dict] = None) -> ProcessingResult:
        """Parse natural language or formatted text into structured ProcessingResult."""
        pass

    @abstractmethod
    def process_photo(
        self,
        image_path: Union[str, Path],
        caption: Optional[str] = None
    ) -> ProcessingResult:
        """Process image file into structured ProcessingResult."""
        pass
