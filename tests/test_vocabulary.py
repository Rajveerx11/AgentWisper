from pathlib import Path

from agent_whisper.vocabulary import (
    CorrectionEngine,
    identifier_to_spoken,
    scan_repository,
)


def test_builtin_technical_corrections() -> None:
    engine = CorrectionEngine()
    result = engine.correct(
        "Use super base with post grass sequel and p g vector through open a i."
    )
    assert result.text == "Use Supabase with PostgreSQL and pgvector through OpenAI."


def test_corrections_match_real_parakeet_output() -> None:
    engine = CorrectionEngine()
    result = engine.correct(
        "Use Superbase with Postgrass SQL and PG Vector through OpenAI."
    )
    assert result.text == "Use Supabase with PostgreSQL and pgvector through OpenAI."


def test_project_and_agent_terms() -> None:
    engine = CorrectionEngine()
    result = engine.correct("Open agent whisper and use clawed code.")
    assert result.text == "Open AgentWisper and use Claude Code."


def test_custom_terms() -> None:
    engine = CorrectionEngine({"MyInternalService": ["my internal service"]})
    result = engine.correct("Restart my internal service.")
    assert result.text == "Restart MyInternalService."


def test_identifier_to_spoken() -> None:
    assert identifier_to_spoken("MyInternalService") == "my internal service"
    assert identifier_to_spoken("payment_service-v2") == "payment service v 2"


def test_repository_filename_context(tmp_path: Path) -> None:
    (tmp_path / "payment_service.py").write_text("", encoding="utf-8")
    terms = scan_repository(tmp_path)
    engine = CorrectionEngine(repository_terms=terms)
    result = engine.correct("Update the payment service implementation.")
    assert result.text == "Update the payment_service implementation."


def test_repository_dependency_context(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"@modelcontextprotocol/sdk":"1.0.0"}}',
        encoding="utf-8",
    )
    terms = scan_repository(tmp_path)
    assert terms["@modelcontextprotocol/sdk"] == ["modelcontextprotocol sdk"]
