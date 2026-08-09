from __future__ import annotations

import threading
from collections.abc import Callable

from pynput import keyboard

DEFAULT_HOTKEY = "<ctrl_r>"
LEGACY_DEFAULT_HOTKEY = "<ctrl>+<alt>+<space>"

HOTKEY_CHOICES: dict[str, str] = {
    "Right Ctrl (default)": DEFAULT_HOTKEY,
    "Left Ctrl": "<ctrl_l>",
    "F8": "<f8>",
    "Ctrl + Alt + Space": LEGACY_DEFAULT_HOTKEY,
    "Ctrl + Shift + Space": "<ctrl>+<shift>+<space>",
}

DIRECT_HOTKEYS = {
    DEFAULT_HOTKEY: keyboard.Key.ctrl_r,
    "<ctrl_l>": keyboard.Key.ctrl_l,
}


def normalize_hotkey(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Choose a hotkey")

    shortcut = HOTKEY_CHOICES.get(cleaned, cleaned)
    if cleaned.casefold() in {"ctrl", "control", "right ctrl", "right control"}:
        shortcut = DEFAULT_HOTKEY

    if shortcut != DEFAULT_HOTKEY:
        try:
            parsed = keyboard.HotKey.parse(shortcut)
        except (ValueError, TypeError):
            raise ValueError("Use Right Ctrl, F8, or a shortcut such as Ctrl + Alt + Space") from None
        if not parsed:
            raise ValueError("Choose a hotkey")
    return shortcut


def hotkey_label(shortcut: str) -> str:
    for label, value in HOTKEY_CHOICES.items():
        if shortcut == value:
            return label.replace(" (default)", "")
    return shortcut


class ShortcutListener:
    """Global shortcut listener with explicit Right Ctrl support."""

    def __init__(
        self,
        hotkey: str,
        on_hotkey: Callable[[], None],
        exit_hotkey: str,
        on_exit: Callable[[], None],
    ) -> None:
        self.hotkey = normalize_hotkey(hotkey)
        self.exit_hotkey = normalize_hotkey(exit_hotkey)
        if self.hotkey == self.exit_hotkey:
            raise ValueError("Recording and exit hotkeys must be different")
        self.on_hotkey = on_hotkey
        self.on_exit = on_exit
        self._listeners: list[keyboard.Listener] = []
        self._direct_key = DIRECT_HOTKEYS.get(self.hotkey)
        self._direct_key_down = False
        self._stopped = threading.Event()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key == self._direct_key and not self._direct_key_down:
            self._direct_key_down = True
            self.on_hotkey()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key == self._direct_key:
            self._direct_key_down = False

    def start(self) -> None:
        self._stopped.clear()
        shortcuts = {self.exit_hotkey: self.on_exit}
        if self._direct_key is not None:
            direct_key_listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listeners.append(direct_key_listener)
        else:
            shortcuts[self.hotkey] = self.on_hotkey

        self._listeners.append(keyboard.GlobalHotKeys(shortcuts))
        for listener in self._listeners:
            listener.start()

    def stop(self) -> None:
        for listener in self._listeners:
            listener.stop()
        self._listeners.clear()
        self._stopped.set()

    def wait(self) -> None:
        self._stopped.wait()
