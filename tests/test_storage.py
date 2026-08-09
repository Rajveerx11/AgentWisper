from pathlib import Path

from agent_whisper.storage import HistoryStore, SecretStore, SettingsStore, UserSettings


def test_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    settings = UserSettings(provider="groq", hotkey="<ctrl>+<shift>+<space>")
    store.save(settings)
    loaded = store.load()
    assert loaded.provider == "groq"
    assert loaded.hotkey == "<ctrl>+<shift>+<space>"


def test_legacy_default_hotkey_migrates_to_right_ctrl(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"hotkey": "<ctrl>+<alt>+<space>"}', encoding="utf-8")
    assert SettingsStore(path).load().hotkey == "<ctrl_r>"


def test_secret_store_uses_dpapi_round_trip(tmp_path: Path) -> None:
    store = SecretStore(tmp_path / "secrets.json")
    store.set("groq_api_key", "test-secret-never-log")
    assert store.get("groq_api_key") == "test-secret-never-log"
    assert "test-secret-never-log" not in (tmp_path / "secrets.json").read_text(encoding="utf-8")
    store.set("groq_api_key", "")
    assert not store.has("groq_api_key")


def test_history_round_trip_and_clear(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    store.add("Supabase", "Superbase", "local", "parakeet", 2.5, 0.3)
    items = store.list()
    assert len(items) == 1
    assert items[0].text == "Supabase"
    assert items[0].raw_text == "Superbase"
    store.clear()
    assert store.list() == []
