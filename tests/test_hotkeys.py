import pytest

from agent_whisper.hotkeys import DEFAULT_HOTKEY, hotkey_label, normalize_hotkey


@pytest.mark.parametrize("value", ["Ctrl", "Right Ctrl", "Right Ctrl (default)", "<ctrl_r>"])
def test_ctrl_aliases_use_right_ctrl(value: str) -> None:
    assert normalize_hotkey(value) == DEFAULT_HOTKEY


def test_named_choice_and_custom_shortcut() -> None:
    assert normalize_hotkey("Left Ctrl") == "<ctrl_l>"
    assert normalize_hotkey("F8") == "<f8>"
    assert normalize_hotkey("<ctrl>+<shift>+<space>") == "<ctrl>+<shift>+<space>"
    assert hotkey_label(DEFAULT_HOTKEY) == "Right Ctrl"


def test_empty_hotkey_is_rejected() -> None:
    with pytest.raises(ValueError, match="Choose a hotkey"):
        normalize_hotkey("  ")
