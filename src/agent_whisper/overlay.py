from __future__ import annotations

import ctypes
import multiprocessing
import os
import queue
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from importlib.resources import files
from multiprocessing.connection import Connection
from typing import Any

OVERLAY_DIMENSIONS = {
    "idle": (264, 60),
    "listening": (352, 74),
    "transcribing": (304, 64),
    "success": (304, 64),
    "error": (304, 64),
    "notice": (304, 64),
}
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def _overlay_dimensions(state: str) -> tuple[int, int]:
    return OVERLAY_DIMENSIONS.get(state, OVERLAY_DIMENSIONS["idle"])


def _load_overlay_interface() -> str:
    assets = files("agent_whisper").joinpath("overlay_web")
    html = assets.joinpath("index.html").read_text(encoding="utf-8")
    css = assets.joinpath("styles.css").read_text(encoding="utf-8")
    script = assets.joinpath("app.js").read_text(encoding="utf-8")
    return html.replace(
        "<!-- AGENTWISPER_OVERLAY_STYLES -->",
        f"<style>{css}</style>",
    ).replace(
        "<!-- AGENTWISPER_OVERLAY_SCRIPT -->",
        f"<script>{script}</script>",
    )


def _work_area() -> tuple[int, int, int, int]:
    class Rect(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("size", ctypes.c_ulong),
            ("monitor", Rect),
            ("work", Rect),
            ("flags", ctypes.c_ulong),
        ]

    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        monitor = user32.MonitorFromWindow(user32.GetForegroundWindow(), 2)
        info = MonitorInfo()
        info.size = ctypes.sizeof(MonitorInfo)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return info.work.left, info.work.top, info.work.right, info.work.bottom
    except (AttributeError, OSError):
        pass
    return 0, 0, 1920, 1080


def _overlay_position(width: int, height: int) -> tuple[int, int]:
    left, top, right, bottom = _work_area()
    return (
        max(left, right - width - 22),
        max(top, bottom - height - 22),
    )


def _set_overlay_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def _style_process_windows(process_id: int) -> None:
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        get_window_process = ctypes.WINFUNCTYPE(
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        )(("GetWindowThreadProcessId", user32))
        get_window_long = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_int,
        )(("GetWindowLongW", user32))
        set_window_long = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_long,
        )(("SetWindowLongW", user32))
        set_window_pos = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        )(("SetWindowPos", user32))
        get_window_rect = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.RECT),
        )(("GetWindowRect", user32))
        set_window_region = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
        )(("SetWindowRgn", user32))
        create_round_region = ctypes.WINFUNCTYPE(
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        )(("CreateRoundRectRgn", gdi32))
        delete_object = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            ctypes.c_void_p,
        )(("DeleteObject", gdi32))
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )

        def update_window(handle: int, _parameter: int) -> bool:
            window_process_id = ctypes.c_ulong()
            get_window_process(handle, ctypes.byref(window_process_id))
            if window_process_id.value != process_id:
                return True
            style = get_window_long(handle, -20)
            set_window_long(
                handle,
                -20,
                style | 0x08000000 | 0x00000080,
            )
            set_window_pos(handle, ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0013)
            rectangle = wintypes.RECT()
            if not get_window_rect(handle, ctypes.byref(rectangle)):
                return True
            width = max(1, rectangle.right - rectangle.left)
            height = max(1, rectangle.bottom - rectangle.top)
            region = create_round_region(
                0,
                0,
                width + 1,
                height + 1,
                36,
                36,
            )
            if region and not set_window_region(handle, region, True):
                delete_object(region)
            return True

        callback = callback_type(update_window)
        user32.EnumWindows(callback, 0)
    except (AttributeError, OSError):
        pass


class OverlayApi:
    """Small IPC bridge exposed only to the local overlay page."""

    def __init__(self, connection: Connection, parent_pid: int) -> None:
        self._connection = connection
        self._parent_handle = self._open_parent(parent_pid)
        self._window: Any | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._snapshot: dict[str, Any] = {
            "state": "idle",
            "hotkey_label": "Right Ctrl",
            "level": 0.0,
            "levels": [],
            "recording_seconds": 0.0,
        }

    @staticmethod
    def _open_parent(parent_pid: int) -> int | None:
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = ctypes.c_void_p
            return int(kernel32.OpenProcess(0x00100000, False, parent_pid) or 0) or None
        except (AttributeError, OSError):
            return None

    def attach(self, window: Any) -> None:
        self._window = window

    def _parent_alive(self) -> bool:
        if not self._parent_handle:
            return True
        try:
            return (
                ctypes.windll.kernel32.WaitForSingleObject(self._parent_handle, 0)
                == 258
            )
        except (AttributeError, OSError):
            return True

    def start(self) -> None:
        _style_process_windows(os.getpid())
        threading.Thread(
            target=self._receive,
            daemon=True,
            name="AgentWisperOverlayReceiver",
        ).start()

    def _receive(self) -> None:
        old_state = ""
        while not self._stop.is_set() and self._parent_alive():
            try:
                if not self._connection.poll(0.15):
                    continue
                message = self._connection.recv()
            except (BrokenPipeError, EOFError, OSError):
                break
            if message.get("kind") == "shutdown":
                break
            if message.get("kind") == "reposition":
                self.reposition()
                continue
            if message.get("kind") != "state":
                continue
            snapshot = dict(message.get("payload", {}))
            with self._lock:
                self._snapshot = snapshot
            state = str(snapshot.get("state", "idle"))
            if state != old_state:
                old_state = state
                self.resize_for_state(state)
        self._stop.set()
        if self._window is not None:
            try:
                self._window.destroy()
            except (AttributeError, OSError, RuntimeError):
                return

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def toggle(self) -> bool:
        return self._send("toggle")

    def open_app(self) -> bool:
        return self._send("open")

    def _send(self, command: str) -> bool:
        try:
            self._connection.send({"kind": "command", "command": command})
            return True
        except (BrokenPipeError, EOFError, OSError):
            return False

    def reposition(self) -> bool:
        if self._window is None:
            return False
        with self._lock:
            state = str(self._snapshot.get("state", "idle"))
        width, height = _overlay_dimensions(state)
        x, y = _overlay_position(width, height)
        try:
            self._window.move(x, y)
            _style_process_windows(os.getpid())
            return True
        except (AttributeError, OSError, RuntimeError):
            return False

    def resize_for_state(self, state: str) -> bool:
        if self._window is None:
            return False
        width, height = _overlay_dimensions(state)
        x, y = _overlay_position(width, height)
        try:
            self._window.resize(width, height)
            self._window.move(x, y)
            _style_process_windows(os.getpid())
            return True
        except (AttributeError, OSError, RuntimeError):
            return False

    def close(self) -> None:
        self._stop.set()
        if self._parent_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self._parent_handle)
            except (AttributeError, OSError):
                pass
        self._connection.close()


def run_signal_node(connection: Connection, parent_pid: int) -> None:
    _set_overlay_dpi_awareness()
    import webview

    api = OverlayApi(connection, parent_pid)
    width, height = _overlay_dimensions("idle")
    x, y = _overlay_position(width, height)
    window = webview.create_window(
        "AgentWisper Signal",
        html=_load_overlay_interface(),
        js_api=api,
        width=width,
        height=height,
        x=x,
        y=y,
        min_size=(200, 50),
        resizable=False,
        frameless=True,
        easy_drag=False,
        shadow=False,
        focus=False,
        on_top=True,
        transparent=False,
        background_color="#111820",
        text_select=False,
    )
    if window is None:
        connection.close()
        return
    api.attach(window)
    try:
        webview.start(
            api.start,
            gui="edgechromium",
            debug=False,
            http_server=False,
            private_mode=True,
            user_agent="AgentWisper/Signal",
        )
    finally:
        api.close()


class OverlayProcess:
    """Owns the frameless HTML signal window and its duplex command pipe."""

    def __init__(
        self,
        runtime_getter: Callable[[], dict[str, Any]],
        toggle_command: Callable[[], Any],
        open_command: Callable[[], Any],
    ) -> None:
        self.runtime_getter = runtime_getter
        self.toggle_command = toggle_command
        self.open_command = open_command
        self._messages: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._stop = threading.Event()
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=run_signal_node,
            args=(child, os.getpid()),
            daemon=True,
            name="AgentWisperSignalNode",
        )
        process.start()
        child.close()
        self._process = process
        self._connection = parent
        self._thread = threading.Thread(
            target=self._sync,
            daemon=True,
            name="AgentWisperSignalSync",
        )
        self._thread.start()

    def notice(self, message: str) -> None:
        self._messages.put(("notice", message))

    def reposition(self) -> None:
        self._messages.put(("reposition", ""))

    def _sync(self) -> None:
        if self._connection is None:
            return
        connection = self._connection
        last_version = -1
        last_sent = 0.0
        notice_until = 0.0
        notice_message = ""
        while not self._stop.is_set():
            try:
                while connection.poll():
                    incoming = connection.recv()
                    if incoming.get("kind") == "command":
                        command = incoming.get("command")
                        if command == "toggle":
                            self.toggle_command()
                        elif command == "open":
                            self.open_command()

                while True:
                    kind, message = self._messages.get_nowait()
                    if kind == "shutdown":
                        connection.send({"kind": "shutdown"})
                        return
                    if kind == "reposition":
                        connection.send({"kind": "reposition"})
                        continue
                    if kind == "notice":
                        notice_until = time.monotonic() + 2.4
                        notice_message = message
            except queue.Empty:
                pass
            except (BrokenPipeError, EOFError, OSError):
                return

            runtime = self.runtime_getter()
            now = time.monotonic()
            if now < notice_until and runtime["state"] == "idle":
                runtime = {**runtime, "state": "notice", "detail": notice_message}
            animated = runtime["state"] == "listening"
            if runtime["version"] != last_version or animated or now - last_sent > 0.8:
                try:
                    connection.send({"kind": "state", "payload": runtime})
                except (BrokenPipeError, EOFError, OSError):
                    return
                last_version = runtime["version"]
                last_sent = now
            time.sleep(0.045 if animated else 0.12)

    def stop(self) -> None:
        if self._process is None:
            return
        self._messages.put(("shutdown", ""))
        if self._thread:
            self._thread.join(timeout=1.5)
        self._stop.set()
        self._process.join(timeout=1.5)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=1.0)
        if self._connection:
            self._connection.close()
        self._process = None
