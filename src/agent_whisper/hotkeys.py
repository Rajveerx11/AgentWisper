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
    "<f8>": keyboard.Key.f8,
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
            raise ValueError(
                "Use Right Ctrl, F8, or a shortcut such as Ctrl + Alt + Space"
            ) from None
        if not parsed:
            raise ValueError("Choose a hotkey")
    return shortcut


def hotkey_label(shortcut: str) -> str:
    for label, value in HOTKEY_CHOICES.items():
        if shortcut == value:
            return label.replace(" (default)", "")
    return shortcut


class ShortcutListener:
    """Global push-to-talk listener with press and release callbacks."""

    def __init__(
        self,
        hotkey: str,
        on_hotkey_down: Callable[[], None],
        on_hotkey_up: Callable[[], None],
        exit_hotkey: str | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        self.hotkey = normalize_hotkey(hotkey)
        self.exit_hotkey = normalize_hotkey(exit_hotkey) if exit_hotkey else None
        if self.exit_hotkey and self.hotkey == self.exit_hotkey:
            raise ValueError("Recording and exit hotkeys must be different")
        if bool(self.exit_hotkey) != bool(on_exit):
            raise ValueError("Exit hotkey and callback must be provided together")
        self.on_hotkey_down = on_hotkey_down
        self.on_hotkey_up = on_hotkey_up
        self.on_exit = on_exit
        self._listeners: list[keyboard.Listener] = []
        self._direct_key = DIRECT_HOTKEYS.get(self.hotkey)
        self._direct_key_down = False
        self._combo_listener: keyboard.Listener | None = None
        self._combo_hotkey: keyboard.HotKey | None = None
        self._combo_keys: frozenset[keyboard.Key | keyboard.KeyCode] = frozenset()
        self._combo_active = False
        self._state_lock = threading.Lock()
        self._stopped = threading.Event()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        fire = False
        if key == self._direct_key:
            with self._state_lock:
                if not self._direct_key_down:
                    self._direct_key_down = True
                    fire = True
        if fire:
            self.on_hotkey_down()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        fire = False
        if key == self._direct_key:
            with self._state_lock:
                if self._direct_key_down:
                    self._direct_key_down = False
                    fire = True
        if fire:
            self.on_hotkey_up()

    def _activate_combo(self) -> None:
        fire = False
        with self._state_lock:
            if not self._combo_active:
                self._combo_active = True
                fire = True
        if fire:
            self.on_hotkey_down()

    def _combo_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if self._combo_listener is None or self._combo_hotkey is None or key is None:
            return
        self._combo_hotkey.press(self._combo_listener.canonical(key))

    def _combo_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if self._combo_listener is None or self._combo_hotkey is None or key is None:
            return
        canonical = self._combo_listener.canonical(key)
        fire = False
        with self._state_lock:
            if self._combo_active and canonical in self._combo_keys:
                self._combo_active = False
                fire = True
        self._combo_hotkey.release(canonical)
        if fire:
            self.on_hotkey_up()

    def start(self) -> None:
        if self._listeners:
            return
        self._stopped.clear()
        if self._direct_key is not None:
            record_listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listeners.append(record_listener)
        else:
            parsed = keyboard.HotKey.parse(self.hotkey)
            self._combo_keys = frozenset(parsed)
            self._combo_hotkey = keyboard.HotKey(parsed, self._activate_combo)
            self._combo_listener = keyboard.Listener(
                on_press=self._combo_press,
                on_release=self._combo_release,
            )
            self._listeners.append(self._combo_listener)

        if self.exit_hotkey and self.on_exit:
            self._listeners.append(
                keyboard.GlobalHotKeys({self.exit_hotkey: self.on_exit})
            )
        for listener in self._listeners:
            listener.start()

    def stop(self) -> None:
        fire_release = False
        with self._state_lock:
            if self._direct_key_down or self._combo_active:
                fire_release = True
            self._direct_key_down = False
            self._combo_active = False
        for listener in self._listeners:
            listener.stop()
        self._listeners.clear()
        self._combo_listener = None
        self._combo_hotkey = None
        self._combo_keys = frozenset()
        if fire_release:
            self.on_hotkey_up()
        self._stopped.set()

    def wait(self) -> None:
        self._stopped.wait()
