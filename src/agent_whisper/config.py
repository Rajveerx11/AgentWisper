from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MODEL_FOLDER = "parakeet-tdt-0.6b-v3-int8"
MODEL_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


def discover_model_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if not app_data:
        raise FileNotFoundError("APPDATA is not defined; set model_dir in config.json")

    candidates = (
        Path(app_data) / "orca" / "speech-models" / MODEL_FOLDER,
        Path(app_data) / "com.pais.handy" / "models" / MODEL_FOLDER,
        Path(app_data) / "October" / "voice-models" / MODEL_FOLDER,
    )
    for candidate in candidates:
        if all((candidate / name).is_file() for name in MODEL_FILES):
            return candidate

    searched = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Parakeet model not found. Searched:\n{searched}")


@dataclass(slots=True)
class AppConfig:
    hotkey: str = "<ctrl>+<alt>+<space>"
    exit_hotkey: str = "<ctrl>+<alt>+<esc>"
    input_device: int | str | None = None
    model_dir: Path = field(default_factory=discover_model_dir)
    workspace_path: Path | None = None
    paste_result: bool = True
    restore_clipboard: bool = True
    max_recording_seconds: int = 120
    num_threads: int = 4
    custom_terms: dict[str, list[str]] = field(default_factory=dict)

    def validate(self) -> None:
        missing = [name for name in MODEL_FILES if not (self.model_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(
                f"Model directory {self.model_dir} is missing: {', '.join(missing)}"
            )
        if self.max_recording_seconds < 1:
            raise ValueError("max_recording_seconds must be positive")
        if self.num_threads < 1:
            raise ValueError("num_threads must be positive")


def _optional_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(os.path.expandvars(str(value))).expanduser().resolve()


def load_config(path: Path | None = None) -> AppConfig:
    raw: dict[str, Any] = {}
    if path and path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))

    model_dir = _optional_path(raw.get("model_dir")) or discover_model_dir()
    workspace_path = _optional_path(raw.get("workspace_path"))
    custom_terms = raw.get("custom_terms", {})
    if not isinstance(custom_terms, dict):
        raise TypeError("custom_terms must be an object mapping canonical terms to aliases")

    config = AppConfig(
        hotkey=str(raw.get("hotkey", "<ctrl>+<alt>+<space>")),
        exit_hotkey=str(raw.get("exit_hotkey", "<ctrl>+<alt>+<esc>")),
        input_device=raw.get("input_device"),
        model_dir=model_dir,
        workspace_path=workspace_path,
        paste_result=bool(raw.get("paste_result", True)),
        restore_clipboard=bool(raw.get("restore_clipboard", True)),
        max_recording_seconds=int(raw.get("max_recording_seconds", 120)),
        num_threads=int(raw.get("num_threads", 4)),
        custom_terms={
            str(canonical): [str(alias) for alias in aliases]
            for canonical, aliases in custom_terms.items()
        },
    )
    config.validate()
    return config
