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

KEY_CODE_INFO: dict[str, tuple[int, str]] = {
    "Backspace": (8, "Backspace"),
    "Tab": (9, "Tab"),
    "Enter": (13, "Enter"),
    "Pause": (19, "Pause"),
    "CapsLock": (20, "Caps Lock"),
    "Escape": (27, "Escape"),
    "Space": (32, "Space"),
    "PageUp": (33, "Page Up"),
    "PageDown": (34, "Page Down"),
    "End": (35, "End"),
    "Home": (36, "Home"),
    "ArrowLeft": (37, "Left Arrow"),
    "ArrowUp": (38, "Up Arrow"),
    "ArrowRight": (39, "Right Arrow"),
    "ArrowDown": (40, "Down Arrow"),
    "PrintScreen": (44, "Print Screen"),
    "Insert": (45, "Insert"),
    "Delete": (46, "Delete"),
    "MetaLeft": (91, "Left Windows"),
    "MetaRight": (92, "Right Windows"),
    "ContextMenu": (93, "Menu"),
    "NumpadMultiply": (106, "Numpad ×"),
    "NumpadAdd": (107, "Numpad +"),
    "NumpadSubtract": (109, "Numpad −"),
    "NumpadDecimal": (110, "Numpad ."),
    "NumpadDivide": (111, "Numpad ÷"),
    "NumLock": (144, "Num Lock"),
    "ScrollLock": (145, "Scroll Lock"),
    "ControlLeft": (162, "Left Ctrl"),
    "ControlRight": (163, "Right Ctrl"),
    "AltLeft": (164, "Left Alt"),
    "AltRight": (165, "Right Alt"),
    "BrowserBack": (166, "Browser Back"),
    "BrowserForward": (167, "Browser Forward"),
    "BrowserRefresh": (168, "Browser Refresh"),
    "BrowserStop": (169, "Browser Stop"),
    "BrowserSearch": (170, "Browser Search"),
    "BrowserFavorites": (171, "Browser Favorites"),
    "BrowserHome": (172, "Browser Home"),
    "AudioVolumeMute": (173, "Volume Mute"),
    "AudioVolumeDown": (174, "Volume Down"),
    "AudioVolumeUp": (175, "Volume Up"),
    "MediaTrackNext": (176, "Next Track"),
    "MediaTrackPrevious": (177, "Previous Track"),
    "MediaStop": (178, "Media Stop"),
    "MediaPlayPause": (179, "Play/Pause"),
    "Semicolon": (186, ";"),
    "Equal": (187, "="),
    "Comma": (188, ","),
    "Minus": (189, "-"),
    "Period": (190, "."),
    "Slash": (191, "/"),
    "Backquote": (192, "`"),
    "BracketLeft": (219, "["),
    "Backslash": (220, "\\"),
    "BracketRight": (221, "]"),
    "Quote": (222, "'"),
    "IntlBackslash": (226, "Intl \\"),
    "ShiftLeft": (160, "Left Shift"),
    "ShiftRight": (161, "Right Shift"),
}

KEY_CODE_INFO.update(
    {f"Key{letter}": (ord(letter), letter) for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
)
KEY_CODE_INFO.update({f"Digit{digit}": (ord(digit), digit) for digit in "0123456789"})
KEY_CODE_INFO.update(
    {f"Numpad{digit}": (96 + digit, f"Numpad {digit}") for digit in range(10)}
)
KEY_CODE_INFO.update(
    {f"F{number}": (111 + number, f"F{number}") for number in range(1, 25)}
)


def _captured_code(shortcut: str) -> str | None:
    if not shortcut.casefold().startswith("code:"):
        return None
    return shortcut[5:]


def _captured_vk(shortcut: str) -> int | None:
    code = _captured_code(shortcut)
    return KEY_CODE_INFO.get(code, (None, ""))[0] if code else None


def _event_vk(key: keyboard.Key | keyboard.KeyCode | None) -> int | None:
    if key is None:
        return None
    direct_vk = getattr(key, "vk", None)
    if direct_vk is not None:
        return int(direct_vk)
    value_vk = getattr(getattr(key, "value", None), "vk", None)
    if value_vk is not None:
        return int(value_vk)
    character = getattr(key, "char", None)
    if isinstance(character, str) and len(character) == 1:
        return ord(character.upper())
    return None


def normalize_hotkey(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Choose a hotkey")

    shortcut = HOTKEY_CHOICES.get(cleaned, cleaned)
    if cleaned.casefold() in {"ctrl", "control", "right ctrl", "right control"}:
        shortcut = DEFAULT_HOTKEY

    captured_code = _captured_code(shortcut)
    if captured_code is not None:
        if captured_code not in KEY_CODE_INFO:
            raise ValueError("That keyboard key is not supported")
        return f"code:{captured_code}"

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
    captured_code = _captured_code(shortcut)
    if captured_code in KEY_CODE_INFO:
        return KEY_CODE_INFO[captured_code][1]
    if len(shortcut) == 1:
        return shortcut.upper()
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
        self._direct_vk = _captured_vk(self.hotkey)
        self._direct_key_down = False
        self._combo_listener: keyboard.Listener | None = None
        self._combo_hotkey: keyboard.HotKey | None = None
        self._combo_keys: frozenset[keyboard.Key | keyboard.KeyCode] = frozenset()
        self._combo_active = False
        self._state_lock = threading.Lock()
        self._stopped = threading.Event()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        fire = False
        if key == self._direct_key or (
            self._direct_vk is not None and _event_vk(key) == self._direct_vk
        ):
            with self._state_lock:
                if not self._direct_key_down:
                    self._direct_key_down = True
                    fire = True
        if fire:
            self.on_hotkey_down()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        fire = False
        if key == self._direct_key or (
            self._direct_vk is not None and _event_vk(key) == self._direct_vk
        ):
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
        if self._direct_key is not None or self._direct_vk is not None:
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
