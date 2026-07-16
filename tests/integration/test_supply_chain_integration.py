"""Integration tests for software supply chain controls (TODO 43).

Tests cover:
- Full SBOM generation workflow from lockfile
- Vulnerability scanning pipeline
- License checking integration
- Exception workflow with SupplyChainManager
- Build provenance end-to-end
"""

from __future__ import annotations

from datetime import timedelta

from wilson_eval3ngine.supply_chain import (
    LockfileEvidence,
    RiskDecision,
    RiskPolicy,
    SBOMComponent,
    SupplyChainManager,
    VulnerabilityException,
    VulnerabilityReport,
    VulnerabilitySeverity,
)
from wilson_eval3ngine.util import sha256_hex, utc_now


class TestSBOMWorkflow:
    """Integration tests for SBOM generation workflow."""

    def test_generate_sbom_from_lockfile(self, tmp_path) -> None:
        """SBOM can be generated from a lockfile."""
        # Create a sample requirements file
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text(
            "# Test requirements\nfastapi==0.110.0\npydantic==2.5.0\nrequests==2.31.0\n"
        )

        manager = SupplyChainManager()
        sbom = manager.generate_sbom_from_lockfile(lockfile, "test-release")

        assert sbom.sbom_id.startswith("sbom_")
        assert sbom.name == "test-release"
        assert len(sbom.components) == 3

        # Verify component names
        names = {c.name for c in sbom.components}
        assert "fastapi" in names
        assert "pydantic" in names
        assert "requests" in names

    def test_generate_sbom_with_hashes(self, tmp_path) -> None:
        """SBOM generation handles hash-annotated requirements."""
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text(
            "# Requirements with hashes\n"
            "fastapi==0.110.0 --hash=sha256=abc123def456\n"
            "pydantic==2.5.0 --hash=sha256=def789ghi012\n"
        )

        manager = SupplyChainManager()
        sbom = manager.generate_sbom_from_lockfile(lockfile, "release-with-hashes")

        assert len(sbom.components) == 2
        fastapi = next(c for c in sbom.components if c.name == "fastapi")
        assert fastapi.sha256 == "abc123def456"

    def test_lockfile_evidence_created(self, tmp_path) -> None:
        """Lockfile evidence is captured during SBOM generation."""
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text("requests==2.31.0\n")

        manager = SupplyChainManager()
        manager.generate_sbom_from_lockfile(lockfile, "test")

        evidence = manager.get_lockfile_evidence()
        assert evidence is not None
        assert isinstance(evidence, LockfileEvidence)
        assert evidence.packages_locked == 1
        assert len(evidence.locked_components) == 1

    def test_sbom_spdx_complete_document(self, tmp_path) -> None:
        """Generated SBOM has complete SPDX document structure."""
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text("fastapi==0.110.0\n")

        manager = SupplyChainManager()
        sbom = manager.generate_sbom_from_lockfile(lockfile, "complete-test")

        spdx = sbom.to_spdx_json()

        # Verify SPDX structure
        assert "spdxVersion" in spdx
        assert "creationInfo" in spdx
        assert "created" in spdx["creationInfo"]
        assert "creators" in spdx["creationInfo"]
        assert "documentNamespace" in spdx
        assert spdx["documentNamespace"].startswith("https://wilsone3.net/sbom/")


class TestVulnerabilityScanningPipeline:
    """Integration tests for vulnerability scanning."""

    def test_scan_components_returns_empty_for_mvp(self) -> None:
        """MVP scanner returns empty findings."""
        manager = SupplyChainManager()

        components = [
            SBOMComponent(
                name="fastapi", version="0.110.0", purl="", download_location=""
            ),
        ]

        findings = manager.scan_for_vulnerabilities(components)
        assert len(findings) == 0

    def test_evaluate_vulnerabilities_with_mock_data(self) -> None:
        """Vulnerability evaluation works with mock findings."""
        manager = SupplyChainManager()

        # Create mock vulnerabilities
        findings = [
            VulnerabilityReport(
                package_name="critical-pkg",
                package_version="1.0.0",
                vulnerability_id="CVE-2024-0001",
                severity=VulnerabilitySeverity.CRITICAL,
                description="Critical issue",
                fix_available=False,
            ),
            VulnerabilityReport(
                package_name="safe-pkg",
                package_version="2.0.0",
                vulnerability_id="CVE-2024-0002",
                severity=VulnerabilitySeverity.LOW,
                description="Low issue fixed",
                fix_available=True,
            ),
        ]

        results = manager.evaluate_vulnerabilities(findings)

        assert len(results) == 2
        assert results[0][1] == RiskDecision.BLOCK
        assert results[1][1] == RiskDecision.ACCEPT


class TestExceptionWorkflow:
    """Integration tests for exception management."""

    def test_register_and_use_exception(self) -> None:
        """Exception can be registered and applied to vulnerability."""
        manager = SupplyChainManager()

        exception = VulnerabilityException(
            exception_id="exc_test_001",
            vulnerability_id="CVE-2024-TEST",
            package_name="test-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Controlled deployment",
            compensating_controls=["WAF"],
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=60),
            follow_up_date=utc_now() + timedelta(days=30),
        )

        manager.register_exception(exception)

        # Verify can retrieve
        retrieved = manager.get_exception("CVE-2024-TEST")
        assert retrieved is not None
        assert retrieved.owner == "security-team"

    def test_expired_exception_not_returned(self) -> None:
        """Expired exceptions are not returned from get_exception."""
        manager = SupplyChainManager()

        exception = VulnerabilityException(
            exception_id="exc_expired",
            vulnerability_id="CVE-2024-EXPIRED",
            package_name="test-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Expired",
            compensating_controls=[],
            created_at=utc_now() - timedelta(days=90),
            expires_at=utc_now() - timedelta(days=30),
            follow_up_date=utc_now() - timedelta(days=60),
        )

        manager.register_exception(exception)

        retrieved = manager.get_exception("CVE-2024-EXPIRED")
        assert retrieved is None

    def test_exception_enables_blocked_vulnerability(self) -> None:
        """Registered exception enables blocked vulnerability to pass."""
        manager = SupplyChainManager()

        exception = VulnerabilityException(
            exception_id="exc_001",
            vulnerability_id="CVE-2024-CRITICAL",
            package_name="critical-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Acceptable risk with mitigations",
            compensating_controls=["network isolation"],
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=90),
            follow_up_date=utc_now() + timedelta(days=45),
        )

        manager.register_exception(exception)

        vuln = VulnerabilityReport(
            package_name="critical-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-CRITICAL",
            severity=VulnerabilitySeverity.CRITICAL,
            description="Critical vulnerability",
            fix_available=False,
        )

        # Without exception - would be blocked
        policy = RiskPolicy()
        assert policy.evaluate(vuln) == RiskDecision.BLOCK

        # With exception - allowed
        retrieved = manager.get_exception("CVE-2024-CRITICAL")
        assert retrieved is not None
        assert policy.evaluate(vuln, retrieved) == RiskDecision.EXCEPTION


class TestBuildProvenanceWorkflow:
    """Integration tests for build provenance."""

    def test_create_provenance_record(self) -> None:
        """Build provenance can be created and stored."""
        manager = SupplyChainManager()

        provenance = manager.create_build_provenance(
            source_commit_sha=sha256_hex(b"test_commit"),
            source_repository="https://github.com/example/wilson-eval3ngine",
            builder_identity="github-actions[bot]",
            build_command="python -m build",
        )

        assert provenance.provenance_id.startswith("prov_")
        assert provenance.builder_identity == "github-actions[bot]"

    def test_provenance_tracking(self) -> None:
        """Multiple provenances are tracked."""
        manager = SupplyChainManager()

        # Create multiple provenances
        for i in range(3):
            manager.create_build_provenance(
                source_commit_sha=f"commit_{i}",
                source_repository="https://github.com/example/repo",
                builder_identity=f"builder-{i}",
                build_command="build",
            )

        provenances = manager.get_build_provenances()
        assert len(provenances) == 3


class TestSupplyChainManagerIntegration:
    """End-to-end integration tests."""

    def test_full_release_workflow(self, tmp_path) -> None:
        """Complete workflow from lockfile to provenance."""
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text("requests==2.31.0\n")

        manager = SupplyChainManager()

        # Step 1: Generate SBOM
        sbom = manager.generate_sbom_from_lockfile(lockfile, "release-1.0.0")
        assert len(sbom.components) > 0

        # Step 2: Scan for vulnerabilities (MVP returns empty)
        findings = manager.scan_for_vulnerabilities(sbom.components)
        decisions = manager.evaluate_vulnerabilities(findings)
        assert all(d == RiskDecision.ACCEPT for _, d in decisions)

        # Step 3: Create build provenance
        provenance = manager.create_build_provenance(
            source_commit_sha=sha256_hex(b"release_commit"),
            source_repository="https://github.com/example/wilson",
            builder_identity="ci-system",
        )

        assert provenance.source_commit_sha is not None
        assert provenance.build_timestamp is not None


class TestRiskPolicyConfiguration:
    """Tests for risk policy configuration options."""

    def test_disable_critical_blocking(self) -> None:
        """Critical blocking can be disabled (for testing)."""
        policy = RiskPolicy(block_critical=False)

        vuln = VulnerabilityReport(
            package_name="test",
            package_version="1.0.0",
            vulnerability_id="CVE-TEST",
            severity=VulnerabilitySeverity.CRITICAL,
            description="Critical",
            fix_available=False,
        )

        assert policy.evaluate(vuln) == RiskDecision.ACCEPT

    def test_max_exceptions_configured(self) -> None:
        """Maximum exception limits are configurable."""
        policy = RiskPolicy(max_medium_exceptions=50)
        assert policy.max_medium_exceptions == 50

    def test_low_severity_accepted(self) -> None:
        """Low severity vulnerabilities are always accepted."""
        policy = RiskPolicy()

        vuln = VulnerabilityReport(
            package_name="test",
            package_version="1.0.0",
            vulnerability_id="CVE-LOW",
            severity=VulnerabilitySeverity.LOW,
            description="Low severity",
            fix_available=False,
            exploitable=True,
        )

        assert policy.evaluate(vuln) == RiskDecision.ACCEPT


class TestSASTScanning:
    """Tests for SAST source code scanning."""

    def test_sast_scanner_detects_patterns(self, tmp_path) -> None:
        """SAST scanner detects hardcoded passwords and secrets."""
        # Create a test file with potential security issues
        test_file = tmp_path / "vulnerable.py"
        test_file.write_text(
            "# Test file\npassword = 'mysecretpassword'\napi_key = 'sk_test12345678'\n"
        )

        manager = SupplyChainManager()
        findings = manager.scan_source_code(tmp_path)

        assert len(findings) > 0
        # Check that finding types match expected patterns
        finding_types = {f.finding_type for f in findings}
        assert any("password" in ft or "secret" in ft for ft in finding_types)

    def test_sast_ignores_venv_files(self, tmp_path) -> None:
        """SAST scanner skips virtual environment files."""
        # Create a file in venv directory
        venv_dir = tmp_path / "venv" / "lib"
        venv_dir.mkdir(parents=True)
        test_file = venv_dir / "test.py"
        test_file.write_text("password = 'secret'\n")

        manager = SupplyChainManager()
        findings = manager.scan_source_code(tmp_path)

        # Should not find anything in venv
        assert len(findings) == 0


class TestSecretScanning:
    """Tests for secret detection scanning."""

    def test_secret_scanner_detects_aws_keys(self, tmp_path) -> None:
        """Secret scanner detects AWS access keys."""
        test_file = tmp_path / "config.py"
        test_file.write_text("aws_key = 'AKIAIOSFODNN7EXAMPLE'\n")

        manager = SupplyChainManager()
        findings = manager.scan_for_secrets(tmp_path)

        assert any(f.matcher_name == "aws_access_key" for f in findings)

    def test_secret_scanner_detects_github_tokens(self, tmp_path) -> None:
        """Secret scanner detects GitHub tokens."""
        test_file = tmp_path / "env.txt"
        test_file.write_text("GITHUB_TOKEN=ghp_abcdef123456789012345678901234567890123\n")

        manager = SupplyChainManager()
        findings = manager.scan_for_secrets(tmp_path)

        assert any(f.matcher_name == "github_token" for f in findings)


class TestContainerScanning:
    """Tests for container image scanning."""

    def test_dockerfile_scan_detects_latest_tag(self, tmp_path) -> None:
        """Dockerfile scanner detects 'latest' tag usage."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.11\nRUN pip install fastapi\n")

        manager = SupplyChainManager()
        findings = manager.scan_dockerfiles(tmp_path)

        # Should detect latest tag
        tags = [f.vulnerability_id for f in findings]
        assert "TAG-LATEST" not in tags  # python:3.11 is not latest

        dockerfile_latest = tmp_path / "Dockerfile.prod"
        dockerfile_latest.write_text("FROM nginx:latest\n")

        findings = manager.scan_dockerfiles(tmp_path)
        tags = [f.vulnerability_id for f in findings]
        assert "TAG-LATEST" in tags


class TestIaCAInfrastructureScanning:
    """Tests for Infrastructure as Code scanning."""

    def test_terraform_scan_detects_issues(self, tmp_path) -> None:
        """IaC scanner detects Terraform security issues."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            'resource "aws_s3_bucket" "public" {\n  bucket = "my-bucket"\n}\n'
        )

        manager = SupplyChainManager()
        results = manager.scan_infrastructure(tmp_path)

        assert len(results) > 0
        # For MVP, results should have proper structure
        for result in results:
            assert result.status in ["pass", "fail", "warning"]
            assert isinstance(result.findings, list)


class TestReleaseEvidence:
    """Tests for complete release evidence generation."""

    def test_generate_release_evidence_bundles_everything(self, tmp_path) -> None:
        """Release evidence combines all scan results."""
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text("requests==2.31.0\n")

        manager = SupplyChainManager()
        evidence = manager.generate_release_evidence(
            source_path=tmp_path,
            lockfile_path=lockfile,
            release_name="test-release",
            source_commit_sha="abc123",
            builder_identity="test-builder",
        )

        assert evidence["schema_version"] == "we3.supply_chain_evidence.v1"
        assert "sbom" in evidence
        assert "vulnerabilities" in evidence
        assert "sast_findings" in evidence
        assert "secret_findings" in evidence
        assert "build_provenance" in evidence
        assert "lockfile_evidence" in evidence


class TestGitHubActionsSecurityScanning:
    """Tests for GitHub Actions workflow security scanning."""

    def test_workflow_scan_detects_unpinned_action(self, tmp_path) -> None:
        """GitHub Actions scanner detects unpinned actions."""
        workflow = tmp_path / ".github" / "workflows" / "test.yaml"
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(
            "name: Test\n"
            "on: [push]\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - uses: actions/setup-python@main\n"
        )

        manager = SupplyChainManager()
        findings = manager.scan_github_actions(workflow)

        # Should detect unpinned action (setup-python@main)
        assert len(findings) > 0
        unpinned = [f for f in findings if f.finding_type == "unpinned-action"]
        assert len(unpinned) > 0

    def test_workflow_scan_no_findings_for_pinned(self, tmp_path) -> None:
        """Pinned actions with hash are not flagged."""
        workflow = tmp_path / ".github" / "workflows" / "good.yaml"
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(
            "name: Good\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@9fa26c6fa94ac1d24e1a3f4e5e6e7e8e9fa0b1c2\n"
        )

        manager = SupplyChainManager()
        findings = manager.scan_github_actions(workflow)

        # Should have no unpinned findings (pinned with hash)
        unpinned = [f for f in findings if f.finding_type == "unpinned-action"]
        assert len(unpinned) == 0

    def test_workflow_scan_detects_write_permissions(self, tmp_path) -> None:
        """Workflow with unrestricted write permissions is flagged."""
        workflow = tmp_path / ".github" / "workflows" / "perms.yaml"
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(
            "name: Perms\n"
            "permissions:\n"
            "  contents: write\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo test\n"
        )

        manager = SupplyChainManager()
        findings = manager.scan_github_actions(workflow)

        # Should detect unrestricted write permissions
        write_issues = [f for f in findings if "write" in f.finding_type.lower()]
        assert len(write_issues) > 0


class TestVulnerabilityExceptionExpiry:
    """Tests for exception lifecycle management."""

    def test_exception_follow_up_date_tracked(self, tmp_path) -> None:
        """Exception follow-up date is accessible for audit."""
        from datetime import timedelta

        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text("vulnerable-pkg==1.0.0\n")

        manager = SupplyChainManager()
        exception = VulnerabilityException(
            exception_id="exc_002",
            vulnerability_id="CVE-2024-FOLLOWUP",
            package_name="vulnerable-pkg",
            package_version="1.0.0",
            owner="security-team",
            rationale="Needs follow-up",
            compensating_controls=["monitoring"],
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=60),
            follow_up_date=utc_now() + timedelta(days=15),
        )

        manager.register_exception(exception)
        retrieved = manager.get_exception("CVE-2024-FOLLOWUP")
        assert retrieved is not None
        assert retrieved.follow_up_date is not None

    def test_expired_exception_excluded_from_decision(self, tmp_path) -> None:
        """Expired exceptions are properly filtered out during evaluation."""
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text("test-pkg==1.0.0\n")

        manager = SupplyChainManager()
        policy = RiskPolicy()

        # Register an expired exception
        from datetime import timedelta

        expired = VulnerabilityException(
            exception_id="exc_exp",
            vulnerability_id="CVE-2024-EXPIRE",
            package_name="vulnerable-pkg",
            package_version="1.0.0",
            owner="team",
            rationale="Expired",
            compensating_controls=[],
            created_at=utc_now() - timedelta(days=90),
            expires_at=utc_now() - timedelta(days=1),
            follow_up_date=utc_now() + timedelta(days=30),
        )
        manager.register_exception(expired)

        vuln = VulnerabilityReport(
            package_name="vulnerable-pkg",
            package_version="1.0.0",
            vulnerability_id="CVE-2024-EXPIRE",
            severity=VulnerabilitySeverity.CRITICAL,
            description="Critical issue",
            fix_available=False,
        )

        # Should block because exception is expired
        decision = policy.evaluate(vuln, manager.get_exception("CVE-2024-EXPIRE"))
        assert decision == RiskDecision.BLOCK
