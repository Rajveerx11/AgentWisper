import json
from pathlib import Path

import pytest

from agent_whisper.storage import (
    HistoryStore,
    SecretStore,
    SettingsStore,
    UserSettings,
    VocabularyStore,
)


def test_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    settings = UserSettings(provider="groq", hotkey="<ctrl>+<shift>+<space>")
    store.save(settings)
    loaded = store.load()
    assert loaded.provider == "groq"
    assert loaded.hotkey == "<ctrl>+<shift>+<space>"
    assert loaded.settings_version == 3


def test_legacy_default_hotkey_migrates_to_right_ctrl(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"hotkey": "<ctrl>+<alt>+<space>"}', encoding="utf-8")
    assert SettingsStore(path).load().hotkey == "<ctrl_r>"


def test_secret_store_uses_dpapi_round_trip(tmp_path: Path) -> None:
    store = SecretStore(tmp_path / "secrets.json")
    store.set("groq_api_key", "test-secret-never-log")
    assert store.get("groq_api_key") == "test-secret-never-log"
    assert "test-secret-never-log" not in (tmp_path / "secrets.json").read_text(
        encoding="utf-8"
    )
    store.set("groq_api_key", "")
    assert not store.has("groq_api_key")


def test_history_round_trip_and_clear(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    store.add("Supabase", "Superbase", "local", "parakeet", 2.5, 0.3)
    items = store.list()
    assert len(items) == 1
    assert items[0].text == "Supabase"
    assert items[0].raw_text == "Superbase"
    assert store.count() == 1
    store.clear()
    assert store.list() == []
    assert store.count() == 0


def test_vocabulary_round_trip_deduplicates_and_removes(tmp_path: Path) -> None:
    path = tmp_path / "vocabulary.json"
    store = VocabularyStore(path)

    assert store.add("Supabase", "zupa base") == {"Supabase": ["zupa base"]}
    assert store.add("supabase", "ZUPA BASE") == {"Supabase": ["zupa base"]}
    assert VocabularyStore(path).load() == {"Supabase": ["zupa base"]}
    assert '"version": 1' in path.read_text(encoding="utf-8")
    assert store.remove("Supabase", "zupa base") == {}
    assert VocabularyStore(path).load() == {}


def test_vocabulary_reassigns_heard_phrase_stably(tmp_path: Path) -> None:
    path = tmp_path / "vocabulary.json"
    store = VocabularyStore(path)

    store.add("Zebra", "x y")
    assert store.add("Alpha", "x y") == {"Alpha": ["x y"]}
    assert VocabularyStore(path).load() == {"Alpha": ["x y"]}


def test_vocabulary_rejects_invalid_and_excessive_aliases(tmp_path: Path) -> None:
    store = VocabularyStore(tmp_path / "vocabulary.json")
    with pytest.raises(ValueError, match="must be different"):
        store.add("Supabase", "supabase")
    with pytest.raises(ValueError, match="Enter heard phrase"):
        store.add("Supabase", "")
    with pytest.raises(TypeError, match="Enter heard phrase"):
        store.add("Supabase", None)  # type: ignore[arg-type]

    for index in range(20):
        store.add("InternalAPI", f"internal api {index}")
    with pytest.raises(ValueError, match="maximum spoken forms"):
        store.add("InternalAPI", "one alias too many")


def test_vocabulary_load_caps_manually_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "vocabulary.json"
    path.write_text(
        json.dumps(
            {
                "terms": [
                    {"canonical": f"Term{index}", "aliases": [f"term {index}"]}
                    for index in range(600)
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = VocabularyStore(path).load()

    assert sum(len(aliases) for aliases in loaded.values()) == 500
