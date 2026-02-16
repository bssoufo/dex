"""Text parsing utilities for web-scraped spa specifications.

Handles the variety of formats found across manufacturer sites:
decimal inches, feet-inches, metric, fractional, with/without unit labels.

Every function accepts empty/None input gracefully and returns None on
failure -- no exceptions are raised for unparseable text.
"""

from __future__ import annotations

import re
import unicodedata


def clean_text(text: str) -> str:
    """Strip and normalize whitespace in *text*.

    - Strips leading/trailing whitespace.
    - Normalizes unicode whitespace characters (non-breaking spaces, etc.).
    - Collapses multiple consecutive spaces into one.

    Examples::

        >>> clean_text("  hello   world  ")
        'hello world'
        >>> clean_text("89\\u00a0inches")
        '89 inches'
    """
    if not text:
        return ""
    # Normalize unicode to NFC, then replace any unicode whitespace with plain space
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_dimension_inches(text: str | None) -> float | None:
    """Parse various dimension text formats into inches (float).

    Handled formats:
        - ``"89.0"`` or ``"89"`` -- plain number (assumed inches)
        - ``"7'10\\""`` or ``"7'-10\\""`` -- feet and inches
        - ``"2.39m"`` -- meters (converted to inches)
        - ``"239cm"`` -- centimeters (converted to inches)
        - ``"37 1/2"`` -- whole number plus fraction
        - ``"37.5 inches"``, ``"37.5 in"``, ``"37.5\\""`` -- with unit label

    Args:
        text: Raw dimension string from a web page.

    Returns:
        Dimension in inches as a float, or None if unparseable.

    Examples::

        >>> parse_dimension_inches("89.0")
        89.0
        >>> parse_dimension_inches("7'10\\"")
        94.0
        >>> parse_dimension_inches("2.39m")
        94.09...
        >>> parse_dimension_inches("")
        >>> parse_dimension_inches(None)
    """
    if not text:
        return None

    text = clean_text(text).replace(",", "")

    # Feet-inches: 7'10" or 7'-10" or 7'10 or 7\u203210\u2033
    ft_in = re.match(
        r"(\d+)['\u2032]-?\s*(\d+(?:\.\d+)?)\s*[\"″\u2033]?",
        text,
    )
    if ft_in:
        feet = int(ft_in.group(1))
        inches = float(ft_in.group(2))
        return feet * 12.0 + inches

    # Meters: 2.39m or 2.39 m
    m_match = re.match(r"(\d+\.?\d*)\s*m\b", text)
    if m_match:
        return float(m_match.group(1)) * 39.3701

    # Centimeters: 239cm or 239 cm
    cm_match = re.match(r"(\d+\.?\d*)\s*cm\b", text)
    if cm_match:
        return float(cm_match.group(1)) * 0.393701

    # Fractional: "37 1/2" -> 37.5
    frac_match = re.match(r"(\d+)\s+(\d+)/(\d+)", text)
    if frac_match:
        whole = int(frac_match.group(1))
        numerator = int(frac_match.group(2))
        denominator = int(frac_match.group(3))
        if denominator != 0:
            return whole + numerator / denominator
        return None

    # Plain number with optional unit label: "37.5 inches", "37.5 in", '37.5"'
    num_match = re.match(
        r"(\d+\.?\d*)\s*(?:inches|inch|in\b|[\"″\u2033]|'')?",
        text,
    )
    if num_match:
        value = float(num_match.group(1))
        if value > 0:
            return value

    return None


def parse_weight_lbs(text: str | None) -> float | None:
    """Parse weight text into pounds (float).

    Handled formats:
        - ``"825 lbs"`` or ``"825 lbs."``
        - ``"825 pounds"``
        - ``"825"`` (plain number)
        - ``"1,250 lbs"`` (comma-separated)

    Args:
        text: Raw weight string from a web page.

    Returns:
        Weight in pounds as a float, or None if unparseable.

    Examples::

        >>> parse_weight_lbs("825 lbs")
        825.0
        >>> parse_weight_lbs("1,250 lbs")
        1250.0
        >>> parse_weight_lbs("")
    """
    if not text:
        return None

    text = clean_text(text).replace(",", "")

    num_match = re.search(r"(\d+\.?\d*)", text)
    if num_match:
        return float(num_match.group(1))

    return None


def parse_gallons(text: str | None) -> float | None:
    """Parse water capacity text into gallons (float).

    Takes the *first* number when a range is given.

    Handled formats:
        - ``"270 gallons"`` or ``"270 gal"`` or ``"270 gal."``
        - ``"270"`` (plain number)
        - ``"270-290 gallons"`` (range -- returns 270)

    Args:
        text: Raw capacity string from a web page.

    Returns:
        Capacity in gallons as a float, or None if unparseable.

    Examples::

        >>> parse_gallons("270 gallons")
        270.0
        >>> parse_gallons("270-290 gallons")
        270.0
        >>> parse_gallons("")
    """
    if not text:
        return None

    text = clean_text(text).replace(",", "")

    # Extract first number (handles ranges like "270-290")
    num_match = re.search(r"(\d+\.?\d*)", text)
    if num_match:
        return float(num_match.group(1))

    return None


def parse_int(text: str | None) -> int | None:
    """Extract the first integer from text.

    Handled formats:
        - ``"60"``
        - ``"60 jets"``
        - ``"7 seats"``

    Args:
        text: Raw text containing an integer.

    Returns:
        The first integer found, or None if none found.

    Examples::

        >>> parse_int("60 jets")
        60
        >>> parse_int("7 seats")
        7
        >>> parse_int("")
    """
    if not text:
        return None

    text = clean_text(text)

    num_match = re.search(r"(\d+)", text)
    if num_match:
        return int(num_match.group(1))

    return None


def parse_float(text: str | None) -> float | None:
    """Extract the first floating-point number from text.

    Handled formats:
        - ``"2.5 HP"``
        - ``"130.0"``
        - ``"5.5"``

    Args:
        text: Raw text containing a decimal number.

    Returns:
        The first float found, or None if none found.

    Examples::

        >>> parse_float("2.5 HP")
        2.5
        >>> parse_float("130.0")
        130.0
        >>> parse_float("")
    """
    if not text:
        return None

    text = clean_text(text).replace(",", "")

    num_match = re.search(r"(\d+\.?\d*)", text)
    if num_match:
        return float(num_match.group(1))

    return None
