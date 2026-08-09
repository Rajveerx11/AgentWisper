"""AgentWisper desktop interface.

THESIS: Dictation is a visible route from microphone to model to cursor; this
surface rejects the generic dark card dashboard and giant microphone button.
OWN-WORLD: Mineral-gray work surface, paper-white content, navy ink, cobalt
interaction, jade success, and a carbon floating Signal Node.
STORY: Confirm privacy, invoke speech, watch the signal move, receive technical
text, and recover it from history.
FIRST VIEWPORT: Compact brand navigation frames one signal stage, one
latest-transcript surface, and one clear action.
FORM: Focused command surface, patch-bay direction 4, seed c63dcfa6.
"""

from __future__ import annotations

import ctypes
import math
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import ClassVar

import pyperclip

from agent_whisper.app import _paste_text
from agent_whisper.audio import AudioRecorder, list_input_devices
from agent_whisper.config import MODEL_FILES, discover_model_dir
from agent_whisper.hotkeys import (
    HOTKEY_CHOICES,
    ShortcutListener,
    hotkey_label,
    normalize_hotkey,
)
from agent_whisper.providers import (
    GROQ_MODELS,
    CloudTranscriber,
    LocalTranscriberPool,
    ProviderRequest,
    validate_base_url,
)
from agent_whisper.storage import (
    HistoryItem,
    HistoryStore,
    SecretStore,
    SettingsStore,
    UserSettings,
)
from agent_whisper.vocabulary import TECHNICAL_TERMS, CorrectionEngine

COLORS = {
    "window": "#F3F5F7",
    "surface": "#FFFFFF",
    "surface_alt": "#EDF1F5",
    "nav": "#F8FAFB",
    "border": "#D8E0E7",
    "border_strong": "#BBC7D3",
    "ink": "#111C2E",
    "text": "#263548",
    "muted": "#647386",
    "faint": "#647386",
    "accent": "#2F67E8",
    "accent_hover": "#2454C5",
    "accent_soft": "#E8EFFF",
    "success": "#087456",
    "success_soft": "#E5F5EF",
    "danger": "#B63A50",
    "danger_soft": "#FCEBED",
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


def _label(
    parent: tk.Misc,
    text: str,
    size: int = 10,
    color: str | None = None,
    weight: str = "normal",
    font: str = FONT_UI,
    **kwargs,
) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        bg=parent.cget("bg"),
        fg=color or COLORS["text"],
        font=(font, size, weight),
        bd=0,
        **kwargs,
    )


def _surface(parent: tk.Misc, **kwargs) -> tk.Frame:
    return tk.Frame(
        parent,
        bg=COLORS["surface"],
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        bd=0,
        **kwargs,
    )


def _round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    **kwargs,
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


class FlatButton(tk.Button):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        variant: str = "secondary",
        compact: bool = False,
        **kwargs,
    ) -> None:
        palette = {
            "primary": (COLORS["accent"], "#FFFFFF", COLORS["accent_hover"]),
            "secondary": (COLORS["surface_alt"], COLORS["ink"], "#E2E8EE"),
            "quiet": (parent.cget("bg"), COLORS["muted"], COLORS["surface_alt"]),
            "danger": (COLORS["danger_soft"], COLORS["danger"], "#F8DDE1"),
        }
        background, foreground, active = palette[variant]
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=active,
            activeforeground=foreground,
            disabledforeground=COLORS["faint"],
            relief="flat",
            bd=0,
            cursor="hand2",
            font=(FONT_UI, 9 if compact else 10, "bold"),
            padx=11 if compact else 18,
            pady=6 if compact else 10,
            highlightthickness=2,
            highlightbackground=background,
            highlightcolor=COLORS["accent"],
            takefocus=True,
            **kwargs,
        )


class BrandMark(tk.Canvas):
    def __init__(self, parent: tk.Misc, size: int = 30) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=parent.cget("bg"),
            bd=0,
            highlightthickness=0,
        )
        self.create_oval(1, 1, size - 1, size - 1, fill=COLORS["ink"], outline="")
        self.create_line(
            8, 16, 13, 10, 18, 20, 23, 13, fill="#FFFFFF", width=2, smooth=True
        )
        for x, y in ((8, 16), (13, 10), (18, 20), (23, 13)):
            self.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#7DA2FF", outline="")


class SignalStage(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        command: Callable[[], None],
        level_getter: Callable[[], float],
    ) -> None:
        super().__init__(
            parent,
            height=172,
            bg=COLORS["surface"],
            bd=0,
            highlightthickness=2,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            cursor="hand2",
            takefocus=1,
        )
        self.command = command
        self.level_getter = level_getter
        self.state = "idle"
        self._paste_target_hwnd: int | None = None
        self.provider = "Local Parakeet"
        self.phase = 0.0
        self.bind("<Button-1>", self._invoke)
        self.bind("<Return>", self._invoke)
        self.bind("<space>", self._invoke)
        self.bind("<Configure>", lambda _event: self._draw())
        self._animate()

    def _invoke(self, _event=None) -> str:
        self.focus_set()
        self.command()
        return "break"

    def set_state(self, state: str) -> None:
        self.state = state
        self._draw()

    def set_provider(self, provider: str) -> None:
        self.provider = provider
        self._draw()

    def _signal_points(
        self, start: float, end: float, y: float, amplitude: float
    ) -> list[float]:
        points: list[float] = []
        steps = 32
        for index in range(steps + 1):
            progress = index / steps
            x = start + (end - start) * progress
            envelope = math.sin(math.pi * progress)
            offset = math.sin(self.phase + index * 0.72) * amplitude * envelope
            points.extend((x, y + offset))
        return points

    def _node(self, x: float, y: float, label: str, kind: str, active: bool) -> None:
        ring = COLORS["accent"] if active else COLORS["border_strong"]
        fill = COLORS["accent_soft"] if active else COLORS["surface_alt"]
        self.create_oval(
            x - 24, y - 24, x + 24, y + 24, fill=fill, outline=ring, width=2
        )
        if kind == "mic":
            self.create_line(x, y - 11, x, y + 5, fill=ring, width=4, capstyle=tk.ROUND)
            self.create_arc(
                x - 10,
                y - 5,
                x + 10,
                y + 12,
                start=180,
                extent=180,
                style=tk.ARC,
                outline=ring,
                width=2,
            )
            self.create_line(x, y + 12, x, y + 17, fill=ring, width=2)
        elif kind == "model":
            self.create_rectangle(x - 10, y - 10, x + 10, y + 10, outline=ring, width=2)
            self.create_text(x, y, text="AI", fill=ring, font=(FONT_MONO, 7, "bold"))
            for offset in (-7, 0, 7):
                self.create_line(
                    x - 15, y + offset, x - 11, y + offset, fill=ring, width=1
                )
                self.create_line(
                    x + 11, y + offset, x + 15, y + offset, fill=ring, width=1
                )
        else:
            self.create_polygon(
                x - 7,
                y - 12,
                x + 11,
                y,
                x + 2,
                y + 2,
                x + 7,
                y + 12,
                x + 2,
                y + 14,
                x - 3,
                y + 4,
                x - 9,
                y + 9,
                fill=ring,
                outline="",
            )
        self.create_text(
            x, y + 39, text=label, fill=COLORS["text"], font=(FONT_UI, 9, "bold")
        )

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 640)
        y = 83
        x1, x2, x3 = 84, width / 2, width - 84
        statuses = {
            "idle": ("Ready", COLORS["success"]),
            "listening": ("Listening", COLORS["accent"]),
            "transcribing": ("Processing", COLORS["warning"]),
            "success": ("Complete", COLORS["success"]),
            "error": ("Needs attention", COLORS["danger"]),
        }
        status, status_color = statuses.get(self.state, statuses["idle"])
        self.create_oval(20, 17, 28, 25, fill=status_color, outline="")
        self.create_text(
            36,
            21,
            anchor="w",
            text=status,
            fill=COLORS["ink"],
            font=(FONT_UI, 9, "bold"),
        )
        self.create_text(
            width - 20,
            21,
            anchor="e",
            text=self.provider,
            fill=COLORS["muted"],
            font=(FONT_UI, 9),
        )

        self.create_line(x1 + 24, y, x3 - 24, y, fill=COLORS["border"], width=2)
        level = min(1.0, self.level_getter()) if self.state == "listening" else 0.0
        if self.state == "listening":
            points = self._signal_points(x1 + 24, x2 - 24, y, 5 + level * 18)
            self.create_line(*points, fill=COLORS["accent"], width=3, smooth=True)
        elif self.state == "transcribing":
            self.create_line(x1 + 24, y, x2 - 24, y, fill=COLORS["success"], width=3)
            progress = (math.sin(self.phase * 0.7) + 1) / 2
            dot_x = x2 + 24 + (x3 - x2 - 48) * progress
            self.create_line(
                x2 + 24, y, x3 - 24, y, fill=COLORS["accent_soft"], width=4
            )
            self.create_oval(
                dot_x - 4, y - 4, dot_x + 4, y + 4, fill=COLORS["accent"], outline=""
            )
        else:
            route_color = (
                COLORS["success"] if self.state == "success" else COLORS["accent"]
            )
            if self.state == "error":
                route_color = COLORS["danger"]
            self.create_line(x1 + 24, y, x3 - 24, y, fill=route_color, width=2)
            for progress in (0.22, 0.78):
                dot_x = x1 + 24 + (x3 - x1 - 48) * progress
                self.create_oval(
                    dot_x - 3, y - 3, dot_x + 3, y + 3, fill=route_color, outline=""
                )

        self._node(x1, y, "Microphone", "mic", self.state == "listening")
        self._node(x2, y, self.provider, "model", self.state == "transcribing")
        self._node(x3, y, "Active cursor", "cursor", self.state == "success")

    def _animate(self) -> None:
        self.phase += 0.24
        if self.state in {"listening", "transcribing"}:
            self._draw()
        self.after(55, self._animate)


class SignalNodeOverlay:
    def __init__(
        self,
        root: tk.Tk,
        level_getter: Callable[[], float],
        hotkey_getter: Callable[[], str],
        toggle_command: Callable[[], None],
        open_command: Callable[[], None],
    ) -> None:
        self.root = root
        self.level_getter = level_getter
        self.hotkey_getter = hotkey_getter
        self.toggle_command = toggle_command
        self.open_command = open_command
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.98)
        self.window.configure(bg=COLORS["transparent"])
        try:
            self.window.wm_attributes("-transparentcolor", COLORS["transparent"])
            canvas_background = COLORS["transparent"]
        except tk.TclError:
            self.window.configure(bg=COLORS["carbon"])
            canvas_background = COLORS["carbon"]
        self.canvas = tk.Canvas(
            self.window,
            bg=canvas_background,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", lambda _event: self.toggle_command())
        self.canvas.bind("<Button-3>", lambda _event: self.open_command())
        self.canvas.bind("<Enter>", lambda _event: self._set_hover(True))
        self.canvas.bind("<Leave>", lambda _event: self._set_hover(False))
        self.state = "idle"
        self.message = ""
        self.phase = 0.0
        self.hovered = False
        self._dirty = True
        self._revert_job: str | None = None
        self.window.update_idletasks()
        self._make_nonactivating()
        self._tick()

    def _set_hover(self, hovered: bool) -> None:
        self.hovered = hovered
        self._dirty = True

    def _native_handle(self) -> int:
        handle = int(self.window.winfo_id())
        parent = int(ctypes.windll.user32.GetParent(handle))
        return parent or handle

    def _make_nonactivating(self) -> None:
        """Keep the Signal Node above apps without stealing the typing target."""
        try:
            handle = self._native_handle()
            style = ctypes.windll.user32.GetWindowLongW(handle, -20)
            ctypes.windll.user32.SetWindowLongW(
                handle,
                -20,
                style | 0x08000000 | 0x00000080,  # NOACTIVATE | TOOLWINDOW
            )
        except (AttributeError, OSError, tk.TclError):
            pass

    def _dimensions(self) -> tuple[int, int]:
        if self.state == "listening":
            return 318, 70
        if self.state in {"transcribing", "success", "error"}:
            return 278, 62
        return 248, 58

    def _position(self) -> None:
        width, height = self._dimensions()
        self.canvas.configure(width=width, height=height)
        left, top, right, bottom = self._work_area()
        x = max(left, right - width - 22)
        y = max(top, bottom - height - 22)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _work_area(self) -> tuple[int, int, int, int]:
        """Return the active monitor work area, excluding its taskbar."""
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

            reference = ctypes.windll.user32.GetForegroundWindow()
            monitor = ctypes.windll.user32.MonitorFromWindow(reference, 2)
            info = MonitorInfo()
            info.size = ctypes.sizeof(MonitorInfo)
            if ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return (
                    info.work.left,
                    info.work.top,
                    info.work.right,
                    info.work.bottom,
                )
        except (AttributeError, OSError):
            pass
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def show(self, state: str, message: str = "") -> None:
        self.state = state
        self.message = message
        if self._revert_job:
            self.window.after_cancel(self._revert_job)
            self._revert_job = None
        self._dirty = True
        self._position()
        self.window.deiconify()
        self._make_nonactivating()
        try:
            ctypes.windll.user32.SetWindowPos(
                self._native_handle(), -1, 0, 0, 0, 0, 0x0013
            )  # NOSIZE | NOMOVE | NOACTIVATE
        except (AttributeError, OSError, tk.TclError):
            self.window.lift()

    def success(self, words: int, pasted: bool) -> None:
        message = (
            f"Pasted {words} word{'s' if words != 1 else ''}"
            if pasted
            else f"{words} word{'s' if words != 1 else ''} ready"
        )
        self.show("success", message)
        self._revert_job = self.window.after(1800, lambda: self.show("idle"))

    def error(self, message: str) -> None:
        short = message if len(message) <= 34 else message[:31] + "..."
        self.show("error", short)
        self._revert_job = self.window.after(2800, lambda: self.show("idle"))

    def destroy(self) -> None:
        self.window.destroy()

    def _base(self, width: int, height: int, border: str) -> None:
        _round_rect(
            self.canvas,
            3,
            5,
            width - 3,
            height - 2,
            18,
            fill="#080D12",
            outline="",
        )
        _round_rect(
            self.canvas,
            2,
            2,
            width - 4,
            height - 6,
            18,
            fill=COLORS["carbon_2"] if self.hovered else COLORS["carbon"],
            outline=border,
            width=1,
        )

    def _draw_idle(self, width: int, height: int) -> None:
        self._base(width, height, COLORS["carbon_border"])
        cx, cy = 29, (height - 4) / 2
        self.canvas.create_oval(
            cx - 15, cy - 15, cx + 15, cy + 15, outline=COLORS["success"], width=2
        )
        self.canvas.create_oval(
            cx - 4, cy - 4, cx + 4, cy + 4, fill=COLORS["carbon_text"], outline=""
        )
        start, end = 49, 133
        for lane, offset in enumerate((-9, 0, 9)):
            points: list[float] = []
            for index in range(13):
                progress = index / 12
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
            151,
            21,
            anchor="w",
            text="Ready",
            fill=COLORS["carbon_text"],
            font=(FONT_UI, 9, "bold"),
        )
        self.canvas.create_text(
            151,
            39,
            anchor="w",
            text=hotkey_label(self.hotkey_getter()),
            fill=COLORS["carbon_muted"],
            font=(FONT_UI, 8),
        )

    def _draw_listening(self, width: int, height: int) -> None:
        self._base(width, height, COLORS["accent"])
        cy = (height - 4) / 2
        pulse = 2 + (math.sin(self.phase) + 1) * 2
        self.canvas.create_oval(
            17 - pulse,
            cy - 13 - pulse,
            43 + pulse,
            cy + 13 + pulse,
            outline="#5B84F2",
            width=2,
        )
        self.canvas.create_oval(25, cy - 5, 35, cy + 5, fill="#FFFFFF", outline="")
        self.canvas.create_text(
            55,
            25,
            anchor="w",
            text="Listening",
            fill="#FFFFFF",
            font=(FONT_UI, 10, "bold"),
        )
        self.canvas.create_text(
            55,
            45,
            anchor="w",
            text="Speak naturally",
            fill=COLORS["carbon_muted"],
            font=(FONT_UI, 8),
        )
        level = min(1.0, self.level_getter())
        start, end = 143, 235
        for lane, offset in enumerate((-10, 0, 10)):
            points: list[float] = []
            for index in range(18):
                progress = index / 17
                x = start + (end - start) * progress
                envelope = math.sin(math.pi * progress)
                wave = math.sin(self.phase * 1.4 + index * 0.72 + lane) * (
                    3 + level * 8
                )
                points.extend((x, cy + offset * 0.45 + wave * envelope))
            color = ("#7DA2FF", "#FFFFFF", "#4BC4A2")[lane]
            self.canvas.create_line(*points, fill=color, width=2, smooth=True)
        _round_rect(
            self.canvas, 252, 18, 300, 49, 10, fill="#253344", outline="#3D4C5D"
        )
        self.canvas.create_text(
            276, 33, text="STOP", fill="#FFFFFF", font=(FONT_MONO, 7, "bold")
        )

    def _draw_compact_state(self, width: int, height: int) -> None:
        colors = {
            "transcribing": (
                COLORS["accent"],
                "Processing",
                "Turning speech into text",
            ),
            "success": (
                COLORS["success"],
                "Complete",
                self.message or "Transcript pasted",
            ),
            "error": (
                COLORS["danger"],
                "Could not transcribe",
                self.message or "Open AgentWisper",
            ),
        }
        color, title, subtitle = colors[self.state]
        self._base(width, height, color)
        cx, cy = 29, (height - 4) / 2
        if self.state == "transcribing":
            for index in range(3):
                angle = self.phase + index * (math.tau / 3)
                x = cx + math.cos(angle) * 11
                y = cy + math.sin(angle) * 11
                self.canvas.create_oval(
                    x - 3, y - 3, x + 3, y + 3, fill=color, outline=""
                )
        elif self.state == "success":
            self.canvas.create_oval(
                cx - 14, cy - 14, cx + 14, cy + 14, fill=COLORS["success"], outline=""
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
                cx - 14, cy - 14, cx + 14, cy + 14, fill=COLORS["danger"], outline=""
            )
            self.canvas.create_text(
                cx, cy, text="!", fill="#FFFFFF", font=(FONT_UI, 12, "bold")
            )
        self.canvas.create_text(
            55, 23, anchor="w", text=title, fill="#FFFFFF", font=(FONT_UI, 9, "bold")
        )
        self.canvas.create_text(
            55,
            41,
            anchor="w",
            text=subtitle,
            fill=COLORS["carbon_muted"],
            font=(FONT_UI, 8),
        )
        self.canvas.create_text(
            width - 18,
            cy,
            anchor="e",
            text="AgentWisper",
            fill=COLORS["carbon_muted"],
            font=(FONT_MONO, 7),
        )

    def _tick(self) -> None:
        animated = self.state in {"listening", "transcribing"}
        if animated:
            self.phase += 0.18
        if animated or self._dirty:
            width, height = self._dimensions()
            self.canvas.delete("all")
            if self.state == "idle":
                self._draw_idle(width, height)
            elif self.state == "listening":
                self._draw_listening(width, height)
            else:
                self._draw_compact_state(width, height)
            self._dirty = False
        self.window.after(55 if animated else 250, self._tick)


class HomePage(tk.Frame):
    def __init__(self, parent: tk.Misc, app: AgentWisperApp) -> None:
        super().__init__(parent, bg=COLORS["window"])
        self.app = app
        self.latest_is_placeholder = True
        self.current_state = "idle"

        header = tk.Frame(self, bg=COLORS["window"])
        header.pack(fill="x", padx=34, pady=(28, 16))
        title_group = tk.Frame(header, bg=COLORS["window"])
        title_group.pack(side="left")
        _label(title_group, "Dictation workspace", 22, COLORS["ink"], "bold").pack(
            anchor="w"
        )
        _label(
            title_group,
            "Route speech through your chosen model and into the active cursor.",
            10,
            COLORS["muted"],
        ).pack(anchor="w", pady=(4, 0))
        self.privacy_badge = _label(
            header,
            "Audio stays on this PC",
            9,
            COLORS["success"],
            "bold",
        )
        self.privacy_badge.pack(side="right", pady=10)

        self.signal = SignalStage(
            self, app.toggle_recording, lambda: app.recorder.level
        )
        self.signal.pack(fill="x", padx=34, pady=(0, 12))

        action = tk.Frame(self, bg=COLORS["window"])
        action.pack(fill="x", padx=34, pady=(0, 18))
        status_group = tk.Frame(action, bg=COLORS["window"])
        status_group.pack(side="left", fill="x", expand=True)
        self.status = _label(
            status_group,
            f"Ready - press {hotkey_label(app.settings.hotkey)}",
            10,
            COLORS["ink"],
            "bold",
        )
        self.status.pack(anchor="w")
        self.status_detail = _label(
            status_group,
            "Click the signal path or use the hotkey to begin.",
            9,
            COLORS["muted"],
        )
        self.status_detail.pack(anchor="w", pady=(3, 0))
        self.action_button = FlatButton(
            action, "Start dictation", app.toggle_recording, "primary"
        )
        self.action_button.pack(side="right")

        transcript = _surface(self)
        transcript.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        transcript_header = tk.Frame(transcript, bg=COLORS["surface"])
        transcript_header.pack(fill="x", padx=20, pady=(17, 10))
        _label(transcript_header, "Latest transcript", 11, COLORS["ink"], "bold").pack(
            side="left"
        )
        self.word_count = _label(
            transcript_header, "", 8, COLORS["faint"], font=FONT_MONO
        )
        self.word_count.pack(side="left", padx=(12, 0))
        self.copy_button = FlatButton(
            transcript_header, "Copy", self.copy_latest, "quiet", compact=True
        )
        self.copy_button.pack(side="right")
        tk.Frame(transcript, height=1, bg=COLORS["border"]).pack(fill="x")
        self.transcript = tk.Text(
            transcript,
            height=8,
            wrap="word",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["accent_soft"],
            selectforeground=COLORS["ink"],
            relief="flat",
            bd=0,
            font=(FONT_UI, 12),
            padx=20,
            pady=18,
            spacing1=2,
            spacing3=4,
        )
        self.transcript.pack(fill="both", expand=True)
        self.set_transcript(
            "Your latest transcript will appear here. It is also saved to local history.",
            placeholder=True,
        )

    def set_state(
        self, state: str, detail: str = "", pasted: bool | None = None
    ) -> None:
        self.current_state = state
        self.signal.set_state(state)
        labels = {
            "idle": f"Ready - press {hotkey_label(self.app.settings.hotkey)}",
            "listening": "Listening",
            "transcribing": "Processing your speech",
            "success": "Transcript pasted" if pasted else "Transcript ready",
            "error": "Could not transcribe",
        }
        defaults = {
            "idle": "Click the signal path or use the hotkey to begin.",
            "listening": "Press the hotkey again when you finish speaking.",
            "transcribing": "Your selected provider is turning audio into text.",
            "success": "The result is saved locally in History.",
            "error": "Check the message, then try again.",
        }
        buttons = {
            "idle": ("Start dictation", "normal"),
            "listening": ("Finish & transcribe", "normal"),
            "transcribing": ("Processing...", "disabled"),
            "success": ("Start dictation", "normal"),
            "error": ("Try again", "normal"),
        }
        self.status.config(text=labels.get(state, state.title()))
        self.status_detail.config(text=detail or defaults.get(state, ""))
        button_text, button_state = buttons.get(state, buttons["idle"])
        self.action_button.config(text=button_text, state=button_state)

    def set_provider(self, provider: str, model: str) -> None:
        provider_name = {
            "local": "Local Parakeet",
            "groq": "Groq",
            "custom": "Custom cloud",
        }.get(provider, provider)
        self.signal.set_provider(provider_name)
        local = provider == "local"
        self.privacy_badge.config(
            text="Audio stays on this PC"
            if local
            else f"Audio sent to {provider_name}",
            fg=COLORS["success"] if local else COLORS["warning"],
        )

    def set_transcript(self, text: str, placeholder: bool = False) -> None:
        self.latest_is_placeholder = placeholder
        self.transcript.config(
            state="normal", fg=COLORS["faint"] if placeholder else COLORS["text"]
        )
        self.transcript.delete("1.0", "end")
        self.transcript.insert("1.0", text)
        self.transcript.config(state="disabled")
        self.word_count.config(text="" if placeholder else f"{len(text.split())} words")
        self.copy_button.config(state="disabled" if placeholder else "normal")

    def copy_latest(self) -> None:
        if not self.latest_is_placeholder:
            pyperclip.copy(self.transcript.get("1.0", "end").strip())


class HistoryPage(tk.Frame):
    def __init__(self, parent: tk.Misc, app: AgentWisperApp) -> None:
        super().__init__(parent, bg=COLORS["window"])
        self.app = app
        header = tk.Frame(self, bg=COLORS["window"])
        header.pack(fill="x", padx=34, pady=(28, 16))
        title_group = tk.Frame(header, bg=COLORS["window"])
        title_group.pack(side="left")
        _label(title_group, "Transcript history", 22, COLORS["ink"], "bold").pack(
            anchor="w"
        )
        self.subtitle = _label(
            title_group, "Stored only on this PC.", 10, COLORS["muted"]
        )
        self.subtitle.pack(anchor="w", pady=(4, 0))
        FlatButton(
            header, "Clear history", self.clear_history, "danger", compact=True
        ).pack(side="right", pady=8)

        container = _surface(self)
        container.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        self.canvas = tk.Canvas(
            container, bg=COLORS["surface"], bd=0, highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=self.canvas.yview
        )
        self.list_frame = tk.Frame(self.canvas, bg=COLORS["surface"])
        self.list_window = self.canvas.create_window(
            (0, 0), window=self.list_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.list_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(
                self.list_window, width=event.width
            ),
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._scroll)

    def _scroll(self, event) -> None:
        if self.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    @staticmethod
    def _date_parts(value: str) -> tuple[str, str]:
        try:
            moment = datetime.fromisoformat(value).astimezone()
            today = datetime.now().astimezone().date()
            if moment.date() == today:
                day = "Today"
            elif (today - moment.date()).days == 1:
                day = "Yesterday"
            else:
                day = moment.strftime("%d %B %Y")
            return day, moment.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            return "Earlier", value

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        items = self.app.history_store.list()
        self.subtitle.config(
            text=f"{len(items)} local transcript{'s' if len(items) != 1 else ''}."
        )
        if not items:
            empty = tk.Frame(self.list_frame, bg=COLORS["surface"])
            empty.pack(fill="both", expand=True, pady=90)
            _label(empty, "No transcripts yet", 15, COLORS["ink"], "bold").pack()
            _label(
                empty,
                f"Use {hotkey_label(self.app.settings.hotkey)} once to begin dictating.",
                10,
                COLORS["muted"],
            ).pack(pady=(7, 0))
            return
        current_day = ""
        for item in items:
            day, time_text = self._date_parts(item.created_at)
            if day != current_day:
                _label(self.list_frame, day, 10, COLORS["ink"], "bold").pack(
                    anchor="w", padx=20, pady=(20, 8)
                )
                current_day = day
            self._item(item, time_text)

    def _item(self, item: HistoryItem, time_text: str) -> None:
        row = tk.Frame(self.list_frame, bg=COLORS["surface"])
        row.pack(fill="x", padx=20)
        meta = tk.Frame(row, bg=COLORS["surface"], width=128)
        meta.pack(side="left", fill="y", pady=13)
        meta.pack_propagate(False)
        _label(meta, time_text, 9, COLORS["muted"]).pack(anchor="w")
        _label(meta, item.provider.title(), 8, COLORS["faint"], font=FONT_MONO).pack(
            anchor="w", pady=(4, 0)
        )
        _label(
            row,
            item.text,
            10,
            COLORS["text"],
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True, pady=13)
        FlatButton(
            row,
            "Copy",
            lambda text=item.text: pyperclip.copy(text),
            "quiet",
            compact=True,
        ).pack(side="right", padx=(12, 0), pady=10)
        tk.Frame(self.list_frame, bg=COLORS["border"], height=1).pack(fill="x", padx=20)

    def clear_history(self) -> None:
        if messagebox.askyesno(
            "Clear history", "Delete all transcript history stored on this PC?"
        ):
            self.app.history_store.clear()
            self.refresh()


class SettingsPage(tk.Frame):
    PROVIDERS: ClassVar[dict[str, str]] = {
        "Local Parakeet - private": "local",
        "Groq Cloud": "groq",
        "Custom OpenAI-compatible": "custom",
    }

    def __init__(self, parent: tk.Misc, app: AgentWisperApp) -> None:
        super().__init__(parent, bg=COLORS["window"])
        self.app = app
        self.provider_display = tk.StringVar()
        self.groq_model = tk.StringVar()
        self.custom_url = tk.StringVar()
        self.custom_model = tk.StringVar()
        self.hotkey = tk.StringVar()
        self.language = tk.StringVar()
        self.local_model = tk.StringVar()
        self.device_display = tk.StringVar()
        self.paste_result = tk.BooleanVar()
        self.restore_clipboard = tk.BooleanVar()
        self._device_values: dict[str, int | None] = {"System default": None}

        header = tk.Frame(self, bg=COLORS["window"])
        header.pack(fill="x", padx=34, pady=(28, 16))
        _label(header, "Settings", 22, COLORS["ink"], "bold").pack(anchor="w")
        _label(
            header,
            "Provider, input, and paste behavior. Nothing else.",
            10,
            COLORS["muted"],
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(self, bg=COLORS["window"])
        body.pack(fill="both", expand=True, padx=34)
        self.canvas = tk.Canvas(body, bg=COLORS["window"], bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, bg=COLORS["window"])
        content_window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.content.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(content_window, width=event.width),
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._scroll, add="+")

        self._provider_section()
        self._input_section()

        footer = tk.Frame(
            self,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        footer.pack(fill="x", side="bottom")
        self.save_status = _label(
            footer, "Changes stay on this PC.", 9, COLORS["muted"]
        )
        self.save_status.pack(side="left", padx=34, pady=14)
        FlatButton(footer, "Save settings", self.save, "primary").pack(
            side="right", padx=34, pady=10
        )
        self.load()

    def _scroll(self, event) -> None:
        if self.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _section(self, title: str, description: str) -> tk.Frame:
        section = _surface(self.content)
        section.pack(fill="x", pady=(0, 12))
        heading = tk.Frame(section, bg=COLORS["surface"])
        heading.pack(fill="x", padx=20, pady=(18, 14))
        _label(heading, title, 12, COLORS["ink"], "bold").pack(anchor="w")
        _label(
            heading, description, 9, COLORS["muted"], wraplength=680, justify="left"
        ).pack(anchor="w", pady=(4, 0))
        tk.Frame(section, height=1, bg=COLORS["border"]).pack(fill="x")
        content = tk.Frame(section, bg=COLORS["surface"])
        content.pack(fill="x", padx=20, pady=(4, 18))
        return content

    @staticmethod
    def _field_label(parent: tk.Misc, text: str) -> None:
        _label(parent, text, 9, COLORS["text"], "bold").pack(anchor="w", pady=(13, 6))

    @staticmethod
    def _entry(parent: tk.Misc, variable: tk.StringVar, show: str = "") -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=variable,
            show=show,
            bg=COLORS["surface"],
            fg=COLORS["ink"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["accent_soft"],
            selectforeground=COLORS["ink"],
            relief="flat",
            bd=0,
            font=(FONT_UI, 10),
            highlightthickness=1,
            highlightbackground=COLORS["border_strong"],
            highlightcolor=COLORS["accent"],
        )

    def _provider_section(self) -> None:
        inside = self._section(
            "Transcription provider",
            "Local keeps audio on-device. Cloud sends only the current recording to the selected provider.",
        )
        self._field_label(inside, "Provider")
        combo = ttk.Combobox(
            inside,
            textvariable=self.provider_display,
            values=list(self.PROVIDERS),
            state="readonly",
        )
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda _event: self._show_provider_fields())

        self.local_fields = tk.Frame(inside, bg=COLORS["surface"])
        self._field_label(self.local_fields, "Detected model folder")
        self._entry(self.local_fields, self.local_model).pack(fill="x", ipady=8)
        _label(
            self.local_fields,
            "Parakeet runs locally through CPU ONNX inference.",
            9,
            COLORS["success"],
        ).pack(anchor="w", pady=(7, 0))

        self.groq_fields = tk.Frame(inside, bg=COLORS["surface"])
        self._field_label(self.groq_fields, "Groq model")
        ttk.Combobox(
            self.groq_fields,
            textvariable=self.groq_model,
            values=list(GROQ_MODELS),
            state="readonly",
        ).pack(fill="x")
        self._field_label(self.groq_fields, "Groq API key")
        self.groq_key = self._entry(self.groq_fields, tk.StringVar(), show="*")
        self.groq_key.pack(fill="x", ipady=8)
        self.groq_key_status = _label(self.groq_fields, "", 9, COLORS["muted"])
        self.groq_key_status.pack(anchor="w", pady=(7, 0))
        _label(
            self.groq_fields,
            "Encrypted with Windows DPAPI. Audio is sent to Groq only when selected.",
            9,
            COLORS["warning"],
            wraplength=680,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self.custom_fields = tk.Frame(inside, bg=COLORS["surface"])
        self._field_label(self.custom_fields, "API base URL")
        self._entry(self.custom_fields, self.custom_url).pack(fill="x", ipady=8)
        self._field_label(self.custom_fields, "Model ID")
        self._entry(self.custom_fields, self.custom_model).pack(fill="x", ipady=8)
        self._field_label(self.custom_fields, "API key")
        self.custom_key = self._entry(self.custom_fields, tk.StringVar(), show="*")
        self.custom_key.pack(fill="x", ipady=8)
        self.custom_key_status = _label(self.custom_fields, "", 9, COLORS["muted"])
        self.custom_key_status.pack(anchor="w", pady=(7, 0))
        _label(
            self.custom_fields,
            "HTTPS required. Plain HTTP is allowed only for localhost tools.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(6, 0))

    def _input_section(self) -> None:
        inside = self._section(
            "Input and paste",
            "Choose how AgentWisper starts, listens, and returns text.",
        )
        two = tk.Frame(inside, bg=COLORS["surface"])
        two.pack(fill="x")
        left = tk.Frame(two, bg=COLORS["surface"])
        right = tk.Frame(two, bg=COLORS["surface"])
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._field_label(left, "Global hotkey")
        ttk.Combobox(left, textvariable=self.hotkey, values=list(HOTKEY_CHOICES)).pack(
            fill="x"
        )
        self._field_label(right, "Language code")
        self._entry(right, self.language).pack(fill="x", ipady=8)

        self._field_label(inside, "Microphone")
        for index, name in list_input_devices():
            self._device_values[f"{index}: {name}"] = index
        ttk.Combobox(
            inside,
            textvariable=self.device_display,
            values=list(self._device_values),
            state="readonly",
        ).pack(fill="x")

        checks = tk.Frame(inside, bg=COLORS["surface"])
        checks.pack(fill="x", pady=(15, 0))
        for text, variable in (
            ("Paste transcript at the active cursor", self.paste_result),
            ("Restore previous clipboard text", self.restore_clipboard),
        ):
            tk.Checkbutton(
                checks,
                text=text,
                variable=variable,
                bg=COLORS["surface"],
                fg=COLORS["text"],
                activebackground=COLORS["surface"],
                activeforeground=COLORS["ink"],
                selectcolor=COLORS["surface"],
                font=(FONT_UI, 10),
                highlightthickness=2,
                highlightbackground=COLORS["surface"],
                highlightcolor=COLORS["accent"],
                cursor="hand2",
                takefocus=True,
            ).pack(anchor="w", pady=3)

    def _show_provider_fields(self) -> None:
        for frame in (self.local_fields, self.groq_fields, self.custom_fields):
            frame.pack_forget()
        provider = self.PROVIDERS.get(self.provider_display.get(), "local")
        {
            "local": self.local_fields,
            "groq": self.groq_fields,
            "custom": self.custom_fields,
        }[provider].pack(fill="x")

    def load(self) -> None:
        settings = self.app.settings
        reverse = {value: key for key, value in self.PROVIDERS.items()}
        self.provider_display.set(reverse.get(settings.provider, reverse["local"]))
        self.groq_model.set(settings.groq_model)
        self.custom_url.set(settings.custom_base_url)
        self.custom_model.set(settings.custom_model)
        self.hotkey.set(hotkey_label(settings.hotkey))
        self.language.set(settings.language)
        self.local_model.set(settings.local_model_dir)
        self.paste_result.set(settings.paste_result)
        self.restore_clipboard.set(settings.restore_clipboard)
        selected = next(
            (
                name
                for name, value in self._device_values.items()
                if value == settings.input_device
            ),
            "System default",
        )
        self.device_display.set(selected)
        self.groq_key_status.config(
            text="Encrypted key saved"
            if self.app.secret_store.has("groq_api_key")
            else "No saved key"
        )
        self.custom_key_status.config(
            text="Encrypted key saved"
            if self.app.secret_store.has("custom_api_key")
            else "No saved key"
        )
        self._show_provider_fields()

    def save(self) -> None:
        try:
            hotkey_value = normalize_hotkey(self.hotkey.get())
            provider = self.PROVIDERS[self.provider_display.get()]
            local_model = Path(self.local_model.get().strip())
            if provider == "local":
                missing = [
                    name for name in MODEL_FILES if not (local_model / name).is_file()
                ]
                if missing:
                    raise ValueError("Local model folder is incomplete")
            custom_url = self.custom_url.get().strip()
            if provider == "custom":
                custom_url = validate_base_url(custom_url)
                if not self.custom_model.get().strip():
                    raise ValueError("Enter a custom model ID")
            language = self.language.get().strip().lower()
            if language and (
                len(language) > 10 or not language.replace("-", "").isalpha()
            ):
                raise ValueError("Language must be an ISO code such as en or en-US")

            settings = UserSettings(
                provider=provider,
                hotkey=hotkey_value,
                input_device=self._device_values.get(self.device_display.get()),
                local_model_dir=str(local_model),
                groq_model=self.groq_model.get(),
                custom_base_url=custom_url,
                custom_model=self.custom_model.get().strip(),
                paste_result=self.paste_result.get(),
                restore_clipboard=self.restore_clipboard.get(),
                language=language,
                num_threads=self.app.settings.num_threads,
            )
            groq_value = self.groq_key.get()
            custom_value = self.custom_key.get()
            if groq_value:
                self.app.secret_store.set("groq_api_key", groq_value)
            if custom_value:
                self.app.secret_store.set("custom_api_key", custom_value)
            if provider == "groq" and not self.app.secret_store.has("groq_api_key"):
                raise ValueError("Enter a Groq API key")
            if provider == "custom" and not self.app.secret_store.has("custom_api_key"):
                raise ValueError("Enter an API key for the custom provider")
            self.app.apply_settings(settings)
            self.groq_key.delete(0, "end")
            self.custom_key.delete(0, "end")
            self.load()
            self.save_status.config(text="Settings saved", fg=COLORS["success"])
        except (ValueError, OSError) as exc:
            self.save_status.config(text=str(exc), fg=COLORS["danger"])


class AgentWisperApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AgentWisper")
        self.root.configure(bg=COLORS["window"])
        self.root.geometry("1120x760")
        self.root.minsize(940, 660)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.settings_store = SettingsStore()
        self.secret_store = SecretStore()
        self.history_store = HistoryStore()
        self.settings = self.settings_store.load()
        if not self.settings.local_model_dir:
            self.settings.local_model_dir = str(discover_model_dir())
            self.settings_store.save(self.settings)

        self.recorder = AudioRecorder(self.settings.input_device)
        self.local_pool = LocalTranscriberPool()
        self.cloud = CloudTranscriber()
        self.corrections = CorrectionEngine()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.hotkey_listener: ShortcutListener | None = None
        self.state = "idle"

        self._style()
        self._layout()
        self.overlay = SignalNodeOverlay(
            root,
            lambda: self.recorder.level,
            lambda: self.settings.hotkey,
            self.toggle_recording,
            self.open_window,
        )
        self._restart_hotkey()
        self._update_provider_display()
        self.home.set_state(self.state)
        self.show_page("home")
        self.overlay.show("idle")
        self.root.after(50, self._poll_events)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["surface"],
            background=COLORS["surface_alt"],
            foreground=COLORS["ink"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["border_strong"],
            lightcolor=COLORS["border_strong"],
            darkcolor=COLORS["border_strong"],
            padding=9,
            font=(FONT_UI, 10),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["surface"])],
            foreground=[("readonly", COLORS["ink"])],
            selectbackground=[("readonly", COLORS["surface"])],
            selectforeground=[("readonly", COLORS["ink"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["surface_alt"],
            troughcolor=COLORS["surface"],
            bordercolor=COLORS["surface"],
            arrowcolor=COLORS["muted"],
            width=11,
        )

    def _layout(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["window"])
        shell.pack(fill="both", expand=True)

        body = tk.Frame(shell, bg=COLORS["window"])
        body.pack(fill="both", expand=True)
        nav = tk.Frame(
            body,
            bg=COLORS["nav"],
            width=184,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        main = tk.Frame(body, bg=COLORS["window"])
        main.pack(side="left", fill="both", expand=True)

        self.nav_buttons: dict[str, tk.Button] = {}
        nav_brand = tk.Frame(nav, bg=COLORS["nav"])
        nav_brand.pack(fill="x", padx=18, pady=(20, 13))
        BrandMark(nav_brand, 28).pack(side="left")
        brand_text = tk.Frame(nav_brand, bg=COLORS["nav"])
        brand_text.pack(side="left", padx=(9, 0))
        _label(brand_text, "AgentWisper", 11, COLORS["ink"], "bold").pack(anchor="w")
        _label(brand_text, "Technical dictation", 7, COLORS["muted"]).pack(anchor="w")
        tk.Frame(nav, height=1, bg=COLORS["border"]).pack(fill="x", padx=12)
        nav_group = tk.Frame(nav, bg=COLORS["nav"])
        nav_group.pack(fill="x", padx=12, pady=(13, 0))
        for key, title, glyph in (
            ("home", "Speak", "●"),
            ("history", "History", "◷"),
            ("settings", "Settings", "◇"),
        ):
            button = tk.Button(
                nav_group,
                text=f"  {glyph}    {title}",
                command=lambda page=key: self.show_page(page),
                anchor="w",
                bg=COLORS["nav"],
                fg=COLORS["muted"],
                activebackground=COLORS["accent_soft"],
                activeforeground=COLORS["accent"],
                relief="flat",
                bd=0,
                padx=10,
                pady=11,
                font=(FONT_UI, 10, "bold"),
                cursor="hand2",
                highlightthickness=2,
                highlightbackground=COLORS["nav"],
                highlightcolor=COLORS["accent"],
                takefocus=True,
            )
            button.pack(fill="x", pady=2)
            self.nav_buttons[key] = button

        nav_footer = tk.Frame(nav, bg=COLORS["nav"])
        nav_footer.pack(side="bottom", fill="x", padx=20, pady=20)
        _label(nav_footer, "LOCAL-FIRST", 7, COLORS["success"], "bold", FONT_MONO).pack(
            anchor="w"
        )
        _label(
            nav_footer,
            "History and keys stay in your Windows profile.",
            8,
            COLORS["muted"],
            wraplength=140,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self.pages = {
            "home": HomePage(main, self),
            "history": HistoryPage(main, self),
            "settings": SettingsPage(main, self),
        }
        for page in self.pages.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

    @property
    def home(self) -> HomePage:
        return self.pages["home"]  # type: ignore[return-value]

    @property
    def history_page(self) -> HistoryPage:
        return self.pages["history"]  # type: ignore[return-value]

    def open_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def show_page(self, name: str) -> None:
        self.pages[name].tkraise()
        for key, button in self.nav_buttons.items():
            selected = key == name
            button.configure(
                bg=COLORS["accent_soft"] if selected else COLORS["nav"],
                fg=COLORS["accent"] if selected else COLORS["muted"],
            )
        if name == "history":
            self.history_page.refresh()

    def _provider_model(self) -> tuple[str, str]:
        if self.settings.provider == "local":
            return "local", "Parakeet v3"
        if self.settings.provider == "groq":
            return "groq", self.settings.groq_model
        return "custom", self.settings.custom_model

    def _update_provider_display(self) -> None:
        provider, model = self._provider_model()
        self.home.set_provider(provider, model)

    def apply_settings(self, settings: UserSettings) -> None:
        self.settings_store.save(settings)
        self.settings = settings
        self.recorder = AudioRecorder(settings.input_device)
        self.overlay.level_getter = lambda: self.recorder.level
        self.home.signal.level_getter = lambda: self.recorder.level
        self._restart_hotkey()
        self._update_provider_display()
        self.home.set_state(self.state)

    def _restart_hotkey(self) -> None:
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.hotkey_listener = ShortcutListener(
            self.settings.hotkey,
            lambda: self.events.put(("toggle", None)),
            "<ctrl>+<alt>+<esc>",
            lambda: self.events.put(("exit", None)),
        )
        self.hotkey_listener.start()

    @staticmethod
    def _foreground_external_window() -> int | None:
        """Capture the app that should receive the finished transcript."""
        try:
            handle = int(ctypes.windll.user32.GetForegroundWindow())
            if not handle:
                return None
            process_id = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(
                handle, ctypes.byref(process_id)
            )
            return None if process_id.value == os.getpid() else handle
        except (AttributeError, OSError):
            return None

    def _restore_paste_target(self) -> bool:
        handle = self._paste_target_hwnd
        if not handle:
            return False
        try:
            if not ctypes.windll.user32.IsWindow(handle):
                return False
            if ctypes.windll.user32.GetForegroundWindow() != handle:
                ctypes.windll.user32.SetForegroundWindow(handle)
            return ctypes.windll.user32.GetForegroundWindow() == handle
        except (AttributeError, OSError):
            return False

    def toggle_recording(self) -> None:
        if self.state == "listening":
            self._stop_recording()
            return
        if self.state != "idle":
            return
        self._paste_target_hwnd = self._foreground_external_window()
        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001 - device backends vary
            self.home.set_state("error", str(exc))
            self.overlay.error(str(exc))
            return
        self.state = "listening"
        self.home.set_state("listening")
        self.overlay.show("listening")

    def _stop_recording(self) -> None:
        samples = self.recorder.stop()
        if samples.size < 1_600:
            self.state = "idle"
            self.home.set_state(
                "idle", "Recording was too short. Hold the hotkey a little longer."
            )
            self.overlay.error("Recording too short")
            return
        self.state = "transcribing"
        self.home.set_state("transcribing")
        self.overlay.show("transcribing")
        settings = self.settings
        threading.Thread(
            target=self._transcribe, args=(samples, settings), daemon=True
        ).start()

    @staticmethod
    def _technical_prompt() -> str:
        terms = list(TECHNICAL_TERMS)[:35]
        return "Technical vocabulary: " + ", ".join(terms)

    def _transcribe(self, samples, settings: UserSettings) -> None:
        try:
            if settings.provider == "local":
                transcription = self.local_pool.transcribe(
                    samples,
                    16_000,
                    Path(settings.local_model_dir),
                    settings.num_threads,
                )
                model = "parakeet-tdt-0.6b-v3-int8"
            else:
                secret_name = (
                    "groq_api_key" if settings.provider == "groq" else "custom_api_key"
                )
                model = (
                    settings.groq_model
                    if settings.provider == "groq"
                    else settings.custom_model
                )
                transcription = self.cloud.transcribe(
                    samples,
                    16_000,
                    ProviderRequest(
                        provider=settings.provider,
                        model=model,
                        api_key=self.secret_store.get(secret_name),
                        base_url=settings.custom_base_url,
                        language=settings.language,
                        prompt=self._technical_prompt(),
                    ),
                )
            correction = self.corrections.correct(transcription.text)
            if not correction.text:
                raise RuntimeError("No speech recognized")
            self.history_store.add(
                correction.text,
                transcription.text,
                settings.provider,
                model,
                transcription.audio_seconds,
                transcription.elapsed_seconds,
            )
            self.events.put(
                (
                    "result",
                    (
                        correction.text,
                        transcription.audio_seconds,
                        transcription.elapsed_seconds,
                        settings,
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - report provider/model failures to UI
            self.events.put(("error", str(exc)))

    def _poll_events(self) -> None:
        while True:
            try:
                name, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if name == "toggle":
                self.toggle_recording()
            elif name == "exit":
                self.close()
                return
            elif name == "result":
                text, audio_seconds, elapsed_seconds, settings = payload  # type: ignore[misc]
                self.state = "idle"
                self.home.set_transcript(text)
                pasted = False
                if settings.paste_result:
                    try:
                        if self._restore_paste_target():
                            _paste_text(text, settings.restore_clipboard)
                            pasted = True
                    except Exception as exc:  # noqa: BLE001 - preserve transcript on paste failure
                        self.home.set_state(
                            "error", f"Transcript ready; paste failed: {exc}"
                        )
                        self.overlay.error("Paste failed - open AgentWisper")
                        self._paste_target_hwnd = None
                        continue
                self._paste_target_hwnd = None
                self.home.set_state(
                    "success",
                    f"{audio_seconds:.1f}s of audio processed in {elapsed_seconds:.2f}s.",
                    pasted=pasted,
                )
                self.overlay.success(len(text.split()), pasted)
                self.root.after(2400, self._settle_success)
            elif name == "error":
                self.state = "idle"
                self._paste_target_hwnd = None
                self.home.set_state("error", str(payload))
                self.overlay.error(str(payload))
        self.root.after(50, self._poll_events)

    def _settle_success(self) -> None:
        if self.state == "idle" and self.home.current_state == "success":
            self.home.set_state("idle")

    def close(self) -> None:
        if self.recorder.recording:
            self.recorder.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.overlay.destroy()
        self.root.destroy()


def _set_windows_app_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "AgentWisper.Desktop"
        )
    except (AttributeError, OSError):
        pass


def main() -> None:
    _set_windows_app_id()
    root = tk.Tk()
    AgentWisperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
