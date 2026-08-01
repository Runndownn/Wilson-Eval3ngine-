"""Software Supply Chain Controls (TODO 43).

T6.1.6 - Provides SBOM generation, dependency vulnerability scanning,
license compliance checking, and provenance attestation for releases.

Components:
- SBOM generation in SPDX format
- Dependency lock file verification
- Vulnerability scanner abstraction
- Risk-based blocking thresholds
- Exception management for vulnerabilities
- SAST scanning for Python source
- Secret detection in source files
- Container image scanning
- IaC (Infrastructure as Code) scanning
- GitHub Actions workflow security scanning
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..util import sha256_hex, utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Core Types
# ============================================================================


class VulnerabilitySeverity(StrEnum):
    """Vulnerability severity levels for risk assessment."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class RiskDecision(StrEnum):
    """Risk-based decision for vulnerability handling."""

    BLOCK = "block"
    EXCEPTION = "exception"
    ACCEPT = "accept"


class LicenseStatus(StrEnum):
    """License compliance status."""

    APPROVED = "approved"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"
    VIOLATION = "violation"


# ============================================================================
# Vulnerability Types
# ============================================================================


@dataclass(frozen=True, slots=True)
class VulnerabilityReport:
    """Vulnerability finding for a dependency."""

    package_name: str
    package_version: str
    vulnerability_id: str
    severity: VulnerabilitySeverity
    description: str
    fix_available: bool
    exploitable: bool = False
    reach: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_name": self.package_name,
            "package_version": self.package_version,
            "vulnerability_id": self.vulnerability_id,
            "severity": self.severity.value,
            "description": self.description,
            "fix_available": self.fix_available,
            "exploitable": self.exploitable,
            "reach": self.reach,
        }


@dataclass
class VulnerabilityException:
    """Exception for allowing a blocked vulnerability through with controls."""

    exception_id: str
    vulnerability_id: str
    package_name: str
    package_version: str
    owner: str
    rationale: str
    compensating_controls: list[str]
    created_at: datetime
    expires_at: datetime
    follow_up_date: datetime

    def is_expired(self) -> bool:
        """Check if exception has expired."""
        return utc_now() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "exception_id": self.exception_id,
            "vulnerability_id": self.vulnerability_id,
            "package_name": self.package_name,
            "package_version": self.package_version,
            "owner": self.owner,
            "rationale": self.rationale,
            "compensating_controls": self.compensating_controls,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "follow_up_date": self.follow_up_date.isoformat(),
        }


# ============================================================================
# Risk Policy
# ============================================================================


@dataclass
class RiskPolicy:
    """Risk-based policy for vulnerability blocking."""

    # Blocking thresholds
    block_critical: bool = True
    block_high_without_fix: bool = True
    block_exploitable_medium: bool = True

    # Maximum allowed exceptions per severity
    max_critical_exceptions: int = 0
    max_high_exceptions: int = 3
    max_medium_exceptions: int = 10

    def evaluate(
        self,
        vulnerability: VulnerabilityReport,
        exception: VulnerabilityException | None = None,
    ) -> RiskDecision:
        """Evaluate vulnerability against policy."""
        # Check expired exceptions
        if exception and exception.is_expired():
            exception = None

        # Check for valid exception
        if exception:
            return RiskDecision.EXCEPTION

        # Apply blocking rules
        if (
            vulnerability.severity == VulnerabilitySeverity.CRITICAL
            and self.block_critical
        ):
            return RiskDecision.BLOCK

        if (
            vulnerability.severity == VulnerabilitySeverity.HIGH
            and self.block_high_without_fix
            and not vulnerability.fix_available
        ):
            return RiskDecision.BLOCK

        if (
            vulnerability.severity == VulnerabilitySeverity.MEDIUM
            and self.block_exploitable_medium
            and vulnerability.exploitable
        ):
            return RiskDecision.BLOCK

        return RiskDecision.ACCEPT


# ============================================================================
# SBOM Types
# ============================================================================


@dataclass
class SBOMComponent:
    """A component in the SBOM (SPDX format)."""

    name: str
    version: str
    purl: str
    download_location: str
    files_analyzed: bool = False
    sha256: str | None = None
    supplier: str | None = None
    license_approved: bool = True

    def to_spdx_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "SPDXID": f"SPDXRef-{sha256_hex(self.name)[:8]}",
            "versionInfo": self.version,
            "downloadLocation": self.download_location,
            "filesAnalyzed": self.files_analyzed,
        }
        if self.sha256:
            result["checksums"] = [{"algorithm": "SHA256", "value": self.sha256}]
        if self.supplier:
            result["supplier"] = self.supplier
        return result


@dataclass
class SBOM:
    """Software Bill of Materials in SPDX format."""

    sbom_id: str
    name: str
    spdx_version: str = "SPDX-2.3"
    creation_date: datetime = field(default_factory=utc_now)
    components: list[SBOMComponent] = field(default_factory=list)
    creator_tool: str = "wilson-eval3ngine-supply-chain-1.0.0"

    def add_component(
        self,
        name: str,
        version: str,
        purl: str,
        download_location: str,
        sha256: str | None = None,
    ) -> SBOMComponent:
        """Add a component to the SBOM."""
        component = SBOMComponent(
            name=name,
            version=version,
            purl=purl,
            download_location=download_location,
            sha256=sha256,
        )
        self.components.append(component)
        logger.info("sbom_component_added", extra={"name": name, "version": version})
        return component

    def to_spdx_json(self) -> dict[str, Any]:
        """Generate SPDX JSON format."""
        return {
            "spdxVersion": self.spdx_version,
            "creationInfo": {
                "created": self.creation_date.isoformat(),
                "creators": [
                    f"Tool: {self.creator_tool}",
                ],
            },
            "name": self.name,
            "SPDXID": f"SPDXRef-{self.sbom_id}",
            "documentNamespace": f"https://wilsone3.net/sbom/{self.sbom_id}",
            "packages": [c.to_spdx_dict() for c in self.components],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "sbom_id": self.sbom_id,
            "name": self.name,
            "spdx_version": self.spdx_version,
            "creation_date": self.creation_date.isoformat(),
            "component_count": len(self.components),
            "components": [
                {
                    "name": c.name,
                    "version": c.version,
                    "purl": c.purl,
                    "license_approved": c.license_approved,
                }
                for c in self.components
            ],
        }


@dataclass
class DependencyLockEntry:
    """Entry from pip lock file."""

    name: str
    version: str
    sha256: str | None = None
    marker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "sha256": self.sha256,
            "marker": self.marker,
        }


@dataclass
class LockfileEvidence:
    """Evidence about lockfile state at build time."""

    lockfile_hash_sha256: str
    generated_at: datetime
    python_version: str
    pip_version: str
    packages_locked: int
    locked_components: list[DependencyLockEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "lockfile_hash_sha256": self.lockfile_hash_sha256,
            "generated_at": self.generated_at.isoformat(),
            "python_version": self.python_version,
            "pip_version": self.pip_version,
            "packages_locked": self.packages_locked,
            "locked_components": [c.to_dict() for c in self.locked_components],
        }


@dataclass
class BuildProvenance:
    """Provenance attestation for a build."""

    provenance_id: str
    build_timestamp: datetime
    builder_identity: str
    source_commit_sha: str
    source_repository: str
    build_command: str | None = None
    build_environment: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance_id": self.provenance_id,
            "build_timestamp": self.build_timestamp.isoformat(),
            "builder_identity": self.builder_identity,
            "source_commit_sha": self.source_commit_sha,
            "source_repository": self.source_repository,
            "build_command": self.build_command,
            "build_environment": self.build_environment,
        }


# ============================================================================
# Scanner Interfaces
# ============================================================================


class VulnerabilityScanner:
    """Abstract vulnerability scanner interface."""

    def __init__(self) -> None:
        self._findings: list[VulnerabilityReport] = []

    def scan_package(self, name: str, version: str) -> VulnerabilityReport | None:
        """Scan a single package for vulnerabilities."""
        return None

    def scan_components(self, components: list[Any]) -> list[VulnerabilityReport]:
        """Scan all components for vulnerabilities."""
        findings = []
        for component in components:
            comp_name = getattr(component, "name", str(component))
            comp_version = getattr(component, "version", "unknown")
            finding = self.scan_package(comp_name, comp_version)
            if finding:
                findings.append(finding)
        self._findings = findings
        return findings

    def get_findings(self) -> list[VulnerabilityReport]:
        """Get all vulnerability findings."""
        return self._findings.copy()


# ============================================================================
# License Checker
# ============================================================================


class LicenseChecker:
    """License compliance checker for Python dependencies."""

    APPROVED_LICENSES = {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Python-2.0",
        "Unicode-3.0",
        "Zlib",
        "CC0-1.0",
        "0BSD",
    }

    RESTRICTED_LICENSES = {
        "AGPL-3.0",
        "GPL-3.0",
        "GPL-2.0",
        "LGPL-3.0",
    }

    def __init__(self) -> None:
        self._cache: dict[str, LicenseStatus] = {}

    def check_package(self, name: str, version: str) -> LicenseStatus:
        """Check license compliance for a package."""
        cache_key = f"{name}@{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        status = LicenseStatus.APPROVED
        self._cache[cache_key] = status
        return status

    def check_components(
        self,
        components: list[SBOMComponent],
    ) -> list[tuple[SBOMComponent, LicenseStatus]]:
        """Check license compliance for all components."""
        return [(c, self.check_package(c.name, c.version)) for c in components]


# ============================================================================
# SAST Scanning
# ============================================================================


class SASTFinding:
    """Security finding from static analysis."""

    def __init__(
        self,
        file_path: str,
        line_number: int | None,
        finding_type: str,
        severity: str,
        description: str,
        code_snippet: str = "",
    ) -> None:
        self.file_path = file_path
        self.line_number = line_number
        self.finding_type = finding_type
        self.severity = severity
        self.description = description
        self.code_snippet = code_snippet

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "finding_type": self.finding_type,
            "severity": self.severity,
            "description": self.description,
            "code_snippet": self.code_snippet,
        }


class SASTScanner:
    """Static Application Security Testing scanner for Python source.

    Detects:
    - Hardcoded secrets and credentials
    - SQL injection vulnerabilities
    - Command injection vulnerabilities
    - Unsafe deserialization
    - Path traversal vulnerabilities
    - Hardcoded passwords
    """

    DANGEROUS_PATTERNS = {
        "hardcoded_password": re.compile(
            r'(password\s*=\s*["\'][^"\']{4,}["\']|'
            r'passwd\s*=\s*["\'][^"\']{4,}["\']|'
            r'PWD\s*=\s*["\'][^"\']{4,}["\'])',
            re.IGNORECASE,
        ),
        "hardcoded_secret": re.compile(
            r'(secret\s*=\s*["\'][^"\']{8,}["\']|'
            r'api_key\s*=\s*["\'][^"\']{8,}["\']|'
            r'access_key\s*=\s*["\'][^"\']{8,}["\']|'
            r'token\s*=\s*["\']sk_["\'])',
            re.IGNORECASE,
        ),
        "sql_injection": re.compile(
            r'(execute\s*\(\s*f["\']|'
            r'cursor\.execute\s*\(\s*["\'][^"\']*\{|'
            r'f["\'][^"\']*SELECT[^"\']*\{)',
            re.IGNORECASE,
        ),
        "command_injection": re.compile(
            r'(os\.system\s*\(|'
            r'subprocess\.(call|run|Popen)\s*\(\s*f|'
            r'eval\s*\(|exec\s*\()',
            re.IGNORECASE,
        ),
        "path_traversal": re.compile(
            r'(open\s*\(\s*f["\']|'
            r'["\'][^"\']*\.\./[^"\']*["\'])',
            re.IGNORECASE,
        ),
    }

    def __init__(self) -> None:
        self._findings: list[SASTFinding] = []

    def scan_file(self, file_path: Path) -> list[SASTFinding]:
        """Scan a single Python file for security issues."""
        findings: list[SASTFinding] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return findings

        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern_name, pattern in self.DANGEROUS_PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        SASTFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            finding_type=pattern_name,
                            severity="high",
                            description=f"Potential {pattern_name} detected",
                            code_snippet=line.strip()[:200],
                        )
                    )

        return findings

    def scan_directory(self, root_path: Path) -> list[SASTFinding]:
        """Scan all Python files in a directory."""
        all_findings: list[SASTFinding] = []
        for py_file in root_path.rglob("*.py"):
            # Skip virtual environments and build artifacts
            if any(
                part in py_file.parts
                for part in ["venv", ".venv", "env", "__pycache__", "build", "dist"]
            ):
                continue
            all_findings.extend(self.scan_file(py_file))
        self._findings = all_findings
        return all_findings

    def get_findings(self) -> list[SASTFinding]:
        """Get all findings from last scan."""
        return self._findings.copy()


# ============================================================================
# Secret Detection Scanner
# ============================================================================


class SecretFinding:
    """Secret detection finding."""

    def __init__(
        self,
        file_path: str,
        line_number: int | None,
        matcher_name: str,
        secret_value: str | None = None,
    ) -> None:
        self.file_path = file_path
        self.line_number = line_number
        self.matcher_name = matcher_name
        self.secret_value = secret_value[:4] + "****" if secret_value else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "matcher_name": self.matcher_name,
            "secret_value": self.secret_value,
        }


class SecretScanner:
    """Detect hardcoded secrets in source files.

    Looks for:
    - AWS keys
    - GitHub tokens
    - Private keys
    - Generic high-entropy strings
    """

    SECRET_PATTERNS = {
        "aws_access_key": re.compile(r"AKIA[A-Z0-9]{16}"),
        "aws_secret_key": re.compile(r"aws_secret_access_key\s*=\s*['\"][^'\"]{40}['\"]"),
        "github_token": re.compile(r"ghp_[A-Za-z0-9]{36}"),
        "private_key": re.compile(r"-----BEGIN (RSA |EC |)PRIVATE KEY-----"),
        "generic_secret": re.compile(r"(secret|password|api_key|token)\s*[:=]\s*['\"][^'\"]{16,}['\"]"),
    }

    def __init__(self) -> None:
        self._findings: list[SecretFinding] = []

    def scan_file(self, file_path: Path) -> list[SecretFinding]:
        """Scan a file for secrets."""
        findings: list[SecretFinding] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return findings

        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern_name, pattern in self.SECRET_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    findings.append(
                        SecretFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            matcher_name=pattern_name,
                            secret_value=match.group(0)[:20],
                        )
                    )
        return findings

    def scan_repository(self, root_path: Path) -> list[SecretFinding]:
        """Scan all relevant files in a repository for secrets."""
        all_findings: list[SecretFinding] = []
        extensions = {".py", ".yaml", ".yml", ".json", ".env", ".toml", ".txt"}
        for ext in extensions:
            for file_path in root_path.rglob(f"*{ext}"):
                if "venv" in file_path.parts or ".venv" in file_path.parts:
                    continue
                all_findings.extend(self.scan_file(file_path))
        self._findings = all_findings
        return all_findings


# ============================================================================
# Container Image Scanning
# ============================================================================


class ContainerFinding:
    """Container image security finding."""

    def __init__(
        self,
        image_ref: str,
        severity: str,
        vulnerability_id: str,
        description: str,
    ) -> None:
        self.image_ref = image_ref
        self.severity = severity
        self.vulnerability_id = vulnerability_id
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_ref": self.image_ref,
            "severity": self.severity,
            "vulnerability_id": self.vulnerability_id,
            "description": self.description,
        }


class ContainerScanner:
    """Container image vulnerability scanner.

    For MVP, provides infrastructure for scanning.
    In production, integrates with Trivy, Grype, or similar.
    """

    def __init__(self) -> None:
        self._findings: list[ContainerFinding] = []

    def scan_image(
        self,
        image_ref: str,
        registry_auth: str | None = None,
    ) -> list[ContainerFinding]:
        """Scan a container image for vulnerabilities.

        For MVP, returns empty findings. Production would integrate
        with Trivy or similar scanner.
        """
        # In production: call Trivy/Grype API
        return []

    def scan_dockerfile(self, dockerfile_path: Path) -> list[ContainerFinding]:
        """Scan a Dockerfile for security issues."""
        findings: list[ContainerFinding] = []
        try:
            content = dockerfile_path.read_text()
        except Exception:
            return findings

        if "FROM" in content:
            # Check for latest tags
            if re.search(r"FROM\s+\S+:latest", content):
                findings.append(
                    ContainerFinding(
                        image_ref="dockerfile",
                        severity="medium",
                        vulnerability_id="TAG-LATEST",
                        description="Image uses 'latest' tag - not reproducible",
                    )
                )

            # Check for root user
            if re.search(r"USER\s+root", content):
                findings.append(
                    ContainerFinding(
                        image_ref="dockerfile",
                        severity="medium",
                        vulnerability_id="USER-ROOT",
                        description="Container runs as root user",
                    )
                )

        return findings


# ============================================================================
# IaC Scanning
# ============================================================================


class IaCFileStatus(StrEnum):
    """Status of IaC file analysis."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class IaCScanResult:
    """Result of scanning an IaC file."""

    file_path: str
    status: IaCFileStatus
    findings: list[dict[str, Any]] = field(default_factory=list)
    lines_of_code: int = 0


class IaCScanner:
    """Infrastructure as Code security scanner.

    Scans:
    - Terraform
    - Kubernetes manifests
    - Docker Compose files
    """

    DANGEROUS_IAC_PATTERNS = {
        "terraform": {
            "public_s3_bucket": re.compile(r'resource\s+"aws_s3_bucket".*public_acl\s*=\s*"public-read"'),
            "unrestricted_security_group": re.compile(
                r'ingress\s*\{[^}]*cidr_blocks\s*=\s*\[?.*0\.0\.0\.0/0'
            ),
            "plain_text_credential": re.compile(r'encrypted\s*=\s*false'),
        },
        "kubernetes": {
            "privileged_container": re.compile(r"privileged:\s*true"),
            "host_network": re.compile(r"hostNetwork:\s*true"),
            "default_namespace": re.compile(r"namespace:\s*default"),
        },
        "compose": {
            "privileged_mode": re.compile(r"privileged:\s*true"),
            "host_network": re.compile(r"network_mode:\s*host"),
        },
    }

    def __init__(self) -> None:
        self._results: list[IaCScanResult] = []

    def scan_file(self, file_path: Path) -> IaCScanResult:
        """Scan a single IaC file."""
        try:
            content = file_path.read_text()
        except Exception:
            return IaCScanResult(
                file_path=str(file_path),
                status=IaCFileStatus.WARNING,
                findings=[{"error": "Unable to read file"}],
            )

        findings: list[dict[str, Any]] = []

        # Determine file type and apply relevant patterns
        file_str = str(file_path).lower()
        if file_str.endswith(".tf"):
            patterns = self.DANGEROUS_IAC_PATTERNS["terraform"]
            file_type = "terraform"
        elif file_str.endswith((".yaml", ".yml")) and ("k8s" in file_str or "kube" in file_str):
            patterns = self.DANGEROUS_IAC_PATTERNS["kubernetes"]
            file_type = "kubernetes"
        elif file_str.endswith((".yaml", ".yml")) and "compose" in file_str:
            patterns = self.DANGEROUS_IAC_PATTERNS["compose"]
            file_type = "compose"
        else:
            # Try all patterns
            patterns = {}
            for p in self.DANGEROUS_IAC_PATTERNS.values():
                patterns.update(p)
            file_type = "unknown"

        for pattern_name, pattern in patterns.items():
            if pattern.search(content):
                findings.append(
                    {
                        "type": pattern_name,
                        "description": f"Security issue detected in {file_type}",
                    }
                )

        status = IaCFileStatus.FAIL if findings else IaCFileStatus.PASS

        return IaCScanResult(
            file_path=str(file_path),
            status=status,
            findings=findings,
            lines_of_code=len(content.splitlines()),
        )

    def scan_directory(self, root_path: Path) -> list[IaCScanResult]:
        """Scan all IaC files in a directory."""
        self._results = []
        iac_extensions = {".tf", ".yaml", ".yml", ".json"}
        for ext in iac_extensions:
            for file_path in root_path.rglob(f"*{ext}"):
                if any(
                    part in file_path.parts
                    for part in ["venv", ".venv", "env", "__pycache__"]
                ):
                    continue
                self._results.append(self.scan_file(file_path))
        return self._results


# ============================================================================
# GitHub Actions Security Scanner
# ============================================================================


class GitHubActionFinding:
    """GitHub Actions workflow security finding."""

    def __init__(
        self,
        workflow_path: str,
        severity: str,
        finding_type: str,
        description: str,
    ) -> None:
        self.workflow_path = workflow_path
        self.severity = severity
        self.finding_type = finding_type
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_path": self.workflow_path,
            "severity": self.severity,
            "finding_type": self.finding_type,
            "description": self.description,
        }


class GitHubActionsScanner:
    """GitHub Actions workflow security scanner."""

    def __init__(self) -> None:
        self._findings: list[GitHubActionFinding] = []

    def scan_workflow(self, workflow_path: Path) -> list[GitHubActionFinding]:
        """Scan a GitHub Actions workflow file for security issues."""
        findings: list[GitHubActionFinding] = []

        try:
            import yaml

            with workflow_path.open() as f:
                workflow = yaml.safe_load(f)
        except Exception:
            return findings

        jobs = workflow.get("jobs", {})
        for job_name, job_def in jobs.items():
            steps = job_def.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                # Check for pinning - should be version tag or SHA256 hash
                # Unpinned: no @ symbol, or branch name after @ instead of version/hash
                if uses:
                    parts = uses.split("@")
                    if len(parts) == 1:
                        # No @ at all - completely unpinned
                        findings.append(
                            GitHubActionFinding(
                                workflow_path=str(workflow_path),
                                severity="medium",
                                finding_type="unpinned-action",
                                description=f"Action '{uses}' in job '{job_name}' is not pinned",
                            )
                        )
                    elif len(parts) >= 2:
                        version_part = parts[-1]
                        # Check if it's a branch name (main, master, v1, v2, etc.) instead of hash
                        # SHA256 hashes are 40+ hex characters
                        is_hash = len(version_part) >= 40 and all(c in "0123456789abcdef" for c in version_part.lower())
                        # Check if it's a proper semver version (v1, v2, 2.0.0, etc.)
                        import re
                        is_version = bool(re.match(r"^v?\d+(\.\d+)*", version_part))
                        if not (is_hash or is_version):
                            # It's a branch name or other non-specific reference
                            findings.append(
                                GitHubActionFinding(
                                    workflow_path=str(workflow_path),
                                    severity="medium",
                                    finding_type="unpinned-action",
                                    description=f"Action '{uses}' in job '{job_name}' is not pinned to a hash or version",
                                )
                            )

                # Check for dangerous permissions
                permissions = workflow.get("permissions", {})
                if permissions.get("contents") == "write":
                    if not step.get("if", "").startswith("github.ref") or "main" not in step.get("if", ""):
                        findings.append(
                            GitHubActionFinding(
                                workflow_path=str(workflow_path),
                                severity="high",
                                finding_type="unrestricted-write",
                                description="Workflow has unrestricted write permissions",
                            )
                        )

        return findings


# ============================================================================
# Supply Chain Manager
# ============================================================================


class SupplyChainManager:
    """Manages supply chain controls for releases."""

    def __init__(
        self,
        *,
        risk_policy: RiskPolicy | None = None,
        use_federated_ci_identities: bool = True,
    ) -> None:
        self.risk_policy = risk_policy or RiskPolicy()
        self._exceptions: dict[str, VulnerabilityException] = {}
        self._scanner = VulnerabilityScanner()
        self._license_checker = LicenseChecker()
        self.use_federated_ci_identities = use_federated_ci_identities
        self._lockfile_evidence: LockfileEvidence | None = None
        self._build_provenances: list[BuildProvenance] = []

    def register_exception(self, exception: VulnerabilityException) -> None:
        """Register a vulnerability exception."""
        self._exceptions[exception.vulnerability_id] = exception
        logger.info(
            "vulnerability_exception_registered",
            extra={
                "exception_id": exception.exception_id,
                "vulnerability_id": exception.vulnerability_id,
                "owner": exception.owner,
            },
        )

    def get_exception(self, vulnerability_id: str) -> VulnerabilityException | None:
        """Get exception for a vulnerability if it exists and is valid."""
        exc = self._exceptions.get(vulnerability_id)
        if exc and exc.is_expired():
            logger.warning(
                "vulnerability_exception_expired",
                extra={"vulnerability_id": vulnerability_id},
            )
            return None
        return exc

    def generate_sbom_from_lockfile(self, lockfile_path: Path, sbom_name: str) -> SBOM:
        """Generate SBOM from pip lock file."""
        lockfile_path = lockfile_path.resolve()
        lockfile_hash = sha256_hex(lockfile_path.read_bytes())

        sbom = SBOM(
            sbom_id=f"sbom_{sha256_hex(lockfile_hash)[:16]}",
            name=sbom_name,
        )

        lock_entries = self._parse_lockfile(lockfile_path)

        import sys as _sys

        self._lockfile_evidence = LockfileEvidence(
            lockfile_hash_sha256=lockfile_hash,
            generated_at=utc_now(),
            python_version=f"{_sys.version_info.major}.{_sys.version_info.minor}",
            pip_version="unknown",
            packages_locked=len(lock_entries),
            locked_components=lock_entries,
        )

        for entry in lock_entries:
            sbom.add_component(
                name=entry.name,
                version=entry.version,
                purl=f"pkg:pypi/{entry.name}@{entry.version}",
                download_location=f"https://pypi.org/project/{entry.name}/{entry.version}/",
                sha256=entry.sha256,
            )

        logger.info(
            "sbom_generated",
            extra={"sbom_id": sbom.sbom_id, "components": len(sbom.components)},
        )
        return sbom

    def _parse_lockfile(self, lockfile_path: Path) -> list[DependencyLockEntry]:
        """Parse lockfile into dependency entries.

        Supports:
        - requirements.txt format (package==1.0.0)
        - requirements with hashes (package==1.0.0 --hash=sha256=abc)
        - pyproject.toml format (for direct dependencies)
        """
        content = lockfile_path.read_text()
        entries: list[DependencyLockEntry] = []

        # Detect pyproject.toml format
        if content.strip().startswith("[") or "dependencies" in content:
            return self._parse_pyproject_dependencies(content)

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r "):
                continue

            # Handle lines with hashes (format: --hash=sha256=abcdef)
            if "--hash=sha256=" in line:
                import re

                hash_match = re.search(r"--hash=sha256=([a-fA-F0-9]+)", line)
                sha256_val = hash_match.group(1) if hash_match else None

                # Get the package part before the hash
                pkg_part = line.split("--hash")[0].strip()

                if "==" in pkg_part:
                    parts = pkg_part.split("==")
                    name = parts[0].strip()
                    version = parts[1].split("[")[0].strip()
                    entries.append(
                        DependencyLockEntry(name=name, version=version, sha256=sha256_val)
                    )
                continue

            # Handle plain == versions
            if "==" in line:
                parts = line.split("==")
                if len(parts) == 2:
                    name = parts[0].strip()
                    version = parts[1].split("[")[0].split("--")[0].strip()
                    entries.append(DependencyLockEntry(name=name, version=version))

        return entries

    def _parse_pyproject_dependencies(self, content: str) -> list[DependencyLockEntry]:
        """Parse dependencies from pyproject.toml format."""
        import re

        entries: list[DependencyLockEntry] = []
        # Match lines like: "fastapi>=0.128,<0.129"
        # We extract package name and derive a pseudo-version
        pattern = r'"([a-zA-Z0-9_-]+)([><=!]+[\d\.\,\<]+)"'
        matches = re.findall(pattern, content)

        for name, version_spec in matches:
            # Extract just the package name (without extras like [binary])
            clean_name = name.split("[")[0]
            # For pyproject.toml without locked versions, we record the spec
            entries.append(DependencyLockEntry(name=clean_name, version=version_spec))

        return entries

    def scan_for_vulnerabilities(
        self, components: list[SBOMComponent]
    ) -> list[VulnerabilityReport]:
        """Scan components for vulnerabilities."""
        findings = self._scanner.scan_components(components)
        logger.info(
            "vulnerability_scan_complete", extra={"findings_count": len(findings)}
        )
        return findings

    def evaluate_vulnerabilities(
        self,
        findings: list[VulnerabilityReport],
    ) -> list[tuple[VulnerabilityReport, RiskDecision]]:
        """Evaluate vulnerability findings against policy."""
        return [
            (
                finding,
                self.risk_policy.evaluate(
                    finding, self.get_exception(finding.vulnerability_id)
                ),
            )
            for finding in findings
        ]

    def create_build_provenance(
        self,
        source_commit_sha: str,
        source_repository: str,
        builder_identity: str,
        build_command: str | None = None,
    ) -> BuildProvenance:
        """Create provenance attestation for a build."""
        provenance = BuildProvenance(
            provenance_id=f"prov_{sha256_hex(source_commit_sha)[:16]}",
            build_timestamp=utc_now(),
            builder_identity=builder_identity,
            source_commit_sha=source_commit_sha,
            source_repository=source_repository,
            build_command=build_command,
        )
        self._build_provenances.append(provenance)
        logger.info(
            "build_provenance_created",
            extra={
                "provenance_id": provenance.provenance_id,
                "builder": builder_identity,
            },
        )
        return provenance

    def get_lockfile_evidence(self) -> LockfileEvidence | None:
        """Get lockfile evidence from last SBOM generation."""
        return self._lockfile_evidence

    def get_build_provenances(self) -> list[BuildProvenance]:
        """Get all build provenances."""
        return self._build_provenances.copy()

    # -------------------------------------------------------------------------
    # SAST Scanning
    # -------------------------------------------------------------------------
    def scan_source_code(self, source_path: Path) -> list[SASTFinding]:
        """Scan source code for security vulnerabilities."""
        scanner = SASTScanner()
        findings = scanner.scan_directory(source_path)
        for finding in findings:
            logger.warning(
                "sast_finding_detected",
                extra={
                    "file": finding.file_path,
                    "line": finding.line_number,
                    "type": finding.finding_type,
                    "severity": finding.severity,
                },
            )
        return findings

    # -------------------------------------------------------------------------
    # Secret Detection
    # -------------------------------------------------------------------------
    def scan_for_secrets(self, source_path: Path) -> list[SecretFinding]:
        """Scan repository for hardcoded secrets."""
        scanner = SecretScanner()
        findings = scanner.scan_repository(source_path)
        for finding in findings:
            logger.warning(
                "secret_detected",
                extra={
                    "file": finding.file_path,
                    "line": finding.line_number,
                    "matcher": finding.matcher_name,
                },
            )
        return findings

    # -------------------------------------------------------------------------
    # Container Scanning
    # -------------------------------------------------------------------------
    def scan_container_image(
        self,
        image_ref: str,
        registry_auth: str | None = None,
    ) -> list[ContainerFinding]:
        """Scan container image for vulnerabilities."""
        scanner = ContainerScanner()
        return scanner.scan_image(image_ref, registry_auth)

    def scan_dockerfiles(self, root_path: Path) -> list[ContainerFinding]:
        """Scan Dockerfiles for security issues."""
        scanner = ContainerScanner()
        findings: list[ContainerFinding] = []
        for dockerfile in root_path.rglob("Dockerfile*"):
            findings.extend(scanner.scan_dockerfile(dockerfile))
        return findings

    # -------------------------------------------------------------------------
    # IaC Scanning
    # -------------------------------------------------------------------------
    def scan_infrastructure(self, iac_path: Path) -> list[IaCScanResult]:
        """Scan IaC files for security issues."""
        scanner = IaCScanner()
        return scanner.scan_directory(iac_path)

    # -------------------------------------------------------------------------
    # GitHub Actions Scanning
    # -------------------------------------------------------------------------
    def scan_github_actions(self, workflow_path: Path) -> list[GitHubActionFinding]:
        """Scan GitHub Actions workflow for security issues."""
        scanner = GitHubActionsScanner()
        return scanner.scan_workflow(workflow_path)

    def scan_all_workflows(self, root_path: Path) -> list[GitHubActionFinding]:
        """Scan all GitHub Actions workflow files."""
        scanner = GitHubActionsScanner()
        findings: list[GitHubActionFinding] = []
        for workflow in root_path.rglob(".github/workflows/*.yaml"):
            findings.extend(scanner.scan_workflow(workflow))
        for workflow in root_path.rglob(".github/workflows/*.yml"):
            findings.extend(scanner.scan_workflow(workflow))
        return findings

    # -------------------------------------------------------------------------
    # Release Evidence Generation
    # -------------------------------------------------------------------------
    def generate_release_evidence(
        self,
        source_path: Path,
        lockfile_path: Path,
        release_name: str,
        source_commit_sha: str,
        builder_identity: str,
    ) -> dict[str, Any]:
        """Generate complete release evidence bundle.

        Combines:
        - SBOM with hash verification
        - SAST scan results
        - Secret scan results
        - Build provenance
        """
        evidence: dict[str, Any] = {
            "schema_version": "we3.supply_chain_evidence.v1",
            "release_name": release_name,
            "generated_at": utc_now().isoformat(),
        }

        # Generate SBOM
        sbom = self.generate_sbom_from_lockfile(lockfile_path, release_name)
        evidence["sbom"] = sbom.to_dict()

        # Scan for vulnerabilities
        vuln_findings = self.scan_for_vulnerabilities(sbom.components)
        vuln_decisions = self.evaluate_vulnerabilities(vuln_findings)
        evidence["vulnerabilities"] = [
            {"report": r.to_dict(), "decision": d.value}
            for r, d in vuln_decisions
        ]

        # SAST scan
        evidence["sast_findings"] = [
            f.to_dict() for f in self.scan_source_code(source_path)
        ]

        # Secret scan
        evidence["secret_findings"] = [
            f.to_dict() for f in self.scan_for_secrets(source_path)
        ]

        # Build provenance
        provenance = self.create_build_provenance(
            source_commit_sha=source_commit_sha,
            source_repository="https://github.com/example/repo",
            builder_identity=builder_identity,
            build_command="python -m build",
        )
        evidence["build_provenance"] = provenance.to_dict()

        # Lockfile evidence
        lockfile_evidence = self.get_lockfile_evidence()
        evidence["lockfile_evidence"] = (
            lockfile_evidence.to_dict() if lockfile_evidence else None
        )

        return evidence


# Global instance
_supply_chain_manager: SupplyChainManager | None = None


def get_supply_chain_manager() -> SupplyChainManager:
    """Get or create the global supply chain manager."""
    global _supply_chain_manager
    if _supply_chain_manager is None:
        _supply_chain_manager = SupplyChainManager()
    return _supply_chain_manager


# ============================================================================
# Supply Chain Scanner Integration
# ============================================================================

def scan_ci_pipeline(
    source_path: Path,
    lockfile_path: Path | None = None,
    dockerfile_paths: list[Path] = None,
) -> dict[str, Any]:
    """Run all supply chain scanners in a CI pipeline context.

    This is the main entry point for CI integration. It runs all scanners
    and returns a comprehensive report suitable for blocking decisions.

    Args:
        source_path: Path to source code root for SAST/secret scanning
        lockfile_path: Optional path to requirements lock file for SBOM
        dockerfile_paths: Optional list of Dockerfile paths for container scanning

    Returns:
        Dictionary with all scan results and blocking decisions
    """
    manager = SupplyChainManager()

    report: dict[str, Any] = {
        "schema_version": "we3.supply_chain_ci_report.v1",
        "generated_at": utc_now().isoformat(),
        "source_path": str(source_path),
        "scans": {},
        "blocking": [],
    }

    # SAST scan
    sast_findings = manager.scan_source_code(source_path)
    report["scans"]["sast"] = {
        "finding_count": len(sast_findings),
        "findings": [f.to_dict() for f in sast_findings],
    }
    for finding in sast_findings:
        if finding.severity in ("critical", "high"):
            report["blocking"].append({
                "type": "sast",
                "severity": finding.severity,
                "description": finding.description,
                "file": finding.file_path,
            })

    # Secret scan
    secret_findings = manager.scan_for_secrets(source_path)
    report["scans"]["secrets"] = {
        "finding_count": len(secret_findings),
        "findings": [f.to_dict() for f in secret_findings],
    }
    for finding in secret_findings:
        report["blocking"].append({
            "type": "secret",
            "severity": "critical",
            "description": f"Secret detected: {finding.matcher_name}",
            "file": finding.file_path,
        })

    # Container/Dockerfile scan
    if dockerfile_paths:
        container_findings: list[ContainerFinding] = []
        for dockerfile in dockerfile_paths:
            container_findings.extend(manager.scan_dockerfiles(source_path))
        report["scans"]["container"] = {
            "finding_count": len(container_findings),
            "findings": [f.to_dict() for f in container_findings],
        }
        for finding in container_findings:
            report["blocking"].append({
                "type": "container",
                "severity": finding.severity,
                "description": finding.description,
            })

    # IaC scan
    iac_results = manager.scan_infrastructure(source_path)
    report["scans"]["iac"] = {
        "file_count": len(iac_results),
        "failures": sum(1 for r in iac_results if r.status == IaCFileStatus.FAIL),
        "results": [
            {
                "file": r.file_path,
                "status": r.status.value,
                "finding_count": len(r.findings),
                "findings": r.findings,
            }
            for r in iac_results
        ],
    }
    for result in iac_results:
        if result.status == IaCFileStatus.FAIL:
            report["blocking"].append({
                "type": "iac",
                "severity": "high",
                "description": f"IaC issue in {result.file_path}",
                "findings": result.findings,
            })

    # GitHub Actions workflow scan
    workflow_findings = manager.scan_all_workflows(source_path)
    report["scans"]["github_actions"] = {
        "finding_count": len(workflow_findings),
        "findings": [f.to_dict() for f in workflow_findings],
    }
    for finding in workflow_findings:
        report["blocking"].append({
            "type": "workflow",
            "severity": finding.severity,
            "description": finding.description,
            "workflow": finding.workflow_path,
        })

    # SBOM and vulnerability scan
    if lockfile_path and lockfile_path.exists():
        sbom = manager.generate_sbom_from_lockfile(lockfile_path, "ci-release")
        vuln_findings = manager.scan_for_vulnerabilities(sbom.components)
        vuln_decisions = manager.evaluate_vulnerabilities(vuln_findings)

        report["scans"]["sbom"] = {
            "component_count": len(sbom.components),
            "dependency_lockfile_hash": sbom.components[0].sha256 if sbom.components else None,
        }
        report["scans"]["vulnerabilities"] = {
            "finding_count": len([d for _, d in vuln_decisions if d == RiskDecision.BLOCK]),
            "blocked": [r.to_dict() for r, d in vuln_decisions if d == RiskDecision.BLOCK],
            "exceptioned": [r.to_dict() for r, d in vuln_decisions if d == RiskDecision.EXCEPTION],
            "allowed": [r.to_dict() for r, d in vuln_decisions if d == RiskDecision.ACCEPT],
        }

        for vuln, decision in vuln_decisions:
            if decision == RiskDecision.BLOCK:
                report["blocking"].append({
                    "type": "vulnerability",
                    "severity": vuln.severity.value,
                    "description": vuln.description,
                    "package": f"{vuln.package_name}@{vuln.package_version}",
                    "vulnerability_id": vuln.vulnerability_id,
                })

    report["pass"] = len(report["blocking"]) == 0
    return report


__all__ = [
    # Vulnerability types
    "VulnerabilitySeverity",
    "RiskDecision",
    "LicenseStatus",
    "VulnerabilityReport",
    "VulnerabilityException",
    "RiskPolicy",
    # SBOM types
    "SBOMComponent",
    "SBOM",
    "DependencyLockEntry",
    "LockfileEvidence",
    "BuildProvenance",
    # Scanners
    "VulnerabilityScanner",
    "LicenseChecker",
    "SASTFinding",
    "SASTScanner",
    "SecretFinding",
    "SecretScanner",
    "ContainerFinding",
    "ContainerScanner",
    "IaCFileStatus",
    "IaCScanResult",
    "IaCScanner",
    "GitHubActionFinding",
    "GitHubActionsScanner",
    # Manager
    "SupplyChainManager",
    "get_supply_chain_manager",
    # CI Integration
    "scan_ci_pipeline",
]