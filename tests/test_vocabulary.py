import json
import time
from pathlib import Path

from agent_whisper.vocabulary import (
    MAX_MANIFEST_BYTES,
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


def test_custom_terms_override_builtin_aliases() -> None:
    engine = CorrectionEngine({"SupabaseCloud": ["super base"]})
    result = engine.correct("Open super base.")
    assert result.text == "Open SupabaseCloud."


def test_custom_exact_spelling_is_not_rewritten_by_later_rules() -> None:
    engine = CorrectionEngine({"super base": ["foo bar baz"]})
    result = engine.correct("Open foo bar baz.")
    assert result.text == "Open super base."


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


def test_repository_scan_is_bounded_and_skips_dependencies(tmp_path: Path) -> None:
    (tmp_path / "alpha_service.py").write_text("", encoding="utf-8")
    (tmp_path / "zulu_service.py").write_text("", encoding="utf-8")
    dependency = tmp_path / "node_modules"
    dependency.mkdir()
    (dependency / "hidden_service.py").write_text("", encoding="utf-8")

    terms = scan_repository(tmp_path, max_files=1)

    assert "alpha_service" in terms
    assert "zulu_service" not in terms
    assert "hidden_service" not in terms


def test_repository_terms_are_capped(tmp_path: Path) -> None:
    dependencies = {f"package-{index}": "1.0.0" for index in range(600)}
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": dependencies}),
        encoding="utf-8",
    )

    assert len(scan_repository(tmp_path)) == 500


def test_repository_cap_is_applied_after_no_op_terms_are_filtered(
    tmp_path: Path,
) -> None:
    def letters(index: int) -> str:
        return "".join(
            chr(ord("a") + part)
            for part in (index // (26 * 26), (index // 26) % 26, index % 26)
        )

    dependencies = {f"a{letters(index)}": "1.0.0" for index in range(500)}
    dependencies["zzz-useful-name"] = "1.0.0"
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": dependencies}),
        encoding="utf-8",
    )

    terms = scan_repository(tmp_path)

    assert terms == {"zzz-useful-name": ["zzz useful name"]}


def test_repository_scan_tolerates_unexpected_manifest_shapes(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("[]", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "project = []\ntool = []\n",
        encoding="utf-8",
    )
    (tmp_path / "Cargo.toml").write_text(
        "dependencies = []\n",
        encoding="utf-8",
    )

    assert scan_repository(tmp_path) == {}


def test_repository_scan_hard_clamps_file_limit(monkeypatch, tmp_path: Path) -> None:
    def letters(index: int) -> str:
        return "".join(
            chr(ord("a") + part)
            for part in (
                index // (26 * 26 * 26),
                (index // (26 * 26)) % 26,
                (index // 26) % 26,
                index % 26,
            )
        )

    filenames = [f"a{letters(index)}.py" for index in range(2_000)]
    filenames.append("zzzz_useful.py")
    monkeypatch.setattr(
        "agent_whisper.vocabulary.os.walk",
        lambda *_args, **_kwargs: [(str(tmp_path), [], filenames)],
    )

    assert scan_repository(tmp_path, max_files=10_000) == {}


def test_repository_scan_ignores_oversized_manifest(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_bytes(b" " * (MAX_MANIFEST_BYTES + 1))

    assert scan_repository(tmp_path) == {}


def test_repository_scan_caps_manifest_entries(tmp_path: Path) -> None:
    dependencies = {f"dependency{index}": "1.0.0" for index in range(2_000)}
    dependencies["zzz-useful-name"] = "1.0.0"
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": dependencies}),
        encoding="utf-8",
    )

    assert "zzz-useful-name" not in scan_repository(tmp_path)


def test_maximum_vocabulary_no_match_stays_fast() -> None:
    learned = {
        f"CustomService{index}": [f"custom phrase {index}"] for index in range(500)
    }
    project = {
        f"ProjectService{index}": [f"project phrase {index}"] for index in range(500)
    }
    engine = CorrectionEngine(custom_terms=learned, repository_terms=project)
    transcript = " ".join(["ordinary"] * 500)

    started = time.perf_counter()
    for _ in range(3):
        assert engine.correct(transcript).text == transcript
    average_seconds = (time.perf_counter() - started) / 3

    assert average_seconds < 0.2
