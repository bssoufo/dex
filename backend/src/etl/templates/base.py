"""Base class for manufacturer-specific extraction templates.

Each manufacturer gets its own template subclass that defines extraction
prompts tailored to that manufacturer's PDF layout, terminology, and
spec organization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ManufacturerTemplate(ABC):
    """Abstract base for manufacturer extraction templates.

    Subclasses implement manufacturer-specific extraction prompts and
    page hints that guide the LLM's PDF understanding to the right
    pages and format expectations for each spec category.
    """

    @property
    @abstractmethod
    def manufacturer_name(self) -> str:
        """Return the manufacturer key (e.g. 'sundance')."""
        ...

    @property
    @abstractmethod
    def series_name(self) -> str:
        """Return the series name (e.g. '880 Series')."""
        ...

    @property
    @abstractmethod
    def models(self) -> list[str]:
        """Return list of model names in this series."""
        ...

    @abstractmethod
    def get_extraction_prompt(self, model_name: str, spec_category: str) -> str:
        """Return a manufacturer-specific extraction prompt for a category.

        Args:
            model_name: The specific model to extract (e.g. 'Aspen').
            spec_category: One of the 10 spec categories (e.g. 'jet_pumps').

        Returns:
            The full extraction prompt string.
        """
        ...

    @abstractmethod
    def get_page_hints(self, spec_category: str) -> str:
        """Return page number hints for where to find a category's data.

        Args:
            spec_category: One of the 10 spec categories.

        Returns:
            Human-readable hint about page locations (e.g. 'Pages 45-48').
        """
        ...
