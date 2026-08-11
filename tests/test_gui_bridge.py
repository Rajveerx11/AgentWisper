from dataclasses import asdict
from typing import cast

import pytest

from agent_whisper.desktop import DesktopController
from agent_whisper.gui import DesktopApi, _load_interface
from agent_whisper.storage import SettingsStore, UserSettings


def test_desktop_bridge_exposes_no_recursive_public_state() -> None:
    controller = cast(DesktopController, object())
    api = DesktopApi(controller)
    assert vars(api)
    assert all(name.startswith("_") for name in vars(api))


def test_local_interface_assets_are_inlined() -> None:
    interface = _load_interface()
    assert "AGENTWISPER_STYLES" not in interface
    assert "AGENTWISPER_SCRIPT" not in interface
    assert "Content-Security-Policy" in interface
    assert "Dictation workspace" in interface
    assert 'id="hotkey-recorder"' in interface
    assert 'id="project-path"' in interface
    assert 'id="teach-dialog"' in interface
    assert "Teach correction" in interface


def test_project_folder_dialog_returns_first_selected_path() -> None:
    controller = cast(DesktopController, object())
    api = DesktopApi(controller)

    class FakeWindow:
        def create_file_dialog(self, dialog_type, allow_multiple):
            assert int(dialog_type) == 20
            assert allow_multiple is False
            return (r"C:\code\project",)

    api._window = FakeWindow()
    assert api.choose_project_folder() == r"C:\code\project"


def test_controller_teaches_and_forgets_local_correction(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(
        "agent_whisper.desktop.discover_model_dir",
        lambda: tmp_path / "model",
    )
    controller = DesktopController()

    vocabulary = controller.teach_correction("my service", "MyService")
    assert vocabulary["learned"] == [{"canonical": "MyService", "alias": "my service"}]
    assert (
        controller.corrections.correct("Restart my service").text == "Restart MyService"
    )

    controller.forget_correction("my service", "MyService")
    assert controller.corrections.correct("Restart my service").text == (
        "Restart my service"
    )
    controller.shutdown()


def test_controller_applies_saved_project_context(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    project = tmp_path / "project"
    project.mkdir()
    (project / "billing_gateway.py").write_text("", encoding="utf-8")
    settings_path = tmp_path / "AgentWisper" / "settings.json"
    SettingsStore(settings_path).save(
        UserSettings(
            local_model_dir=str(tmp_path / "model"),
            project_path=str(project),
        )
    )

    controller = DesktopController()

    assert controller.vocabulary_payload()["project_term_count"] == 1
    assert controller.corrections.correct("Open billing gateway").text == (
        "Open billing_gateway"
    )
    controller.shutdown()


def test_settings_save_does_not_replace_active_recorder(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(
        "agent_whisper.desktop.discover_model_dir",
        lambda: tmp_path / "model",
    )
    controller = DesktopController()

    class FakeRecorder:
        recording = False
        level = 0.0

        def start(self) -> None:
            self.recording = True

        def stop(self):
            self.recording = False

    class FakeListener:
        stopped = False

        def start(self) -> None:
            pass

        def stop(self) -> None:
            self.stopped = True

    recorder = FakeRecorder()
    listener = FakeListener()
    controller.recorder = recorder
    monkeypatch.setattr(
        controller,
        "_make_hotkey_listener",
        lambda _hotkey: listener,
    )

    project = tmp_path / "project"
    project.mkdir()

    def start_recording_during_scan(_project):
        assert controller.start_recording()
        return {}

    monkeypatch.setattr(
        "agent_whisper.desktop.scan_repository",
        start_recording_during_scan,
    )
    payload = asdict(controller.settings)
    payload.update(
        {
            "provider": "custom",
            "custom_api_key": "test-key",
            "project_path": str(project),
        }
    )

    with pytest.raises(ValueError, match="Finish the current dictation"):
        controller.save_settings(payload)

    assert controller.recorder is recorder
    assert recorder.recording
    assert listener.stopped
    assert controller.settings.provider == "local"
    controller.shutdown()
