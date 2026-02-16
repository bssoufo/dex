"""Abstract base class for manufacturer-specific HTML parsers.

Defines the ScrapedSpecs intermediate dataclass and the ManufacturerParser
ABC that each manufacturer parser (Sundance, Hot Spring, Bullfrog) must
implement.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ScrapedSpecs:
    """Intermediate container for specs extracted from a web page.

    NOT a Pydantic model -- this is a plain dataclass used between
    HTML parsing and the merge step that writes into the Pydantic
    SpaModel JSON files.

    All fields are optional (None) because not every manufacturer
    page includes every data point.
    """

    length_inches: float | None = None
    width_inches: float | None = None
    height_inches: float | None = None
    dry_weight_lbs: float | None = None
    filled_weight_lbs: float | None = None
    water_capacity_gallons: float | None = None
    seating_capacity: int | None = None
    total_jet_count: int | None = None
    pump_count: int | None = None
    filtration_area_sqft: float | None = None
    heater_wattage: int | None = None
    electrical_volts: int | None = None
    electrical_amps: int | None = None
    diverter_valves: int | None = None
    source_url: str = ""


class ManufacturerParser(ABC):
    """Abstract base for manufacturer-specific HTML parsers.

    Subclasses must implement ``parse_model_page`` to extract specs
    from a single model's product page HTML.
    """

    @abstractmethod
    def parse_model_page(self, html: str, model_name: str) -> ScrapedSpecs:
        """Parse a single model's product page HTML into structured specs.

        Args:
            html: Raw HTML of the product page.
            model_name: Expected model name (e.g. "Grandee", "M9").

        Returns:
            A ScrapedSpecs instance with whatever fields could be extracted.
        """
        ...

    def validate_model_name(self, html: str, expected_model: str) -> bool:
        """Check whether the expected model name appears on the page.

        Looks in the ``<title>`` tag and all ``<h1>`` tags (case-insensitive).
        Logs a warning if the name is not found but does NOT raise.

        Args:
            html: Raw HTML of the page.
            expected_model: The model name to look for.

        Returns:
            True if the model name was found, False otherwise.
        """
        soup = BeautifulSoup(html, "lxml")
        search_term = expected_model.lower()

        # Check <title>
        title_tag = soup.find("title")
        if title_tag and search_term in title_tag.get_text().lower():
            return True

        # Check all <h1> tags
        for h1 in soup.find_all("h1"):
            if search_term in h1.get_text().lower():
                return True

        logger.warning(
            "Model name '%s' not found in page title or h1 tags",
            expected_model,
        )
        return False
