"""Enumerated types for the Dex spa specification schema.

These enums represent known finite value sets shared across multiple
fields and models. Use StrEnum so values serialize as plain strings
in JSON while retaining type safety during validation.
"""

from __future__ import annotations

from enum import StrEnum


class Manufacturer(StrEnum):
    """Spa manufacturer supported in the Dex POC."""

    SUNDANCE = "sundance"
    HOT_SPRING = "hotspring"
    BULLFROG = "bullfrog"


class PumpSpeed(StrEnum):
    """Jet pump speed configuration."""

    ONE_SPEED = "1-speed"
    TWO_SPEED = "2-speed"
    VARIABLE = "variable"


class JetSystemType(StrEnum):
    """Jet installation architecture.

    Fixed jets are permanently mounted (Sundance, Hot Spring).
    Modular JetPak jets are swappable cartridges (Bullfrog).
    """

    FIXED = "fixed"
    MODULAR_JETPAK = "modular_jetpak"
