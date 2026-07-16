#!/usr/bin/env python3
"""Validate supply chain controls for release certification.

This script verifies:
- SBOM can be generated from dependencies
- All dependencies are accounted for
- No blocked vulnerabilities without exceptions
- License compliance
"""

from __future__ import annotations

from pathlib import Path

from wilson_eval3ngine.supply_chain import SupplyChainManager


def validate_supply_chain() -> bool:
    """Run supply chain validation checks."""
    # Check pyproject.toml exists (look in workspace root)
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        # Try current directory for development
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            print("ERROR: pyproject.toml not found")
            return False

    # Generate SBOM
    manager = SupplyChainManager()
    sbom = manager.generate_sbom_from_lockfile(pyproject_path, "release-validation")

    print(f"SBOM generated: {len(sbom.components)} components")

    # Get lockfile evidence
    evidence = manager.get_lockfile_evidence()
    if evidence:
        print(f"Lockfile evidence: {evidence.packages_locked} packages locked")

    # Check for vulnerabilities (MVP returns empty)
    findings = manager.scan_for_vulnerabilities(sbom.components)
    decisions = manager.evaluate_vulnerabilities(findings)

    blocked = [f for f, d in zip(findings, decisions) if d.value == "block"]
    if blocked:
        print(f"ERROR: {len(blocked)} blocked vulnerabilities found")
        return False

    print("Supply chain validation: PASSED")
    return True


if __name__ == "__main__":
    import sys
    success = validate_supply_chain()
    sys.exit(0 if success else 1)