"""Unit tests for software supply chain controls (TODO 43).

Tests cover:
- SBOM generation and SPDX format
- Vulnerability policy evaluation
- License compliance checking
- Exception management and expiry
- Lockfile parsing
- Build provenance generation
"""

from __future__ import annotations

from datetime import timedelta

from wilson_eval3ngine.supply_chain import (
    BuildProvenance,
    LicenseChecker,
    LicenseStatus,
    RiskDecision,
    RiskPolicy,
    SBOM,
    SBOMComponent,
    VulnerabilityException,
    VulnerabilityReport,
    VulnerabilitySeverity,
    VulnerabilityScanner,
)
from wilson_eval3ngine.util import sha256_hex, utc_now


class TestSBOMGeneration:
    """Tests for SBOM generation and SPDX format."""

    def test_sbom_creation(self) -> None:
        """SBOM can be created with basic info."""
        sbom = SBOM(
            sbom_id="sbom_test_001",
            name="test-sbom",
        )
        assert sbom.sbom_id == "sbom_test_001"
        assert sbom.name == "test-sbom"
        assert sbom.spdx_version == "SPDX-2.3"
        assert len(sbom.components) == 0

    def test_sbom_add_component(self) -> None:
        """Component can be added to SBOM."""
        sbom = SBOM(sbom_id="sbom_test", name="test")

        component = sbom.add_component(
            name="fastapi",
            version="0.110.0",
            purl="pkg:pypi/fastapi@0.110.0",
            download_location="https://pypi.org/project/fastapi/0.110.0/",
            sha256="abc123def456",
        )

        assert len(sbom.components) == 1
        assert component.name == "fastapi"
        assert component.version == "0.110.0"
        assert component.sha256 == "abc123def456"

    def test_sbom_spdx_format(self) -> None:
        """SBOM generates valid SPDX JSON format."""
        sbom = SBOM(sbom_id="sbom_test", name="test-sbom")

        sbom.add_component(
            name="pydantic",
            version="2.5.0",
            purl="pkg:pypi/pydantic@2.5.0",
            download_location="https://pypi.org/project/pydantic/2.5.0/",
        )

        spdx = sbom.to_spdx_json()

        assert spdx["spdxVersion"] == "SPDX-2.3"
        assert spdx["name"] == "test-sbom"
        assert "SPDXID" in spdx
        assert "packages" in spdx
        assert len(spdx["packages"]) == 1

    def test_sbom_spdx_package_has_required_fields(self) -> None:
        """SPDX package entries have required fields."""
        sbom = SBOM(sbom_id="sbom_test", name="test")

        sbom.add_component(
            name="requests",
            version="2.31.0",
            purl="pkg:pypi/requests@2.31.0",
            download_location="https://pypi.org/project/requests/2.31.0/",
            sha256="deadbeef",
        )

        spdx = sbom.to_spdx_json()
        pkg = spdx["packages"][0]

        assert "name" in pkg
        assert "SPDXID" in pkg
        assert "versionInfo" in pkg
        assert "downloadLocation" in pkg
        assert "checksums" in pkg


class TestVulnerabilityPolicy:
    """Tests for vulnerability risk policy evaluation."""

    def test_block_critical_vulnerability(self) -> None:
        """Critical vulnerabilities are blocked by default."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="vulnerable-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-1234",
            severity=VulnerabilitySeverity.CRITICAL,
            description="Critical security issue",
            fix_available=False,
            exploitable=True,
        )

        assert policy.evaluate(vuln) == RiskDecision.BLOCK

    def test_block_high_without_fix(self) -> None:
        """High severity vulnerabilities without fix are blocked."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="high-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-5678",
            severity=VulnerabilitySeverity.HIGH,
            description="High severity issue",
            fix_available=False,
        )

        assert policy.evaluate(vuln) == RiskDecision.BLOCK

    def test_allow_high_with_fix(self) -> None:
        """High severity vulnerabilities with available fix are allowed."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="fix-available-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-9999",
            severity=VulnerabilitySeverity.HIGH,
            description="Fixed in newer version",
            fix_available=True,
        )

        assert policy.evaluate(vuln) == RiskDecision.ACCEPT

    def test_exception_allows_vulnerability(self) -> None:
        """Valid exception allows a blocked vulnerability."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="critical-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-1234",
            severity=VulnerabilitySeverity.CRITICAL,
            description="Critical issue",
            fix_available=False,
        )

        exception = VulnerabilityException(
            exception_id="exc_001",
            vulnerability_id="CVE-2024-1234",
            package_name="critical-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Controlled deployment with mitigations",
            compensating_controls=["WAF", "runtime monitoring"],
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=30),
            follow_up_date=utc_now() + timedelta(days=15),
        )

        assert policy.evaluate(vuln, exception) == RiskDecision.EXCEPTION

    def test_expired_exception_ignored(self) -> None:
        """Expired exceptions are ignored and vulnerability is blocked."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="critical-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-1234",
            severity=VulnerabilitySeverity.CRITICAL,
            description="Critical issue",
            fix_available=False,
        )

        exception = VulnerabilityException(
            exception_id="exc_001",
            vulnerability_id="CVE-2024-1234",
            package_name="critical-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Expired",
            compensating_controls=[],
            created_at=utc_now() - timedelta(days=60),
            expires_at=utc_now() - timedelta(days=30),
            follow_up_date=utc_now() - timedelta(days=35),
        )

        assert policy.evaluate(vuln, exception) == RiskDecision.BLOCK

    def test_medium_exploitable_blocked(self) -> None:
        """Exploitable medium vulnerabilities are blocked."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="medium-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-7777",
            severity=VulnerabilitySeverity.MEDIUM,
            description="Exploitable medium issue",
            fix_available=False,
            exploitable=True,
        )

        assert policy.evaluate(vuln) == RiskDecision.BLOCK

    def test_medium_non_exploitable_allowed(self) -> None:
        """Non-exploitable medium vulnerabilities are allowed."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="safe-medium-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-7778",
            severity=VulnerabilitySeverity.MEDIUM,
            description="Not exploitable",
            fix_available=False,
            exploitable=False,
        )

        assert policy.evaluate(vuln) == RiskDecision.ACCEPT


class TestLicenseChecker:
    """Tests for license compliance checking."""

    def test_approved_license_default(self) -> None:
        """All packages default to approved for MVP."""
        checker = LicenseChecker()
        result = checker.check_package("fastapi", "0.110.0")
        assert result == LicenseStatus.APPROVED

    def test_license_cache(self) -> None:
        """License checks are cached."""
        checker = LicenseChecker()

        # First check
        checker.check_package("pkg", "1.0.0")

        # Should be cached
        assert "pkg@1.0.0" in checker._cache

    def test_check_multiple_components(self) -> None:
        """Can check license for multiple components."""
        checker = LicenseChecker()

        components = [
            SBOMComponent(
                name="fastapi",
                version="0.110.0",
                purl="pkg:pypi/fastapi",
                download_location="",
            ),
            SBOMComponent(
                name="pydantic",
                version="2.5.0",
                purl="pkg:pypi/pydantic",
                download_location="",
            ),
        ]

        results = checker.check_components(components)
        assert len(results) == 2
        assert all(status == LicenseStatus.APPROVED for _, status in results)


class TestVulnerabilityException:
    """Tests for vulnerability exception management."""

    def test_exception_not_expired(self) -> None:
        """New exception is not expired."""
        exc = VulnerabilityException(
            exception_id="exc_001",
            vulnerability_id="CVE-2024-1234",
            package_name="test-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Testing",
            compensating_controls=["WAF"],
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=30),
            follow_up_date=utc_now() + timedelta(days=15),
        )
        assert exc.is_expired() is False

    def test_exception_expired(self) -> None:
        """Expired exception returns expired status."""
        exc = VulnerabilityException(
            exception_id="exc_001",
            vulnerability_id="CVE-2024-1234",
            package_name="test-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Testing",
            compensating_controls=[],
            created_at=utc_now() - timedelta(days=60),
            expires_at=utc_now() - timedelta(days=30),
            follow_up_date=utc_now() - timedelta(days=45),
        )
        assert exc.is_expired() is True

    def test_exception_serialization(self) -> None:
        """Exception serializes to dictionary correctly."""
        exc = VulnerabilityException(
            exception_id="exc_001",
            vulnerability_id="CVE-2024-1234",
            package_name="test-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Test rationale",
            compensating_controls=["WAF", "monitoring"],
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=30),
            follow_up_date=utc_now() + timedelta(days=15),
        )

        d = exc.to_dict()
        assert d["exception_id"] == "exc_001"
        assert d["vulnerability_id"] == "CVE-2024-1234"
        assert d["owner"] == "security-team"
        assert d["compensating_controls"] == ["WAF", "monitoring"]


class TestVulnerabilityScanner:
    """Tests for vulnerability scanner base class."""

    def test_scanner_no_findings_by_default(self) -> None:
        """Base scanner returns no findings for MVP."""
        scanner = VulnerabilityScanner()
        findings = scanner.scan_package("some-package", "1.0.0")
        assert findings is None

    def test_scanner_scan_components(self) -> None:
        """Scanner can iterate over components."""
        scanner = VulnerabilityScanner()

        components = [
            SBOMComponent(name="pkg-a", version="1.0.0", purl="", download_location=""),
            SBOMComponent(name="pkg-b", version="2.0.0", purl="", download_location=""),
        ]

        findings = scanner.scan_components(components)
        assert len(findings) == 0


class TestBuildProvenance:
    """Tests for build provenance generation."""

    def test_create_provenance(self) -> None:
        """Build provenance can be created."""
        provenance = BuildProvenance(
            provenance_id="prov_001",
            build_timestamp=utc_now(),
            builder_identity="ci-system",
            source_commit_sha=sha256_hex(b"test commit"),
            source_repository="https://github.com/example/repo",
        )

        assert provenance.provenance_id == "prov_001"
        assert provenance.builder_identity == "ci-system"
        assert provenance.source_repository == "https://github.com/example/repo"

    def test_provenance_serialization(self) -> None:
        """Provenance serializes to dictionary."""
        provenance = BuildProvenance(
            provenance_id="prov_001",
            build_timestamp=utc_now(),
            builder_identity="builder",
            source_commit_sha="abc123",
            source_repository="https://github.com/test/repo",
            build_command="python -m build",
            build_environment={"CI": "true", "PYTHON_VERSION": "3.13"},
        )

        d = provenance.to_dict()
        assert d["builder_identity"] == "builder"
        assert d["build_command"] == "python -m build"
        assert d["build_environment"]["CI"] == "true"
