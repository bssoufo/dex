"""Bullfrog M Series HTML parser.

Parses dealer pages from bullfrogfactorystores.com to extract spa
specifications into the ScrapedSpecs intermediate format.

Page structure (verified 2026-02-16):
  - Structured span pairs: ``<span class="label">Key:</span>``
    followed by ``<span class="value">Value</span>`` in the same container.
  - Spec table: ``<table>`` with ``<tr>`` rows containing ``<td>`` cells
    for additional detail (seat breakdown, pump count, equipment lists).
  - Model name appears in ``<span class="value">Model M9</span>`` and in
    image alt text.
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


class BullfrogParser(ManufacturerParser):
    """Parser for Bullfrog M Series dealer pages on bullfrogfactorystores.com.

    The dealer site uses ``span.label`` / ``span.value`` pairs for key specs
    and an HTML ``<table>`` for the detailed specification sheet.

    IMPORTANT: Bullfrog robots.txt specifies a 10-second crawl delay. The
    fetcher handles this via the RATE_LIMITS config, but be aware that
    fetching multiple Bullfrog pages will be slow by design.
    """

    def parse_model_page(self, html: str, model_name: str) -> ScrapedSpecs:
        """Parse a Bullfrog model dealer page into ScrapedSpecs.

        If the page title/model field does not contain the expected model name,
        returns an empty ScrapedSpecs to avoid extracting wrong model data.

        Args:
            html: Raw HTML of the dealer page.
            model_name: Expected model name (e.g. "M9", "M6").

        Returns:
            ScrapedSpecs with extracted fields; unparseable fields stay None.
        """
        logger.info(
            "Parsing Bullfrog page for '%s' (10s crawl-delay in effect)",
            model_name,
        )

        soup = BeautifulSoup(html, "lxml")

        # --- Model name validation ---
        # Bullfrog unit_id URLs may change. If the page shows a different model,
        # return empty specs rather than extracting wrong data.
        if not self._validate_bullfrog_model(soup, model_name):
            logger.warning(
                "Model mismatch: expected '%s' but page shows different model. "
                "Returning empty ScrapedSpecs to avoid incorrect extraction.",
                model_name,
            )
            return ScrapedSpecs()

        specs = ScrapedSpecs()

        # --- Extract from span.label / span.value pairs ---
        span_attrs = self._extract_span_attributes(soup)

        if not span_attrs:
            logger.warning(
                "No span attributes found on Bullfrog page for '%s'", model_name
            )

        logger.info(
            "Found %d span attributes for Bullfrog '%s': %s",
            len(span_attrs),
            model_name,
            list(span_attrs.keys()),
        )

        # --- Extract from spec table ---
        table_attrs = self._extract_table_attributes(soup)
        logger.info(
            "Found %d table attributes for Bullfrog '%s'",
            len(table_attrs),
            model_name,
        )

        # --- Dimensions (from span pairs) ---
        specs.length_inches = parse_dimension_inches(span_attrs.get("length"))
        specs.width_inches = parse_dimension_inches(span_attrs.get("width"))
        specs.height_inches = parse_dimension_inches(span_attrs.get("height"))

        # --- Water capacity ---
        holds_text = span_attrs.get("holds") or ""
        specs.water_capacity_gallons = parse_gallons(holds_text)

        # --- Weights ---
        specs.dry_weight_lbs = parse_weight_lbs(span_attrs.get("dry weight"))
        specs.filled_weight_lbs = parse_weight_lbs(span_attrs.get("filled weight"))

        # --- Seating ---
        seats_text = span_attrs.get("seats") or ""
        specs.seating_capacity = parse_int(seats_text)
        # Fall back to table "Total Seats" if span didn't have it
        if specs.seating_capacity is None:
            specs.seating_capacity = parse_int(table_attrs.get("total seats"))

        # --- Pumps ---
        specs.pump_count = parse_int(span_attrs.get("number of pumps"))
        # Fall back to table "High-Performance 2-Speed Jet Pumps"
        if specs.pump_count is None:
            for key, val in table_attrs.items():
                if "jet pump" in key.lower():
                    specs.pump_count = parse_int(val)
                    break

        # --- Jets ---
        max_jets = span_attrs.get("max jets")
        specs.total_jet_count = parse_int(max_jets)

        # --- Filtration ---
        # Not typically listed as area on Bullfrog; leave None

        # --- Heater ---
        # Not typically listed on dealer page; leave None

        # Log extraction results
        extracted = []
        missing = []
        for field_name in [
            "length_inches",
            "width_inches",
            "height_inches",
            "dry_weight_lbs",
            "filled_weight_lbs",
            "water_capacity_gallons",
            "seating_capacity",
            "total_jet_count",
            "pump_count",
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
    def _validate_bullfrog_model(soup: BeautifulSoup, expected_model: str) -> bool:
        """Validate the page contains the expected Bullfrog model.

        Checks both:
        1. The ``<span class="value">Model XX</span>`` field
        2. The ``<title>`` tag
        3. Any ``<h1>`` tag

        Returns True if the expected model name is found anywhere on the page.
        """
        search_term = expected_model.lower()

        # Check span.value containing "Model XX"
        for span in soup.select("span.value"):
            text = span.get_text().lower()
            if "model" in text and search_term in text:
                return True

        # Check title
        title_tag = soup.find("title")
        if title_tag and search_term in title_tag.get_text().lower():
            return True

        # Check h1 tags
        for h1 in soup.find_all("h1"):
            if search_term in h1.get_text().lower():
                return True

        return False

    @staticmethod
    def _extract_span_attributes(soup: BeautifulSoup) -> dict[str, str]:
        """Extract all label->value pairs from span.label / span.value elements.

        The page has containers with:
          ``<span class="label">Key:</span> <span class="value">Value</span>``

        Returns dict keyed by lowercase label (without trailing colon).
        Only returns the first occurrence of each label to avoid duplicates
        from repeated sections.
        """
        attrs: dict[str, str] = {}

        for label_span in soup.select("span.label"):
            key = clean_text(label_span.get_text()).rstrip(":").strip().lower()
            if not key:
                continue

            # Skip if already seen (page duplicates some span pairs)
            if key in attrs:
                continue

            # Find value span: next sibling or within same parent
            value_span = label_span.find_next_sibling("span", class_="value")
            if not value_span:
                parent = label_span.parent
                if parent:
                    value_span = parent.find("span", class_="value")

            if value_span:
                value = clean_text(value_span.get_text())
                if value:
                    attrs[key] = value

        return attrs

    @staticmethod
    def _extract_table_attributes(soup: BeautifulSoup) -> dict[str, str]:
        """Extract label->value pairs from spec table rows.

        Each table row has two ``<td>`` cells: label and value.

        Returns dict keyed by lowercase first-cell text.
        """
        attrs: dict[str, str] = {}

        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    key = clean_text(cells[0].get_text()).lower()
                    value = clean_text(cells[1].get_text())
                    if key and value:
                        attrs[key] = value

        return attrs
