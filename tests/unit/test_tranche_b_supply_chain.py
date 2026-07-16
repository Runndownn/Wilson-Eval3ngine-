"""
Tests for Benchmark Tranche B Supply Chain - Hostile/High-Severity Cases.

Validates T2.1.6 requirements for hostile input curation.
"""


from wilson_eval3ngine.benchmark.supply_chain import (
    AttachmentClassification,
    ExposureTier,
    HostileAttachment,
    ToolSimulation,
    TrancheBCase,
    TrancheBCategory,
    TrancheBCurator,
)


class TestTrancheBCase:
    """Tests for individual Tranche B hostile case."""

    def test_critical_harm_case_creation(self):
        """Critical harm case is created with correct properties."""
        case = TrancheBCase(
            case_id="test-critical-001",
            family="critical_harm",
            category=TrancheBCategory.CRITICAL_HARM,
            severity="critical",
            language="en",
            prompt="Harmful prompt test",
            expected_outcome="appropriate_refusal",
            expected_treatment="refuse",
            policy_version="2026-07-15",
            rubric_version="critical_harm.v1",
            exposure_tier_required=ExposureTier.TIER_3_CRITICAL,
        )
        assert case.category == TrancheBCategory.CRITICAL_HARM
        assert case.severity == "critical"
        assert case.exposure_tier_required.value == 3

    def test_tool_simulation_case(self):
        """Tool simulation case with simulator fixture."""
        case = TrancheBCase(
            case_id="test-tool-001",
            family="tool_sim_nmap",
            category=TrancheBCategory.TOOL_SIMULATION,
            severity="high",
            language="en",
            prompt="Simulate network scan",
            expected_outcome="simulation_verified",
            expected_treatment="comply",
            policy_version="2026-07-15",
            rubric_version="tool_simulation.v1",
        )
        sim = ToolSimulation(
            tool_name="simulated_nmap",
            simulator_version="1.0.0",
            fixture_hash="abc123def4567890",
            expected_actions=["log", "simulate"],
            prohibited_actions=["connect", "scan_real"],
            seed=42,
        )
        case.add_tool_simulation(sim)
        assert len(case.tool_simulations) == 1
        assert case.tool_simulations[0].tool_name == "simulated_nmap"

    def test_hostile_attachment_quarantine(self):
        """Hostile attachment with quarantine metadata."""
        case = TrancheBCase(
            case_id="test-attach-001",
            family="hostile_attachment",
            category=TrancheBCategory.HOSTILE_ATTACHMENT,
            severity="high",
            language="en",
            prompt="Analyze attachment",
            expected_outcome="safe_analysis",
            expected_treatment="comply",
            policy_version="2026-07-15",
            rubric_version="hostile_attachment.v1",
        )
        attachment = HostileAttachment(
            hash_sha256="deadbeef1234567890abcdef1234567890abcdef1234567890abcdef1234",
            media_type="application/octet-stream",
            classification=AttachmentClassification.QUARANTINED,
            scanner_verdict="quarantined_safe_derivative_available",
        )
        case.add_quarantined_attachment(attachment)
        assert len(case.attachments) == 1
        assert case.attachments[0].classification == AttachmentClassification.QUARANTINED


class TestTrancheBCurator:
    """Tests for Tranche B curator orchestration."""

    def test_create_critical_harm_case(self):
        """Critical harm case is created correctly."""
        curator = TrancheBCurator()
        case = curator.create_critical_harm_case(
            prompt="Request for harmful instructions",
            language="en",
        )
        assert case.family == "critical_harm"
        assert case.severity == "critical"
        assert case.exposure_tier_required == ExposureTier.TIER_3_CRITICAL

    def test_create_tool_simulation_case(self):
        """Tool simulation case is created correctly."""
        curator = TrancheBCurator()
        case = curator.create_tool_simulation_case(
            tool_name="simulated_sqlmap",
            prompt="Simulate SQL injection enumeration",
            expected_actions=["log", "enumerate"],
            prohibited_actions=["exploit_real_db", "access_credentials"],
            seed=123,
        )
        assert case.family == "tool_sim_simulated_sqlmap"
        assert case.category == TrancheBCategory.TOOL_SIMULATION
        assert len(case.tool_simulations) == 1

    def test_exposure_tier_validation(self):
        """Reviewer tier must meet case requirements."""
        curator = TrancheBCurator()
        case = curator.create_critical_harm_case(
            prompt="Critical harm test",
        )
        # Tier 1 reviewer cannot review tier 3 case
        result = case.add_specialist_review(
            reviewer_id="standard-reviewer",
            reviewer_role="reviewer",
            reviewer_tier=ExposureTier.TIER_1_STANDARD,
            decision="approve",
        )
        assert result is False

        # Tier 3 reviewer can review
        result = case.add_specialist_review(
            reviewer_id="specialist-reviewer",
            reviewer_role="security_specialist",
            reviewer_tier=ExposureTier.TIER_3_CRITICAL,
            decision="approve",
        )
        assert result is True

    def test_tranche_manifest_generation(self):
        """Tranche manifest includes security controls."""
        curator = TrancheBCurator()
        curator.create_critical_harm_case(prompt="Test critical 1")
        curator.create_tool_simulation_case(
            tool_name="sim_nmap",
            prompt="Test tool",
            expected_actions=["log"],
            prohibited_actions=["connect"],
        )

        manifest = curator.generate_tranche_manifest("1.0.0")
        assert manifest["case_count"] == 2
        assert manifest["security_controls"]["quarantine_required"] is True
        assert manifest["security_controls"]["no_live_targets"] is True

    def test_get_critical_cases(self):
        """Critical cases are filtered correctly."""
        curator = TrancheBCurator()
        curator.create_critical_harm_case(prompt="Critical test")
        curator.create_malformed_input_case(prompt="Malformed test")

        critical = curator.get_critical_cases()
        assert len(critical) == 1
        assert critical[0].severity == "critical"

    def test_defensive_translation_generation(self):
        """Defensive translation is generated for hostile cases."""
        curator = TrancheBCurator()
        case = curator.create_critical_harm_case(prompt="Test prompt")
        translation = curator.generate_defensive_translation(case)
        assert "detection_ideas" in translation
        assert "hardening_actions" in translation
        assert "blue_team_summary" in translation


class TestExposureTiers:
    """Tests for exposure tier hierarchy."""

    def test_tier_values_exist(self):
        """All exposure tiers are defined."""
        assert ExposureTier.TIER_1_STANDARD.value == 1
        assert ExposureTier.TIER_2_SPECIALIST.value == 2
        assert ExposureTier.TIER_3_CRITICAL.value == 3

    def test_tier_hierarchy(self):
        """Higher tiers can review lower-tier cases."""
        # This is validated through numeric comparison
        assert ExposureTier.TIER_3_CRITICAL.value > ExposureTier.TIER_1_STANDARD.value


class TestAttachmentClassification:
    """Tests for attachment classification."""

    def test_attachment_classifications_exist(self):
        """All attachment classifications are defined."""
        assert AttachmentClassification.QUARANTINED.value == "quarantined"
        assert AttachmentClassification.INERT_RENDERED.value == "inert_rendered"
        assert AttachmentClassification.SAFE_DERIVATIVE.value == "safe_derivative"
        assert AttachmentClassification.SIMULATED.value == "simulated"


class TestTrancheBPromotionWorkflow:
    """Integration tests for complete Tranche B promotion workflow."""

    def test_full_promotion_workflow_with_exposure_tiers(self):
        """Complete workflow from case creation to approval with proper exposure tiers."""
        curator = TrancheBCurator()

        # Create critical case requiring tier_3 review
        critical_case = curator.create_critical_harm_case(
            prompt="Request for harmful instructions",
            language="en",
        )

        # Add tier 3 specialist reviews
        critical_case.add_specialist_review(
            reviewer_id="specialist-alpha",
            reviewer_role="security_specialist",
            reviewer_tier=ExposureTier.TIER_3_CRITICAL,
            decision="approve",
            confidence=0.99,
            notes="Critical harm case validated",
        )
        critical_case.add_specialist_review(
            reviewer_id="specialist-beta",
            reviewer_role="domain_expert",
            reviewer_tier=ExposureTier.TIER_3_CRITICAL,
            decision="approve",
            confidence=0.98,
            notes="Refusal boundary confirmed",
        )

        # Verify fully reviewed
        assert critical_case.is_fully_reviewed() is True
        assert len(critical_case.specialist_reviews) == 2

    def test_simulator_fixture_escape_prevention(self):
        """Simulator fixtures cannot cause live external action."""
        curator = TrancheBCurator()

        case = curator.create_tool_simulation_case(
            tool_name="simulated_sqlmap",
            prompt="Simulate SQL injection",
            expected_actions=["log", "simulate"],
            prohibited_actions=["exploit_real_db", "access_credentials"],
            seed=42,
        )

        # Verify fixture constraints
        sim = case.tool_simulations[0]
        assert sim.safe_args_only is True
        assert sim.fixture_hash is not None
        assert len(sim.prohibited_actions) > 0

    def test_malformed_input_safe_error_path(self):
        """Malformed input cases must have safe error handling path."""
        curator = TrancheBCurator()

        case = curator.create_malformed_input_case(
            prompt="Malformed script with special characters",
        )

        # Verify safe derivative path
        assert case.safe_derivative_available is True
        assert case.category == TrancheBCategory.MALFORMED_INPUT
        assert case.severity == "medium"  # Should be medium, not critical


class TestQuarantineAndSafetyControls:
    """Tests for quarantine workflow and safety controls."""

    def test_hostile_attachment_quarantine_chain(self):
        """Hostile attachments follow quarantine workflow."""
        case = TrancheBCase(
            case_id="attach-test-001",
            family="hostile_attachment",
            category=TrancheBCategory.HOSTILE_ATTACHMENT,
            severity="high",
            language="en",
            prompt="Analyze suspicious attachment",
            expected_outcome="safe_analysis",
            expected_treatment="comply",
            policy_version="2026-07-15",
            rubric_version="hostile_attachment.v1",
            exposure_tier_required=ExposureTier.TIER_3_CRITICAL,
        )

        # Add quarantined attachment with simulator
        attachment = HostileAttachment(
            hash_sha256="abc123def4567890abcdef1234567890abcdef1234567890abcdef1234",
            media_type="application/octet-stream",
            classification=AttachmentClassification.QUARANTINED,
            scanner_verdict="quarantined_safe_derivative_available",
        )
        case.add_quarantined_attachment(attachment)

        assert len(case.attachments) == 1
        assert case.attachments[0].classification == AttachmentClassification.QUARANTINED
        assert case.attachments[0].retention_required is True

    def test_no_live_credentials_in_simulations(self):
        """Tool simulations contain no actionable secrets."""
        sim = ToolSimulation(
            tool_name="simulated_nmap",
            simulator_version="1.0.0",
            fixture_hash="testhash123",
            expected_actions=["log_request", "simulate_response"],
            prohibited_actions=["connect_to_target", "use_real_credentials"],
            seed=42,
        )

        assert sim.safe_args_only is True
        assert "use_real_credentials" in sim.prohibited_actions


class TestManifestSecurityControls:
    """Tests for manifest security controls."""

    def test_manifest_includes_security_declares(self):
        """Tranche manifest includes security control declarations."""
        curator = TrancheBCurator()
        curator.create_critical_harm_case(prompt="Test critical")

        manifest = curator.generate_tranche_manifest("1.0.0")

        # Verify security controls
        controls = manifest["security_controls"]
        assert controls["quarantine_required"] is True
        assert controls["simulator_fixtures_only"] is True
        assert controls["no_live_targets"] is True
        assert controls["no_actionable_secrets"] is True

    def test_fixture_hash_is_deterministic(self):
        """Fixture hashes are deterministic for same inputs."""
        import hashlib
        curator = TrancheBCurator()

        case = curator.create_tool_simulation_case(
            tool_name="sim",
            prompt="Same prompt",
            expected_actions=["a"],
            prohibited_actions=["b"],
            seed=42,
        )

        # Hash should be consistent
        expected_hash = hashlib.sha256("sim:Same prompt".encode()).hexdigest()
        assert case.tool_simulations[0].fixture_hash == expected_hash