import pytest
from pynput import keyboard

from agent_whisper.hotkeys import (
    DEFAULT_HOTKEY,
    ShortcutListener,
    hotkey_label,
    normalize_hotkey,
)


@pytest.mark.parametrize(
    "value", ["Ctrl", "Right Ctrl", "Right Ctrl (default)", "<ctrl_r>"]
)
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


def test_right_ctrl_is_push_to_talk_and_ignores_repeat() -> None:
    events: list[str] = []
    listener = ShortcutListener(
        DEFAULT_HOTKEY,
        lambda: events.append("down"),
        lambda: events.append("up"),
    )

    listener._on_press(keyboard.Key.ctrl_r)
    listener._on_press(keyboard.Key.ctrl_r)
    listener._on_release(keyboard.Key.ctrl_r)
    listener._on_release(keyboard.Key.ctrl_r)

    assert events == ["down", "up"]


def test_stopping_listener_releases_active_push_to_talk() -> None:
    events: list[str] = []
    listener = ShortcutListener(
        DEFAULT_HOTKEY,
        lambda: events.append("down"),
        lambda: events.append("up"),
    )
    listener._on_press(keyboard.Key.ctrl_r)
    listener.stop()
    assert events == ["down", "up"]
