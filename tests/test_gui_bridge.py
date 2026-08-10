from typing import cast

from agent_whisper.desktop import DesktopController
from agent_whisper.gui import DesktopApi, _load_interface


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
