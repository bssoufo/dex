"""Hot Spring Highlife Collection HTML parser.

Parses dealer pages from hotspringhottubs.com to extract spa specifications
into the ScrapedSpecs intermediate format.

Page structure (verified 2026-02-16):
  - Spec rows are ``<div class="et_pb_row">`` with two columns:
    - 1/3 column: ``<p><strong>Label:</strong></p>``
    - 2/3 column: ``<p>value text</p>``
  - Values are in ``<div class="et_pb_text_inner">`` containers.
  - Dimensions use smart-quote unicode entities for feet/inches.
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


class HotSpringParser(ManufacturerParser):
    """Parser for Hot Spring Highlife dealer pages on hotspringhottubs.com.

    The dealer site uses a Divi (et_pb) layout where each spec is a two-column
    row. The first column contains the label in a ``<strong>`` tag, and the
    second column contains the value as paragraph text.
    """

    def parse_model_page(self, html: str, model_name: str) -> ScrapedSpecs:
        """Parse a Hot Spring model dealer page into ScrapedSpecs.

        Args:
            html: Raw HTML of the dealer page.
            model_name: Expected model name (e.g. "Grandee", "Envoy").

        Returns:
            ScrapedSpecs with extracted fields; unparseable fields stay None.
        """
        self.validate_model_name(html, model_name)

        soup = BeautifulSoup(html, "lxml")
        specs = ScrapedSpecs()

        # Collect all label->value pairs from the Divi row layout
        attrs = self._extract_all_attributes(soup)

        if not attrs:
            logger.warning(
                "No spec attributes found on Hot Spring page for '%s'", model_name
            )
            return specs

        logger.info(
            "Found %d spec attributes for Hot Spring '%s': %s",
            len(attrs),
            model_name,
            list(attrs.keys()),
        )

        # --- Dimensions ---
        dims_text = attrs.get("dimensions")
        if dims_text:
            l, w, h = self._parse_dimensions(dims_text)
            specs.length_inches = l
            specs.width_inches = w
            specs.height_inches = h

        # --- Water capacity ---
        specs.water_capacity_gallons = parse_gallons(attrs.get("water capacity"))

        # --- Weight ---
        weight_text = attrs.get("weight") or ""
        specs.dry_weight_lbs, specs.filled_weight_lbs = self._parse_weights(
            weight_text
        )

        # --- Seating ---
        specs.seating_capacity = parse_int(attrs.get("seating capacity"))

        # --- Jets ---
        jets_text = attrs.get("jets") or ""
        specs.total_jet_count = self._parse_total_jets(jets_text)

        # --- Pump count ---
        pump_count = 0
        for key in attrs:
            if key.startswith("jet pump"):
                pump_count += 1
        if pump_count > 0:
            specs.pump_count = pump_count

        # --- Filtration ---
        filtration_text = attrs.get("effective filtration area") or ""
        specs.filtration_area_sqft = self._parse_filtration_area(filtration_text)

        # --- Electrical (from Control System field) ---
        control_text = attrs.get("control system") or ""
        specs.electrical_volts, specs.electrical_amps = self._parse_electrical(
            control_text
        )

        # --- Heater ---
        heater_text = attrs.get("heater") or ""
        specs.heater_wattage = self._parse_heater_wattage(heater_text)

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
            "filtration_area_sqft",
            "electrical_volts",
            "electrical_amps",
            "heater_wattage",
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
        """Gather all label->value pairs from the Divi two-column row layout.

        Each row has:
          - Column 1 (1/3): ``<div class="et_pb_text_inner"><p><strong>Label:</strong></p></div>``
          - Column 2 (2/3): ``<div class="et_pb_text_inner"><p>value</p></div>``

        Returns a dict keyed by lowercase label (without trailing colon).
        """
        attrs: dict[str, str] = {}

        # Find all et_pb_row elements containing spec data
        rows = soup.select("div.et_pb_row")
        for row in rows:
            columns = row.select("div.et_pb_column")
            if len(columns) < 2:
                continue

            # Look for a <strong> label in the first column
            label_col = columns[0]
            value_col = columns[1]

            strong_tag = label_col.find("strong")
            if not strong_tag:
                continue

            label = clean_text(strong_tag.get_text()).rstrip(":").strip().lower()
            if not label:
                continue

            # Get value text from the second column's text_inner div
            value_div = value_col.select_one("div.et_pb_text_inner")
            if not value_div:
                continue

            value = clean_text(value_div.get_text())
            if value:
                attrs[label] = value

        return attrs

    @staticmethod
    def _parse_dimensions(text: str) -> tuple[float | None, float | None, float | None]:
        """Parse Hot Spring dimension text into (length, width, height) in inches.

        Input formats seen:
            - ``"8'4 x 7'7\" x 38\""`` (feet-inches with unicode smart quotes)
            - ``"8\\u20174 x 7\\u20177\\u2033 x 38\\u2033"`` (actual unicode)
            - with metric suffix: "2.54m x 2.31m x .97m"

        Returns tuple of (length_inches, width_inches, height_inches).
        """
        if not text:
            return None, None, None

        # Normalize unicode quotes
        text = text.replace("\u2032", "'").replace("\u2033", '"')
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')

        # Split on " x " to get individual dimension strings
        parts = re.split(r"\s*x\s*", text, flags=re.IGNORECASE)
        if len(parts) < 3:
            return None, None, None

        # Parse each part -- take only the first measurement (imperial, skip metric)
        dims: list[float | None] = []
        for part in parts[:3]:
            # Strip metric portion after space+digit+m pattern
            # e.g. "8'4 x 7'7\" x 38\" 2.54m x 2.31m x .97m"
            # We split before metric at the first digit followed by decimal+m
            part = part.strip()

            # Try feet-inches pattern: N'N or N'N"
            ft_in = re.match(
                r"(\d+)['\u2032]\s*(\d+(?:\.\d+)?)\s*[\"″\u2033]?", part
            )
            if ft_in:
                feet = int(ft_in.group(1))
                inches = float(ft_in.group(2))
                dims.append(feet * 12.0 + inches)
                continue

            # Plain inches: NN" or NN
            inch_match = re.match(r"(\d+\.?\d*)\s*[\"″\u2033]?", part)
            if inch_match:
                val = float(inch_match.group(1))
                if val > 0:
                    dims.append(val)
                    continue

            dims.append(None)

        # Hot Spring lists as L x W x H
        length = dims[0] if len(dims) > 0 else None
        width = dims[1] if len(dims) > 1 else None
        height = dims[2] if len(dims) > 2 else None

        return length, width, height

    @staticmethod
    def _parse_weights(text: str) -> tuple[float | None, float | None]:
        """Parse weight text into (dry_weight_lbs, filled_weight_lbs).

        Example: "1,060 lbs./480 kg dry 6,040 lbs./2,740 kg filled*"
        """
        dry: float | None = None
        filled: float | None = None

        if not text:
            return dry, filled

        # Look for "N lbs" before "dry"
        dry_match = re.search(
            r"([\d,]+(?:\.\d+)?)\s*lbs?\.?\s*/?\s*[\d,]*\s*kg\s*dry", text, re.IGNORECASE
        )
        if dry_match:
            dry = parse_weight_lbs(dry_match.group(1))

        # Look for "N lbs" before "filled"
        filled_match = re.search(
            r"([\d,]+(?:\.\d+)?)\s*lbs?\.?\s*/?\s*[\d,]*\s*kg\s*filled",
            text,
            re.IGNORECASE,
        )
        if filled_match:
            filled = parse_weight_lbs(filled_match.group(1))

        # Fallback: if only one number found without dry/filled labels
        if dry is None and filled is None:
            nums = re.findall(r"([\d,]+(?:\.\d+)?)\s*lbs?", text, re.IGNORECASE)
            if len(nums) >= 2:
                dry = parse_weight_lbs(nums[0])
                filled = parse_weight_lbs(nums[1])
            elif len(nums) == 1:
                dry = parse_weight_lbs(nums[0])

        return dry, filled

    @staticmethod
    def _parse_total_jets(text: str) -> int | None:
        """Parse total jet count from jets text.

        Two formats exist across Hot Spring models:

        Format A (total first):
            "43, 2 Moto-Massage DX jets (2), 2 SoothingStream jets, ..."
            First number is the standalone total, followed by breakdown.

        Format B (breakdown only):
            "1 Moto-Massage DX jet (2), 2 SoothingStream jets, 3 JetStream jets, ..."
            No standalone total; sum all leading numbers from each segment.

        Detection: If text starts with ``N,`` where N is followed by comma
        and then another number + text, it is Format A. Otherwise, Format B.
        """
        if not text:
            return None

        text = text.strip()

        # Format A: standalone total before breakdown
        # e.g. "43, 2 Moto-Massage..."  -- total is 43
        format_a = re.match(r"^(\d+)\s*,\s*\d+\s+[A-Z]", text)
        if format_a:
            return int(format_a.group(1))

        # Format B: sum individual counts from comma-separated segments
        # e.g. "1 Moto-Massage DX jet (2), 2 SoothingStream jets, ..."
        total = 0
        segments = text.split(",")
        for segment in segments:
            segment = segment.strip()
            num_match = re.match(r"(\d+)\s+", segment)
            if num_match:
                total += int(num_match.group(1))

        return total if total > 0 else None

    @staticmethod
    def _parse_filtration_area(text: str) -> float | None:
        """Parse filtration area from text.

        Example: "325 sq. ft., top loading Tri-X filters ..."
        """
        if not text:
            return None

        match = re.search(r"(\d+\.?\d*)\s*sq\.?\s*ft", text, re.IGNORECASE)
        if match:
            return float(match.group(1))

        return None

    @staticmethod
    def _parse_electrical(text: str) -> tuple[int | None, int | None]:
        """Parse electrical specs from control system text.

        Example: "IQ 2020 with wireless remote control 230v/50amp, 60Hz, ..."
        """
        if not text:
            return None, None

        volts: int | None = None
        amps: int | None = None

        volts_match = re.search(r"(\d+)\s*v(?:olt)?", text, re.IGNORECASE)
        if volts_match:
            v = int(volts_match.group(1))
            # Only accept plausible spa voltages (110-240 range)
            if 100 <= v <= 250:
                volts = v

        amps_match = re.search(r"(\d+)\s*amp", text, re.IGNORECASE)
        if amps_match:
            amps = int(amps_match.group(1))

        return volts, amps

    @staticmethod
    def _parse_heater_wattage(text: str) -> int | None:
        """Parse heater wattage from heater text.

        Example: "No-Fault , 4000w/230v"
        """
        if not text:
            return None

        match = re.search(r"(\d+)\s*w(?:att)?", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return None
