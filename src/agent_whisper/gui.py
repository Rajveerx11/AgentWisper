from __future__ import annotations

import math
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import ClassVar

import pyperclip
from pynput import keyboard

from agent_whisper.app import _paste_text
from agent_whisper.audio import AudioRecorder, list_input_devices
from agent_whisper.config import MODEL_FILES, discover_model_dir
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
    "bg": "#0B0E12",
    "sidebar": "#10141A",
    "card": "#151A21",
    "card_hover": "#1A2028",
    "border": "#28303A",
    "text": "#F3F6F8",
    "muted": "#96A0AD",
    "faint": "#66717E",
    "accent": "#65E6B4",
    "accent_dark": "#183D32",
    "danger": "#FB7185",
    "warning": "#F5C26B",
    "white": "#FFFFFF",
}

FONT_UI = "Segoe UI"
FONT_MONO = "Cascadia Mono"


def _card(parent: tk.Misc, **kwargs) -> tk.Frame:
    return tk.Frame(
        parent,
        bg=COLORS["card"],
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        bd=0,
        **kwargs,
    )


def _label(
    parent: tk.Misc,
    text: str,
    size: int = 11,
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


class FlatButton(tk.Button):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command,
        accent: bool = False,
        compact: bool = False,
        **kwargs,
    ) -> None:
        background = COLORS["accent"] if accent else COLORS["card_hover"]
        foreground = COLORS["bg"] if accent else COLORS["text"]
        active_background = "#8CF0C9" if accent else "#232B35"
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=active_background,
            activeforeground=foreground,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=(FONT_UI, 10, "bold"),
            padx=12 if compact else 18,
            pady=7 if compact else 10,
            highlightthickness=0,
            **kwargs,
        )


class MicControl(tk.Canvas):
    def __init__(self, parent: tk.Misc, command, level_getter) -> None:
        super().__init__(
            parent,
            width=176,
            height=176,
            bg=parent.cget("bg"),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.command = command
        self.level_getter = level_getter
        self.state = "idle"
        self.phase = 0.0
        self.bind("<Button-1>", lambda _event: self.command())
        self._animate()

    def set_state(self, state: str) -> None:
        self.state = state

    def _animate(self) -> None:
        self.delete("all")
        self.phase += 0.16
        level = self.level_getter() if self.state == "listening" else 0.0
        pulse = 4.0 * math.sin(self.phase) if self.state == "transcribing" else level * 18
        outer = 75 + max(0.0, pulse)
        center = 88
        ring = COLORS["accent_dark"] if self.state != "idle" else COLORS["border"]
        fill = COLORS["accent"] if self.state == "listening" else COLORS["card_hover"]
        if self.state == "transcribing":
            fill = "#21443A"
        self.create_oval(
            center - outer,
            center - outer,
            center + outer,
            center + outer,
            fill=ring,
            outline="",
        )
        self.create_oval(28, 28, 148, 148, fill=fill, outline="")
        icon_color = COLORS["bg"] if self.state == "listening" else COLORS["accent"]
        self.create_line(88, 57, 88, 100, fill=icon_color, width=11, capstyle=tk.ROUND)
        self.create_arc(
            62,
            72,
            114,
            122,
            start=180,
            extent=180,
            style=tk.ARC,
            outline=icon_color,
            width=4,
        )
        self.create_line(88, 121, 88, 134, fill=icon_color, width=4)
        self.create_line(73, 134, 103, 134, fill=icon_color, width=4, capstyle=tk.ROUND)
        self.after(55, self._animate)


class ListeningOverlay:
    def __init__(self, root: tk.Tk, level_getter) -> None:
        self.root = root
        self.level_getter = level_getter
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.97)
        self.canvas = tk.Canvas(
            self.window,
            width=346,
            height=70,
            bg=COLORS["bg"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.canvas.pack()
        self.state = "listening"
        self.phase = 0.0
        self._tick()

    def show(self, state: str) -> None:
        self.state = state
        width = 346
        height = 70
        x = (self.root.winfo_screenwidth() - width) // 2
        y = self.root.winfo_screenheight() - height - 74
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.deiconify()

    def hide(self) -> None:
        self.window.withdraw()

    def _tick(self) -> None:
        self.canvas.delete("all")
        self.phase += 0.22
        listening = self.state == "listening"
        level = self.level_getter() if listening else 0.22
        title = "Listening" if listening else "Transcribing"
        subtitle = "Press hotkey to finish" if listening else "Turning speech into text"
        for index in range(5):
            oscillation = (math.sin(self.phase + index * 0.8) + 1) / 2
            height = 8 + (level * 30 + oscillation * (7 if not listening else 9))
            x = 28 + index * 10
            self.canvas.create_line(
                x,
                35 - height / 2,
                x,
                35 + height / 2,
                fill=COLORS["accent"],
                width=5,
                capstyle=tk.ROUND,
            )
        self.canvas.create_text(
            102,
            26,
            anchor="w",
            text=title,
            fill=COLORS["text"],
            font=(FONT_UI, 11, "bold"),
        )
        self.canvas.create_text(
            102,
            46,
            anchor="w",
            text=subtitle,
            fill=COLORS["muted"],
            font=(FONT_UI, 9),
        )
        self.window.after(60, self._tick)


class HomePage(tk.Frame):
    def __init__(self, parent: tk.Misc, app: AgentWisperApp) -> None:
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=42, pady=(34, 16))
        _label(header, "Speak to your stack", 26, weight="bold").pack(anchor="w")
        _label(
            header,
            "Private by default. Precise where technical language matters.",
            11,
            COLORS["muted"],
        ).pack(anchor="w", pady=(5, 0))

        body = _card(self)
        body.pack(fill="x", padx=42, pady=10)
        provider_row = tk.Frame(body, bg=COLORS["card"])
        provider_row.pack(fill="x", padx=24, pady=(20, 0))
        self.provider_badge = _label(
            provider_row,
            "LOCAL • PARAKEET",
            9,
            COLORS["accent"],
            "bold",
            FONT_MONO,
        )
        self.provider_badge.pack(side="left")
        self.privacy_label = _label(
            provider_row,
            "Audio stays on this device",
            9,
            COLORS["muted"],
        )
        self.privacy_label.pack(side="right")

        center = tk.Frame(body, bg=COLORS["card"])
        center.pack(pady=(10, 24))
        self.mic = MicControl(center, app.toggle_recording, lambda: app.recorder.level)
        self.mic.pack()
        self.status = _label(center, "Press Ctrl + Alt + Space", 12, weight="bold")
        self.status.pack(pady=(0, 4))
        self.status_detail = _label(
            center,
            "Your transcript will appear at the active cursor.",
            10,
            COLORS["muted"],
        )
        self.status_detail.pack()

        transcript_card = _card(self)
        transcript_card.pack(fill="both", expand=True, padx=42, pady=(10, 34))
        transcript_header = tk.Frame(transcript_card, bg=COLORS["card"])
        transcript_header.pack(fill="x", padx=22, pady=(18, 8))
        _label(transcript_header, "LATEST TRANSCRIPT", 9, COLORS["muted"], "bold", FONT_MONO).pack(
            side="left"
        )
        FlatButton(
            transcript_header,
            "Copy",
            self.copy_latest,
            compact=True,
        ).pack(side="right")
        self.transcript = tk.Text(
            transcript_card,
            height=7,
            wrap="word",
            bg=COLORS["card"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["accent_dark"],
            relief="flat",
            bd=0,
            font=(FONT_UI, 13),
            padx=22,
            pady=8,
        )
        self.transcript.pack(fill="both", expand=True, pady=(0, 16))
        self.set_transcript("Your most recent transcription will appear here.", placeholder=True)

    def set_state(self, state: str, detail: str = "") -> None:
        self.mic.set_state(state)
        labels = {
            "idle": "Press Ctrl + Alt + Space",
            "listening": "Listening…",
            "transcribing": "Transcribing…",
            "error": "Could not transcribe",
        }
        self.status.config(text=labels.get(state, state.title()))
        if detail:
            self.status_detail.config(text=detail)

    def set_provider(self, provider: str, model: str) -> None:
        names = {"local": "LOCAL", "groq": "GROQ", "custom": "CUSTOM CLOUD"}
        self.provider_badge.config(text=f"{names.get(provider, provider.upper())} • {model.upper()}")
        local = provider == "local"
        self.privacy_label.config(
            text="Audio stays on this device" if local else "Audio is sent to selected provider",
            fg=COLORS["muted"] if local else COLORS["warning"],
        )

    def set_transcript(self, text: str, placeholder: bool = False) -> None:
        self.transcript.config(state="normal", fg=COLORS["faint"] if placeholder else COLORS["text"])
        self.transcript.delete("1.0", "end")
        self.transcript.insert("1.0", text)
        self.transcript.config(state="disabled")

    def copy_latest(self) -> None:
        text = self.transcript.get("1.0", "end").strip()
        if text and text != "Your most recent transcription will appear here.":
            pyperclip.copy(text)


class HistoryPage(tk.Frame):
    def __init__(self, parent: tk.Misc, app: AgentWisperApp) -> None:
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=42, pady=(34, 16))
        title_group = tk.Frame(header, bg=COLORS["bg"])
        title_group.pack(side="left")
        _label(title_group, "History", 26, weight="bold").pack(anchor="w")
        _label(title_group, "Stored only on this PC.", 11, COLORS["muted"]).pack(anchor="w", pady=(5, 0))
        FlatButton(header, "Clear history", self.clear_history, compact=True).pack(side="right", pady=8)

        container = tk.Frame(self, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=42, pady=(0, 28))
        self.canvas = tk.Canvas(container, bg=COLORS["bg"], bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.list_frame.bind(
            "<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>", lambda event: self.canvas.itemconfigure(self.list_window, width=event.width)
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._scroll)

    def _scroll(self, event) -> None:
        if self.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    @staticmethod
    def _display_time(value: str) -> str:
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%d %b, %I:%M %p")
        except ValueError:
            return value

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        items = self.app.history_store.list()
        if not items:
            empty = _card(self.list_frame)
            empty.pack(fill="x", pady=6)
            _label(empty, "No transcripts yet", 14, weight="bold").pack(pady=(34, 6))
            _label(
                empty,
                "Use the hotkey once. Your words will land here.",
                10,
                COLORS["muted"],
            ).pack(pady=(0, 34))
            return
        for item in items:
            self._item(item)

    def _item(self, item: HistoryItem) -> None:
        card = _card(self.list_frame)
        card.pack(fill="x", pady=6)
        meta = tk.Frame(card, bg=COLORS["card"])
        meta.pack(fill="x", padx=18, pady=(14, 8))
        _label(
            meta,
            f"{item.provider.upper()}  •  {item.model}",
            8,
            COLORS["accent"],
            "bold",
            FONT_MONO,
        ).pack(side="left")
        _label(meta, self._display_time(item.created_at), 9, COLORS["muted"]).pack(side="right")
        row = tk.Frame(card, bg=COLORS["card"])
        row.pack(fill="x", padx=18, pady=(0, 15))
        _label(
            row,
            item.text,
            11,
            wraplength=650,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        FlatButton(row, "Copy", lambda text=item.text: pyperclip.copy(text), compact=True).pack(
            side="right", padx=(14, 0)
        )

    def clear_history(self) -> None:
        if messagebox.askyesno("Clear history", "Delete all local transcript history?"):
            self.app.history_store.clear()
            self.refresh()


class SettingsPage(tk.Frame):
    PROVIDERS: ClassVar[dict[str, str]] = {
        "Local Parakeet — private": "local",
        "Groq Cloud": "groq",
        "Custom OpenAI-compatible": "custom",
    }

    def __init__(self, parent: tk.Misc, app: AgentWisperApp) -> None:
        super().__init__(parent, bg=COLORS["bg"])
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

        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=42, pady=(34, 16))
        _label(header, "Settings", 26, weight="bold").pack(anchor="w")
        _label(
            header,
            "Only the controls needed to choose, speak, and paste.",
            11,
            COLORS["muted"],
        ).pack(anchor="w", pady=(5, 0))

        self.canvas = tk.Canvas(self, bg=COLORS["bg"], bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, bg=COLORS["bg"])
        window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.content.bind(
            "<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(window, width=event.width))
        self.canvas.pack(side="left", fill="both", expand=True, padx=(42, 0), pady=(0, 28))
        scrollbar.pack(side="right", fill="y", padx=(0, 24), pady=(0, 28))

        self._provider_card()
        self._credentials_card()
        self._behavior_card()
        footer = tk.Frame(self.content, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(12, 30))
        self.save_status = _label(footer, "", 9, COLORS["muted"])
        self.save_status.pack(side="left")
        FlatButton(footer, "Save settings", self.save, accent=True).pack(side="right")
        self.load()

    def _field_label(self, parent: tk.Misc, text: str) -> None:
        _label(parent, text.upper(), 8, COLORS["muted"], "bold", FONT_MONO).pack(
            anchor="w", pady=(13, 6)
        )

    @staticmethod
    def _entry(parent: tk.Misc, variable: tk.StringVar, show: str = "") -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=variable,
            show=show,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["accent_dark"],
            relief="flat",
            bd=0,
            font=(FONT_UI, 10),
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )

    def _provider_card(self) -> None:
        card = _card(self.content)
        card.pack(fill="x", pady=6)
        inside = tk.Frame(card, bg=COLORS["card"])
        inside.pack(fill="x", padx=22, pady=18)
        _label(inside, "Transcription provider", 14, weight="bold").pack(anchor="w")
        _label(
            inside,
            "Local keeps audio on-device. Cloud sends each recording to that provider.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(4, 12))
        combo = ttk.Combobox(
            inside,
            textvariable=self.provider_display,
            values=list(self.PROVIDERS),
            state="readonly",
        )
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda _event: self._show_provider_fields())

    def _credentials_card(self) -> None:
        self.credentials_card = _card(self.content)
        self.credentials_card.pack(fill="x", pady=6)
        self.credentials = tk.Frame(self.credentials_card, bg=COLORS["card"])
        self.credentials.pack(fill="x", padx=22, pady=18)

        self.local_fields = tk.Frame(self.credentials, bg=COLORS["card"])
        _label(self.local_fields, "Local Parakeet", 14, weight="bold").pack(anchor="w")
        self._field_label(self.local_fields, "Detected model folder")
        self._entry(self.local_fields, self.local_model).pack(fill="x", ipady=9)
        _label(
            self.local_fields,
            "Parakeet runs through local CPU ONNX inference. No network request.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(9, 0))

        self.groq_fields = tk.Frame(self.credentials, bg=COLORS["card"])
        _label(self.groq_fields, "Groq Cloud", 14, weight="bold").pack(anchor="w")
        self._field_label(self.groq_fields, "Model")
        ttk.Combobox(
            self.groq_fields,
            textvariable=self.groq_model,
            values=list(GROQ_MODELS),
            state="readonly",
        ).pack(fill="x")
        self._field_label(self.groq_fields, "Groq API key")
        self.groq_key = self._entry(self.groq_fields, tk.StringVar(), show="•")
        self.groq_key.pack(fill="x", ipady=9)
        self.groq_key_status = _label(self.groq_fields, "", 9, COLORS["muted"])
        self.groq_key_status.pack(anchor="w", pady=(7, 0))
        _label(
            self.groq_fields,
            "Encrypted with Windows DPAPI. Audio is sent to Groq only when selected.",
            9,
            COLORS["warning"],
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        self.custom_fields = tk.Frame(self.credentials, bg=COLORS["card"])
        _label(self.custom_fields, "Custom compatible provider", 14, weight="bold").pack(anchor="w")
        self._field_label(self.custom_fields, "API base URL")
        self._entry(self.custom_fields, self.custom_url).pack(fill="x", ipady=9)
        self._field_label(self.custom_fields, "Model ID")
        self._entry(self.custom_fields, self.custom_model).pack(fill="x", ipady=9)
        self._field_label(self.custom_fields, "API key")
        self.custom_key = self._entry(self.custom_fields, tk.StringVar(), show="•")
        self.custom_key.pack(fill="x", ipady=9)
        self.custom_key_status = _label(self.custom_fields, "", 9, COLORS["muted"])
        self.custom_key_status.pack(anchor="w", pady=(7, 0))
        _label(
            self.custom_fields,
            "HTTPS required. Plain HTTP is allowed only for localhost tools.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(8, 0))

    def _behavior_card(self) -> None:
        card = _card(self.content)
        card.pack(fill="x", pady=6)
        inside = tk.Frame(card, bg=COLORS["card"])
        inside.pack(fill="x", padx=22, pady=18)
        _label(inside, "Input and paste", 14, weight="bold").pack(anchor="w")
        two = tk.Frame(inside, bg=COLORS["card"])
        two.pack(fill="x")
        left = tk.Frame(two, bg=COLORS["card"])
        right = tk.Frame(two, bg=COLORS["card"])
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._field_label(left, "Global hotkey")
        self._entry(left, self.hotkey).pack(fill="x", ipady=9)
        self._field_label(right, "Language code")
        self._entry(right, self.language).pack(fill="x", ipady=9)

        self._field_label(inside, "Microphone")
        for index, name in list_input_devices():
            self._device_values[f"{index}: {name}"] = index
        ttk.Combobox(
            inside,
            textvariable=self.device_display,
            values=list(self._device_values),
            state="readonly",
        ).pack(fill="x")

        checks = tk.Frame(inside, bg=COLORS["card"])
        checks.pack(fill="x", pady=(16, 0))
        for text, variable in (
            ("Paste transcript at active cursor", self.paste_result),
            ("Restore previous clipboard text", self.restore_clipboard),
        ):
            tk.Checkbutton(
                checks,
                text=text,
                variable=variable,
                bg=COLORS["card"],
                fg=COLORS["text"],
                activebackground=COLORS["card"],
                activeforeground=COLORS["text"],
                selectcolor=COLORS["bg"],
                font=(FONT_UI, 10),
                highlightthickness=0,
            ).pack(anchor="w", pady=3)

    def _show_provider_fields(self) -> None:
        for frame in (self.local_fields, self.groq_fields, self.custom_fields):
            frame.pack_forget()
        provider = self.PROVIDERS.get(self.provider_display.get(), "local")
        {"local": self.local_fields, "groq": self.groq_fields, "custom": self.custom_fields}[
            provider
        ].pack(fill="x")

    def load(self) -> None:
        settings = self.app.settings
        reverse = {value: key for key, value in self.PROVIDERS.items()}
        self.provider_display.set(reverse.get(settings.provider, reverse["local"]))
        self.groq_model.set(settings.groq_model)
        self.custom_url.set(settings.custom_base_url)
        self.custom_model.set(settings.custom_model)
        self.hotkey.set(settings.hotkey)
        self.language.set(settings.language)
        self.local_model.set(settings.local_model_dir)
        self.paste_result.set(settings.paste_result)
        self.restore_clipboard.set(settings.restore_clipboard)
        selected = next(
            (name for name, value in self._device_values.items() if value == settings.input_device),
            "System default",
        )
        self.device_display.set(selected)
        self.groq_key_status.config(
            text="Encrypted key saved" if self.app.secret_store.has("groq_api_key") else "No saved key"
        )
        self.custom_key_status.config(
            text="Encrypted key saved" if self.app.secret_store.has("custom_api_key") else "No saved key"
        )
        self._show_provider_fields()

    def save(self) -> None:
        try:
            hotkey_value = self.hotkey.get().strip()
            keyboard.HotKey.parse(hotkey_value)
            provider = self.PROVIDERS[self.provider_display.get()]
            local_model = Path(self.local_model.get().strip())
            if provider == "local":
                missing = [name for name in MODEL_FILES if not (local_model / name).is_file()]
                if missing:
                    raise ValueError("Local model folder is incomplete")
            custom_url = self.custom_url.get().strip()
            if provider == "custom":
                custom_url = validate_base_url(custom_url)
                if not self.custom_model.get().strip():
                    raise ValueError("Enter a custom model ID")
            language = self.language.get().strip().lower()
            if language and (len(language) > 10 or not language.replace("-", "").isalpha()):
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
            self.save_status.config(text="Settings saved", fg=COLORS["accent"])
        except (ValueError, OSError) as exc:
            self.save_status.config(text=str(exc), fg=COLORS["danger"])


class AgentWisperApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AgentWisper")
        self.root.configure(bg=COLORS["bg"])
        self.root.geometry("1040x700")
        self.root.minsize(900, 620)
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
        self.hotkey_listener: keyboard.GlobalHotKeys | None = None
        self.state = "idle"

        self._style()
        self._layout()
        self.overlay = ListeningOverlay(root, lambda: self.recorder.level)
        self._restart_hotkey()
        self._update_provider_display()
        self.show_page("home")
        self.root.after(50, self._poll_events)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["bg"],
            background=COLORS["card_hover"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["accent"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=9,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["bg"])],
            foreground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["bg"])],
            selectforeground=[("readonly", COLORS["text"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["card_hover"],
            troughcolor=COLORS["bg"],
            bordercolor=COLORS["bg"],
            arrowcolor=COLORS["muted"],
        )

    def _layout(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["bg"])
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=COLORS["sidebar"], width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        main = tk.Frame(shell, bg=COLORS["bg"])
        main.pack(side="left", fill="both", expand=True)

        brand = tk.Frame(sidebar, bg=COLORS["sidebar"])
        brand.pack(fill="x", padx=22, pady=(26, 34))
        mark = tk.Canvas(brand, width=28, height=28, bg=COLORS["sidebar"], bd=0, highlightthickness=0)
        mark.pack(side="left")
        mark.create_oval(3, 3, 25, 25, fill=COLORS["accent_dark"], outline="")
        for index, height in enumerate((7, 15, 11)):
            x = 9 + index * 5
            mark.create_line(x, 14 - height / 2, x, 14 + height / 2, fill=COLORS["accent"], width=3)
        _label(brand, "AgentWisper", 13, weight="bold").pack(side="left", padx=(8, 0))

        self.nav_buttons: dict[str, tk.Button] = {}
        for key, title in (("home", "Speak"), ("history", "History"), ("settings", "Settings")):
            button = tk.Button(
                sidebar,
                text=title,
                command=lambda page=key: self.show_page(page),
                anchor="w",
                bg=COLORS["sidebar"],
                fg=COLORS["muted"],
                activebackground=COLORS["card"],
                activeforeground=COLORS["text"],
                relief="flat",
                bd=0,
                padx=22,
                pady=12,
                font=(FONT_UI, 10, "bold"),
                cursor="hand2",
            )
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

        privacy = tk.Frame(sidebar, bg=COLORS["sidebar"])
        privacy.pack(side="bottom", fill="x", padx=22, pady=22)
        _label(privacy, "LOCAL-FIRST", 8, COLORS["accent"], "bold", FONT_MONO).pack(anchor="w")
        _label(
            privacy,
            "History stays on this PC.",
            9,
            COLORS["faint"],
            wraplength=150,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

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

    def show_page(self, name: str) -> None:
        self.pages[name].tkraise()
        for key, button in self.nav_buttons.items():
            selected = key == name
            button.configure(
                bg=COLORS["card"] if selected else COLORS["sidebar"],
                fg=COLORS["text"] if selected else COLORS["muted"],
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
        self._restart_hotkey()
        self._update_provider_display()

    def _restart_hotkey(self) -> None:
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.hotkey_listener = keyboard.GlobalHotKeys(
            {
                self.settings.hotkey: lambda: self.events.put(("toggle", None)),
                "<ctrl>+<alt>+<esc>": lambda: self.events.put(("exit", None)),
            }
        )
        self.hotkey_listener.start()

    def toggle_recording(self) -> None:
        if self.state == "listening":
            self._stop_recording()
            return
        if self.state != "idle":
            return
        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001 - device backends vary
            self.home.set_state("error", str(exc))
            return
        self.state = "listening"
        self.home.set_state("listening", "Press the hotkey again when finished.")
        self.overlay.show("listening")

    def _stop_recording(self) -> None:
        samples = self.recorder.stop()
        if samples.size < 1_600:
            self.state = "idle"
            self.home.set_state("idle", "Recording was too short.")
            self.overlay.hide()
            return
        self.state = "transcribing"
        self.home.set_state("transcribing", "Using your selected transcription provider.")
        self.overlay.show("transcribing")
        settings = self.settings
        threading.Thread(
            target=self._transcribe,
            args=(samples, settings),
            daemon=True,
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
                secret_name = "groq_api_key" if settings.provider == "groq" else "custom_api_key"
                model = settings.groq_model if settings.provider == "groq" else settings.custom_model
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
                self.overlay.hide()
                self.home.set_state(
                    "idle",
                    f"{audio_seconds:.1f}s audio transcribed in {elapsed_seconds:.2f}s.",
                )
                self.home.set_transcript(text)
                if settings.paste_result:
                    try:
                        _paste_text(text, settings.restore_clipboard)
                    except Exception as exc:  # noqa: BLE001 - preserve transcript on paste failure
                        self.home.set_state("idle", f"Transcript ready; paste failed: {exc}")
            elif name == "error":
                self.state = "idle"
                self.overlay.hide()
                self.home.set_state("error", str(payload))
        self.root.after(50, self._poll_events)

    def close(self) -> None:
        if self.recorder.recording:
            self.recorder.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AgentWisperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
