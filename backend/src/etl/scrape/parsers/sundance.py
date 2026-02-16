"""Sundance 880 Series HTML parser.

Parses product pages from sundancespas.com to extract spa specifications
into the ScrapedSpecs intermediate format.

Page structure (verified 2026-02-16):
  - Specs section: ``<div class="product-attributes">`` with button "Specs"
    containing ``<li class="attribute-values">`` items with ``<label>``/``<span>``
  - Dimensions section: same container pattern with button "Dimensions"
    containing Height (in), Length (in), Width (in), Volume (gals)
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, Tag

from src.etl.scrape.parsers.base import ManufacturerParser, ScrapedSpecs
from src.etl.scrape.parsers.utils import (
    clean_text,
    parse_dimension_inches,
    parse_float,
    parse_gallons,
    parse_int,
    parse_weight_lbs,
)

logger = logging.getLogger(__name__)


class SundanceParser(ManufacturerParser):
    """Parser for Sundance 880 Series product pages on sundancespas.com.

    Sundance pages embed specs inside expandable ``<div class="product-attributes">``
    sections. Each section has a button title ("Specs", "Dimensions") and a
    ``<ul class="expand-content">`` containing ``<li class="attribute-values">``
    elements. Each ``<li>`` has a ``<label class="label">`` with the field name
    and a ``<span>`` with the value text.
    """

    def parse_model_page(self, html: str, model_name: str) -> ScrapedSpecs:
        """Parse a Sundance model product page into ScrapedSpecs.

        Args:
            html: Raw HTML of the product page.
            model_name: Expected model name (e.g. "Aspen", "Optima").

        Returns:
            ScrapedSpecs with extracted fields; unparseable fields stay None.
        """
        self.validate_model_name(html, model_name)

        soup = BeautifulSoup(html, "lxml")
        specs = ScrapedSpecs()

        # Collect all attribute label->value pairs from product-attributes sections
        attrs = self._extract_all_attributes(soup)

        if not attrs:
            logger.warning(
                "No spec attributes found on Sundance page for '%s'", model_name
            )
            return specs

        logger.info(
            "Found %d spec attributes for Sundance '%s': %s",
            len(attrs),
            model_name,
            list(attrs.keys()),
        )

        # --- Dimensions ---
        specs.height_inches = parse_dimension_inches(attrs.get("height (in)"))
        specs.length_inches = parse_dimension_inches(attrs.get("length (in)"))
        specs.width_inches = parse_dimension_inches(attrs.get("width (in)"))

        # --- Water capacity ---
        # Prefer "Volume (gals)" from Dimensions section (numeric), fall back
        # to "Volume" from Specs section (e.g. "505 gal / 1912 l")
        vol_gals = attrs.get("volume (gals)") or attrs.get("volume")
        specs.water_capacity_gallons = parse_gallons(vol_gals)

        # --- Weight ---
        specs.dry_weight_lbs = parse_weight_lbs(attrs.get("dry weight"))

        # --- Jets ---
        specs.total_jet_count = parse_int(attrs.get("jets"))

        # --- Electrical ---
        electrical_text = attrs.get("electrical") or ""
        specs.electrical_volts, specs.electrical_amps = self._parse_electrical(
            electrical_text
        )

        # --- Filtration ---
        # Filter Type field contains area, e.g. "MicroClean Ultra II ... 130 ft2 ..."
        filter_type_text = attrs.get("filter type") or ""
        specs.filtration_area_sqft = self._parse_filtration_area(filter_type_text)

        # --- Diverter valves ---
        specs.diverter_valves = parse_int(attrs.get("diverter valves #"))

        # --- Seating capacity ---
        # Not a structured field on Sundance pages; attempt to extract from
        # the descriptive text ("Comfortably seating seven")
        specs.seating_capacity = self._extract_seating_from_text(soup)

        # Log extraction results
        extracted = []
        missing = []
        for field_name in [
            "length_inches",
            "width_inches",
            "height_inches",
            "dry_weight_lbs",
            "water_capacity_gallons",
            "total_jet_count",
            "electrical_volts",
            "electrical_amps",
            "filtration_area_sqft",
            "diverter_valves",
            "seating_capacity",
        ]:
            if getattr(specs, field_name) is not None:
                extracted.append(field_name)
            else:
                missing.append(field_name)

        logger.info("Extracted fields: %s", extracted)
        if missing:
            logger.info("Missing fields: %s", missing)

        return specs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_all_attributes(soup: BeautifulSoup) -> dict[str, str]:
        """Gather all label->value pairs from product-attributes sections.

        Returns a dict keyed by lowercase, stripped label text (without
        trailing colon) mapped to the span value text.
        """
        attrs: dict[str, str] = {}

        for li in soup.select("li.attribute-values"):
            label_tag = li.find("label", class_="label")
            span_tag = li.find("span")
            if label_tag and span_tag:
                key = clean_text(label_tag.get_text())
                # Remove trailing colon from label
                key = key.rstrip(":").strip().lower()
                value = clean_text(span_tag.get_text())
                if key and value:
                    attrs[key] = value

        return attrs

    @staticmethod
    def _parse_electrical(text: str) -> tuple[int | None, int | None]:
        """Parse electrical spec text into (volts, amps).

        Example input:
            "North America (60 Hz): 240 VAC@50A or 60A; Export ..."

        Extracts the North America values: 240V, max amps (60A from "50A or 60A").
        """
        if not text:
            return None, None

        volts: int | None = None
        amps: int | None = None

        # Look for "NNN VAC" pattern
        volts_match = re.search(r"(\d+)\s*VAC", text)
        if volts_match:
            volts = int(volts_match.group(1))

        # Look for amps -- may be "50A or 60A" (take max) or just "50A"
        # First try the "XA or YA" pattern
        amps_or_match = re.search(r"(\d+)\s*A\s+or\s+(\d+)\s*A", text)
        if amps_or_match:
            amps = max(int(amps_or_match.group(1)), int(amps_or_match.group(2)))
        else:
            # Single amp value after @
            amps_match = re.search(r"@\s*(\d+)\s*A", text)
            if amps_match:
                amps = int(amps_match.group(1))

        return volts, amps

    @staticmethod
    def _parse_filtration_area(text: str) -> float | None:
        """Parse filtration area from filter type text.

        Example: "MicroClean Ultra II Filtration System, 130 ft2 ..."
        Returns: 130.0
        """
        if not text:
            return None

        # Match "NNN ft2" or "NNN ft&sup2;" (after HTML entity decode)
        area_match = re.search(r"(\d+\.?\d*)\s*ft", text)
        if area_match:
            return parse_float(area_match.group(1))

        return None

    @staticmethod
    def _extract_seating_from_text(soup: BeautifulSoup) -> int | None:
        """Attempt to extract seating capacity from page description text.

        Sundance pages mention seating in prose like "Comfortably seating seven",
        "seating six", or "up to seven adults" in the product description.
        """
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }

        # Patterns to try, in priority order
        patterns = [
            r"seating\s+(\w+)",
            r"seats?\s+(\w+)",
            r"up\s+to\s+(\w+)\s+adult",
            r"for\s+(?:up\s+to\s+)?(\w+)\s+adult",
            r"(\w+)\s+adult",
        ]

        # Search in product description / collapsible content
        for div in soup.select("div.value.content"):
            text = div.get_text().lower()
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    word = match.group(1)
                    if word in word_to_num:
                        return word_to_num[word]
                    if word.isdigit():
                        return int(word)

        return None
