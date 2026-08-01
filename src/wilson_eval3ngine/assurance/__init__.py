"""Deterministic repository and runtime assurance utilities.

The assurance package emits evidence that is safe to archive and compare. It
never includes secret values, absolute checkout paths, or volatile timestamps
in its identity hashes.
"""

from .inventory import InventoryResult, build_inventory, verify_inventory

__all__ = ["InventoryResult", "build_inventory", "verify_inventory"]
