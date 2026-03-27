"""Tests for the ADR generator module."""

from __future__ import annotations

from letsbuild.architect.adr_generator import ADRGenerator
from letsbuild.models.architect_models import ADR, ADRStatus


class TestADRGeneratorGenerate:
    """Tests for ADRGenerator.generate()."""

    def test_generate_returns_at_least_two_adrs(self) -> None:
        """Generate always produces a minimum of 2 ADRs even with minimal input."""
        gen = ADRGenerator()
        adrs = gen.generate(project_name="test-project", tech_choices=[])
        assert len(adrs) >= 2
        for adr in adrs:
            assert isinstance(adr, ADR)

    def test_generate_with_skill_templates(self) -> None:
        """Skill ADR templates are incorporated into the output."""
        gen = ADRGenerator()
        templates = ["Use event sourcing for audit trail"]
        adrs = gen.generate(
            project_name="audit-app",
            tech_choices=["fastapi"],
            skill_adr_templates=templates,
        )
        assert len(adrs) >= 2
        titles = [a.title for a in adrs]
        assert "Use FastAPI for API layer" in titles
        assert "Use event sourcing for audit trail" in titles


class TestADRGeneratorFromTechStack:
    """Tests for ADRGenerator.generate_from_tech_stack()."""

    def test_generate_from_tech_stack_fastapi(self) -> None:
        """FastAPI in tech stack produces the FastAPI ADR."""
        gen = ADRGenerator()
        adrs = gen.generate_from_tech_stack(["FastAPI"])
        assert len(adrs) == 1
        assert adrs[0].title == "Use FastAPI for API layer"
        assert adrs[0].status == ADRStatus.ACCEPTED

    def test_generate_from_tech_stack_react(self) -> None:
        """React in tech stack produces the React ADR."""
        gen = ADRGenerator()
        adrs = gen.generate_from_tech_stack(["react"])
        assert len(adrs) == 1
        assert adrs[0].title == "Use React for frontend UI"
        assert adrs[0].status == ADRStatus.ACCEPTED

    def test_generate_from_tech_stack_multiple(self) -> None:
        """Multiple recognised technologies produce multiple ADRs."""
        gen = ADRGenerator()
        adrs = gen.generate_from_tech_stack(["fastapi", "postgresql", "docker"])
        assert len(adrs) == 3
        titles = {a.title for a in adrs}
        assert "Use FastAPI for API layer" in titles
        assert "Use PostgreSQL for data persistence" in titles
        assert "Containerize application with Docker" in titles

    def test_generate_from_tech_stack_unrecognised_tech_skipped(self) -> None:
        """Unrecognised technologies are silently skipped."""
        gen = ADRGenerator()
        adrs = gen.generate_from_tech_stack(["obscure-framework"])
        assert len(adrs) == 0


class TestADRIDIncrement:
    """Tests for ADR ID sequencing."""

    def test_adr_ids_increment(self) -> None:
        """ADR IDs increment sequentially as ADR-001, ADR-002, etc."""
        gen = ADRGenerator()
        adrs = gen.generate_from_tech_stack(["fastapi", "postgresql", "docker"])
        assert adrs[0].adr_id == "ADR-001"
        assert adrs[1].adr_id == "ADR-002"
        assert adrs[2].adr_id == "ADR-003"


class TestADRContent:
    """Tests for ADR content quality."""

    def test_adr_status_is_accepted(self) -> None:
        """All generated ADRs have ACCEPTED status."""
        gen = ADRGenerator()
        adrs = gen.generate(
            project_name="status-check",
            tech_choices=["fastapi", "react"],
            skill_adr_templates=["Use CQRS pattern"],
        )
        for adr in adrs:
            assert adr.status == ADRStatus.ACCEPTED

    def test_adr_has_substantive_content(self) -> None:
        """Each ADR field (context, decision, consequences) is non-empty and substantive."""
        gen = ADRGenerator()
        adrs = gen.generate_from_tech_stack(["fastapi"])
        adr = adrs[0]
        # Non-empty
        assert adr.context
        assert adr.decision
        assert adr.consequences
        # Substantive (at least 50 characters each)
        assert len(adr.context) >= 50
        assert len(adr.decision) >= 50
        assert len(adr.consequences) >= 50


class TestADRGeneratorFromTemplates:
    """Tests for ADRGenerator.generate_from_templates()."""

    def test_generate_from_templates(self) -> None:
        """Template strings are expanded into full ADR models."""
        gen = ADRGenerator()
        templates = [
            "Use event sourcing for audit trail",
            "Adopt hexagonal architecture",
        ]
        adrs = gen.generate_from_templates(templates)
        assert len(adrs) == 2
        assert adrs[0].title == "Use event sourcing for audit trail"
        assert adrs[1].title == "Adopt hexagonal architecture"
        # Each expanded ADR has substantive content
        for adr in adrs:
            assert adr.status == ADRStatus.ACCEPTED
            assert len(adr.context) >= 50
            assert len(adr.decision) >= 50
            assert len(adr.consequences) >= 50

    def test_generate_from_templates_skips_empty(self) -> None:
        """Empty template strings are skipped."""
        gen = ADRGenerator()
        adrs = gen.generate_from_templates(["Valid template", "", "  "])
        assert len(adrs) == 1
        assert adrs[0].title == "Valid template"
