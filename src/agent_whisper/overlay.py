from __future__ import annotations

import ctypes
import math
import multiprocessing
import os
import queue
import threading
import time
import tkinter as tk
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

COLORS = {
    "accent": "#2F67E8",
    "success": "#087456",
    "danger": "#B63A50",
    "warning": "#A36616",
    "carbon": "#111820",
    "carbon_2": "#18222D",
    "carbon_border": "#344252",
    "carbon_text": "#F7FAFC",
    "carbon_muted": "#AAB7C5",
    "transparent": "#010203",
}

FONT_UI = "Segoe UI"
FONT_MONO = "Cascadia Mono"


def _round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    **kwargs: Any,
) -> int:
    points = (
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    )
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class SignalNode:
    def __init__(self, connection: Connection, parent_pid: int) -> None:
        self.connection = connection
        self.parent_handle = self._open_parent(parent_pid)
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.985)
        self.root.configure(bg=COLORS["transparent"])
        try:
            self.root.wm_attributes("-transparentcolor", COLORS["transparent"])
            canvas_background = COLORS["transparent"]
        except tk.TclError:
            self.root.configure(bg=COLORS["carbon"])
            canvas_background = COLORS["carbon"]

        self.canvas = tk.Canvas(
            self.root,
            bg=canvas_background,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", lambda _event: self._send("toggle"))
        self.canvas.bind("<Button-3>", lambda _event: self._send("open"))
        self.canvas.bind("<Enter>", lambda _event: self._set_hover(True))
        self.canvas.bind("<Leave>", lambda _event: self._set_hover(False))

        self.state = "idle"
        self.detail = ""
        self.hotkey = "Right Ctrl"
        self.level = 0.0
        self.visual_level = 0.0
        self.peak_level = 0.0
        self.recording_seconds = 0.0
        self.word_count = 0
        self.pasted: bool | None = None
        self.phase = 0.0
        self.hovered = False
        self.dirty = True
        self.root.update_idletasks()
        self._make_nonactivating()
        self._position()
        self.root.deiconify()
        self._make_nonactivating()
        self.root.after(35, self._poll)
        self.root.after(45, self._tick)

    @staticmethod
    def _open_parent(parent_pid: int) -> int | None:
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = ctypes.c_void_p
            return int(kernel32.OpenProcess(0x00100000, False, parent_pid) or 0) or None
        except (AttributeError, OSError):
            return None

    def _parent_alive(self) -> bool:
        if not self.parent_handle:
            return True
        try:
            return (
                ctypes.windll.kernel32.WaitForSingleObject(self.parent_handle, 0) == 258
            )
        except (AttributeError, OSError):
            return True

    def _send(self, command: str) -> None:
        try:
            self.connection.send({"kind": "command", "command": command})
        except (BrokenPipeError, EOFError, OSError):
            self.root.destroy()

    def _native_handle(self) -> int:
        user32 = ctypes.windll.user32
        user32.GetParent.restype = ctypes.c_void_p
        handle = int(self.root.winfo_id())
        parent = int(user32.GetParent(handle) or 0)
        return parent or handle

    def _make_nonactivating(self) -> None:
        try:
            user32 = ctypes.windll.user32
            handle = self._native_handle()
            style = user32.GetWindowLongW(handle, -20)
            user32.SetWindowLongW(
                handle,
                -20,
                style | 0x08000000 | 0x00000080,
            )
            user32.SetWindowPos(handle, -1, 0, 0, 0, 0, 0x0013)
        except (AttributeError, OSError, tk.TclError):
            pass

    def _set_hover(self, hovered: bool) -> None:
        self.hovered = hovered
        self.dirty = True

    def _dimensions(self) -> tuple[int, int]:
        if self.state == "listening":
            return 352, 74
        if self.state in {"transcribing", "success", "error", "notice"}:
            return 304, 64
        return 264, 60

    def _work_area(self) -> tuple[int, int, int, int]:
        try:

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

            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            user32.MonitorFromWindow.restype = ctypes.c_void_p
            reference = user32.GetForegroundWindow()
            monitor = user32.MonitorFromWindow(reference, 2)
            info = MonitorInfo()
            info.size = ctypes.sizeof(MonitorInfo)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return (
                    info.work.left,
                    info.work.top,
                    info.work.right,
                    info.work.bottom,
                )
        except (AttributeError, OSError):
            pass
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def _position(self) -> None:
        width, height = self._dimensions()
        self.canvas.configure(width=width, height=height)
        left, top, right, bottom = self._work_area()
        x = max(left, right - width - 22)
        y = max(top, bottom - height - 22)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_snapshot(self, payload: dict[str, Any]) -> None:
        old_state = self.state
        self.state = str(payload.get("state", "idle"))
        self.detail = str(payload.get("detail", ""))
        self.hotkey = str(payload.get("hotkey_label", "Right Ctrl"))
        self.level = min(1.0, max(0.0, float(payload.get("level", 0.0))))
        self.recording_seconds = max(0.0, float(payload.get("recording_seconds", 0.0)))
        self.word_count = max(0, int(payload.get("word_count", 0)))
        self.pasted = payload.get("pasted")
        if self.state != old_state:
            self._position()
        self.dirty = True

    def _poll(self) -> None:
        if not self._parent_alive():
            self.root.destroy()
            return
        try:
            while self.connection.poll():
                payload = self.connection.recv()
                if payload.get("kind") == "shutdown":
                    self.root.destroy()
                    return
                if payload.get("kind") == "state":
                    self._apply_snapshot(payload["payload"])
        except (BrokenPipeError, EOFError, OSError, tk.TclError):
            self.root.destroy()
            return
        self.root.after(35, self._poll)

    def _base(self, width: int, height: int, border: str) -> None:
        _round_rect(
            self.canvas,
            3,
            5,
            width - 3,
            height - 2,
            19,
            fill="#080D12",
            outline="",
        )
        _round_rect(
            self.canvas,
            2,
            2,
            width - 4,
            height - 6,
            19,
            fill=COLORS["carbon_2"] if self.hovered else COLORS["carbon"],
            outline=border,
            width=1,
        )

    def _draw_idle(self, width: int, height: int) -> None:
        self._base(width, height, COLORS["carbon_border"])
        cx, cy = 30, (height - 4) / 2
        self.canvas.create_oval(
            cx - 15,
            cy - 15,
            cx + 15,
            cy + 15,
            outline=COLORS["success"],
            width=2,
        )
        self.canvas.create_oval(
            cx - 4,
            cy - 4,
            cx + 4,
            cy + 4,
            fill=COLORS["carbon_text"],
            outline="",
        )
        start, end = 52, 137
        for lane, offset in enumerate((-9, 0, 9)):
            points: list[float] = []
            for index in range(15):
                progress = index / 14
                x = start + (end - start) * progress
                y = cy + math.sin(progress * math.pi) * offset
                points.extend((x, y))
            color = COLORS["success"] if lane == 1 else "#667789"
            self.canvas.create_line(*points, fill=color, width=2, smooth=True)
            self.canvas.create_oval(
                end - 2,
                cy + offset - 2,
                end + 2,
                cy + offset + 2,
                fill=color,
                outline="",
            )
        self.canvas.create_text(
            154,
            22,
            anchor="w",
            text="Ready",
            fill=COLORS["carbon_text"],
            font=(FONT_UI, 9, "bold"),
        )
        self.canvas.create_text(
            154,
            42,
            anchor="w",
            text=f"Hold {self.hotkey}",
            fill=COLORS["carbon_muted"],
            font=(FONT_UI, 8),
        )

    def _draw_listening(self, width: int, height: int) -> None:
        self._base(width, height, COLORS["accent"])
        cy = (height - 4) / 2
        energy = 0.15 + self.visual_level * 0.85
        pulse = 2.5 + energy * 4.5 + math.sin(self.phase * 0.8) * 1.2
        self.canvas.create_oval(
            29 - 17 - pulse,
            cy - 17 - pulse,
            29 + 17 + pulse,
            cy + 17 + pulse,
            outline="#405B84",
            width=1,
        )
        self.canvas.create_oval(
            14,
            cy - 15,
            44,
            cy + 15,
            outline="#6D94F4",
            width=2,
        )
        self.canvas.create_oval(24, cy - 5, 34, cy + 5, fill="#FFFFFF", outline="")
        elapsed = int(self.recording_seconds)
        self.canvas.create_text(
            55,
            27,
            anchor="w",
            text=f"Listening  {elapsed // 60}:{elapsed % 60:02d}",
            fill="#FFFFFF",
            font=(FONT_UI, 10, "bold"),
        )
        self.canvas.create_text(
            55,
            49,
            anchor="w",
            text=f"Release {self.hotkey}",
            fill=COLORS["carbon_muted"],
            font=(FONT_UI, 8),
        )

        start, end = 165, 286
        colors = ("#7DA2FF", "#FFFFFF", "#4BC4A2")
        for lane, lane_offset in enumerate((-11, 0, 11)):
            points: list[float] = []
            amplitude = (3.2 + self.visual_level * (8.5 + lane * 1.5)) * (
                0.82 if lane != 1 else 1.0
            )
            for index in range(29):
                progress = index / 28
                x = start + (end - start) * progress
                envelope = math.sin(math.pi * progress) ** 0.7
                primary = math.sin(self.phase * (1.25 + lane * 0.08) + index * 0.67)
                harmonic = math.sin(self.phase * 0.7 + index * 1.21 + lane) * 0.32
                wave = (primary + harmonic) * amplitude * envelope
                points.extend((x, cy + lane_offset * 0.42 + wave))
            self.canvas.create_line(
                *points,
                fill=colors[lane],
                width=2 if lane != 1 else 3,
                smooth=True,
                splinesteps=18,
            )
            travel = (self.phase * (0.045 + lane * 0.004) + lane * 0.26) % 1.0
            dot_x = start + (end - start) * travel
            dot_y = cy + lane_offset * 0.42
            radius = 2.2 + self.peak_level * 1.7
            self.canvas.create_oval(
                dot_x - radius,
                dot_y - radius,
                dot_x + radius,
                dot_y + radius,
                fill=colors[lane],
                outline="",
            )

        _round_rect(
            self.canvas,
            299,
            20,
            338,
            52,
            10,
            fill="#253344",
            outline="#43566A",
        )
        self.canvas.create_text(
            318,
            36,
            text="LET GO",
            fill="#FFFFFF",
            font=(FONT_MONO, 6, "bold"),
        )

    def _draw_compact(self, width: int, height: int) -> None:
        states = {
            "transcribing": (
                COLORS["accent"],
                "Processing",
                "Turning speech into text",
            ),
            "success": (
                COLORS["success"],
                "Pasted" if self.pasted else "Transcript ready",
                f"{self.word_count} word{'s' if self.word_count != 1 else ''} saved",
            ),
            "error": (
                COLORS["danger"],
                "Needs attention",
                self.detail or "Open AgentWisper",
            ),
            "notice": (
                COLORS["success"],
                "Running in background",
                self.detail or f"Hold {self.hotkey} to dictate",
            ),
        }
        color, title, subtitle = states[self.state]
        if len(subtitle) > 34:
            subtitle = subtitle[:31] + "..."
        self._base(width, height, color)
        cx, cy = 30, (height - 4) / 2
        if self.state == "transcribing":
            for index in range(4):
                angle = self.phase + index * (math.tau / 4)
                x = cx + math.cos(angle) * 12
                y = cy + math.sin(angle) * 12
                radius = 2 + (index % 2)
                self.canvas.create_oval(
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius,
                    fill=("#7DA2FF", "#FFFFFF", "#4BC4A2", "#5B84F2")[index],
                    outline="",
                )
        elif self.state in {"success", "notice"}:
            self.canvas.create_oval(
                cx - 14,
                cy - 14,
                cx + 14,
                cy + 14,
                fill=COLORS["success"],
                outline="",
            )
            self.canvas.create_line(
                cx - 7,
                cy,
                cx - 1,
                cy + 6,
                cx + 9,
                cy - 7,
                fill="#FFFFFF",
                width=3,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
        else:
            self.canvas.create_oval(
                cx - 14,
                cy - 14,
                cx + 14,
                cy + 14,
                fill=COLORS["danger"],
                outline="",
            )
            self.canvas.create_text(
                cx,
                cy,
                text="!",
                fill="#FFFFFF",
                font=(FONT_UI, 12, "bold"),
            )
        self.canvas.create_text(
            56,
            24,
            anchor="w",
            text=title,
            fill="#FFFFFF",
            font=(FONT_UI, 9, "bold"),
        )
        self.canvas.create_text(
            56,
            44,
            anchor="w",
            text=subtitle,
            fill=COLORS["carbon_muted"],
            font=(FONT_UI, 8),
        )

    def _tick(self) -> None:
        animated = self.state in {"listening", "transcribing"}
        if animated:
            self.phase += 0.22
            self.visual_level += (self.level - self.visual_level) * 0.24
            self.peak_level = max(self.visual_level, self.peak_level * 0.93)
        else:
            self.visual_level *= 0.82
            self.peak_level *= 0.86
        if animated or self.dirty:
            width, height = self._dimensions()
            self.canvas.delete("all")
            if self.state == "idle":
                self._draw_idle(width, height)
            elif self.state == "listening":
                self._draw_listening(width, height)
            else:
                self._draw_compact(width, height)
            self.dirty = False
        self.root.after(45 if animated else 220, self._tick)

    def run(self) -> None:
        self.root.mainloop()
        if self.parent_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.parent_handle)
            except (AttributeError, OSError):
                pass


def run_signal_node(connection: Connection, parent_pid: int) -> None:
    SignalNode(connection, parent_pid).run()


class OverlayProcess:
    """Owns the native transparent Signal Node and its duplex command pipe."""

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
