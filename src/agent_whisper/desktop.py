from __future__ import annotations

import ctypes
import os
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

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
from agent_whisper.storage import HistoryStore, SecretStore, SettingsStore, UserSettings
from agent_whisper.vocabulary import TECHNICAL_TERMS, CorrectionEngine

MAX_RECORDING_SECONDS = 120


class DesktopController:
    """Thread-safe desktop application core, independent from its HTML UI."""

    def __init__(self) -> None:
        self.settings_store = SettingsStore()
        self.secret_store = SecretStore()
        self.history_store = HistoryStore()
        self.settings = self.settings_store.load()
        if not self.settings.local_model_dir:
            self.settings.local_model_dir = str(discover_model_dir())
            self.settings_store.save(self.settings)

        self.recorder = AudioRecorder(
            self.settings.input_device,
            max_recording_seconds=MAX_RECORDING_SECONDS,
        )
        self.local_pool = LocalTranscriberPool()
        self.cloud = CloudTranscriber()
        self.corrections = CorrectionEngine()
        self.hotkey_listener: ShortcutListener | None = None

        latest = self.history_store.list(limit=1)
        self.state = "idle"
        self.detail = ""
        self.latest_text = latest[0].text if latest else ""
        self.pasted: bool | None = None
        self.version = 1
        self._paste_target_hwnd: int | None = None
        self._recording_started_at = 0.0
        self._recording_timer: threading.Timer | None = None
        self._settle_timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self._shutdown = False

    def start(self) -> None:
        listener = self._make_hotkey_listener(self.settings.hotkey)
        listener.start()
        self.hotkey_listener = listener

    def _make_hotkey_listener(self, hotkey: str) -> ShortcutListener:
        return ShortcutListener(
            hotkey,
            self.start_recording,
            self.stop_recording,
        )

    def _cancel_timer(self, name: str) -> None:
        timer = getattr(self, name)
        if timer is not None:
            timer.cancel()
            setattr(self, name, None)

    def _set_state(
        self,
        state: str,
        detail: str = "",
        *,
        pasted: bool | None = None,
    ) -> None:
        with self._lock:
            self._cancel_timer("_settle_timer")
            self.state = state
            self.detail = detail
            self.pasted = pasted
            self.version += 1

    def _settle_after(self, seconds: float, expected_state: str) -> None:
        def settle() -> None:
            with self._lock:
                if self._shutdown or self.state != expected_state:
                    return
                self._settle_timer = None
            self._set_state("idle")

        with self._lock:
            self._cancel_timer("_settle_timer")
            timer = threading.Timer(seconds, settle)
            timer.daemon = True
            self._settle_timer = timer
            timer.start()

    @staticmethod
    def _foreground_external_window() -> int | None:
        try:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            handle = int(user32.GetForegroundWindow() or 0)
            if not handle:
                return None
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
            return None if process_id.value == os.getpid() else handle
        except (AttributeError, OSError):
            return None

    def _restore_paste_target(self) -> bool:
        handle = self._paste_target_hwnd
        if not handle:
            return False
        try:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            if not user32.IsWindow(handle):
                return False
            if int(user32.GetForegroundWindow() or 0) != handle:
                user32.SetForegroundWindow(handle)
            return int(user32.GetForegroundWindow() or 0) == handle
        except (AttributeError, OSError):
            return False

    def start_recording(self) -> bool:
        with self._lock:
            if self._shutdown or self.state in {"listening", "transcribing"}:
                return False
            self._cancel_timer("_settle_timer")
            self._paste_target_hwnd = self._foreground_external_window()
            try:
                self.recorder.start()
            except Exception as exc:  # noqa: BLE001 - audio backends vary
                self._set_state("error", f"Microphone unavailable: {exc}")
                self._settle_after(3.5, "error")
                return False
            self._recording_started_at = time.monotonic()
            timer = threading.Timer(
                MAX_RECORDING_SECONDS,
                lambda: self.stop_recording(reached_limit=True),
            )
            timer.daemon = True
            self._recording_timer = timer
            timer.start()
        self._set_state("listening")
        return True

    def stop_recording(self, reached_limit: bool = False) -> bool:
        with self._lock:
            if self._shutdown or self.state != "listening":
                return False
            self._cancel_timer("_recording_timer")
            samples = self.recorder.stop()
            self._recording_started_at = 0.0
            if samples.size < 1_600:
                self._paste_target_hwnd = None
                self._set_state(
                    "error",
                    "Recording was too short. Hold the hotkey a little longer.",
                )
                self._settle_after(3.0, "error")
                return False
            settings = replace(self.settings)
            detail = (
                "Two-minute limit reached. Transcribing captured audio."
                if reached_limit
                else ""
            )
            self._set_state("transcribing", detail)
            threading.Thread(
                target=self._transcribe,
                args=(samples, settings),
                daemon=True,
                name="AgentWisperTranscription",
            ).start()
            return True

    def toggle_recording(self) -> bool:
        if self.runtime()["state"] == "listening":
            return self.stop_recording()
        return self.start_recording()

    @staticmethod
    def _technical_prompt() -> str:
        return "Technical vocabulary: " + ", ".join(list(TECHNICAL_TERMS)[:35])

    def _transcribe(self, samples: Any, settings: UserSettings) -> None:
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

            pasted = False
            paste_failed = ""
            if settings.paste_result and self._restore_paste_target():
                try:
                    _paste_text(correction.text, settings.restore_clipboard)
                    pasted = True
                except Exception as exc:  # noqa: BLE001 - transcript remains recoverable
                    paste_failed = str(exc)

            with self._lock:
                self.latest_text = correction.text
                self._paste_target_hwnd = None
            if paste_failed:
                self._set_state(
                    "error",
                    f"Transcript saved, but paste failed: {paste_failed}",
                )
                self._settle_after(4.0, "error")
                return

            if pasted:
                detail = (
                    f"Pasted {len(correction.text.split())} words. "
                    f"Processed {transcription.audio_seconds:.1f}s in "
                    f"{transcription.elapsed_seconds:.2f}s."
                )
            elif settings.paste_result:
                detail = (
                    "Transcript ready. Use the hotkey from another app to auto-paste."
                )
            else:
                detail = "Transcript ready and saved locally."
            self._set_state("success", detail, pasted=pasted)
            self._settle_after(2.6, "success")
        except Exception as exc:  # noqa: BLE001 - provider/model failures reach UI
            with self._lock:
                self._paste_target_hwnd = None
            self._set_state("error", str(exc))
            self._settle_after(4.0, "error")

    def runtime(self) -> dict[str, Any]:
        with self._lock:
            recording_seconds = (
                max(0.0, time.monotonic() - self._recording_started_at)
                if self.state == "listening" and self._recording_started_at
                else 0.0
            )
            provider_name = {
                "local": "Local Parakeet",
                "groq": "Groq Cloud",
                "custom": "Custom cloud",
            }.get(self.settings.provider, self.settings.provider)
            model = (
                "Parakeet v3"
                if self.settings.provider == "local"
                else self.settings.groq_model
                if self.settings.provider == "groq"
                else self.settings.custom_model
            )
            return {
                "version": self.version,
                "state": self.state,
                "detail": self.detail,
                "pasted": self.pasted,
                "latest_text": self.latest_text,
                "word_count": len(self.latest_text.split()) if self.latest_text else 0,
                "level": self.recorder.level if self.state == "listening" else 0.0,
                "recording_seconds": recording_seconds,
                "recording_limit_seconds": MAX_RECORDING_SECONDS,
                "hotkey": self.settings.hotkey,
                "hotkey_label": hotkey_label(self.settings.hotkey),
                "provider": self.settings.provider,
                "provider_name": provider_name,
                "model": model,
                "local": self.settings.provider == "local",
            }

    def history(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.history_store.list()]

    def settings_payload(self) -> dict[str, Any]:
        with self._lock:
            payload = asdict(self.settings)
        payload.update(
            {
                "groq_key_saved": self.secret_store.has("groq_api_key"),
                "custom_key_saved": self.secret_store.has("custom_api_key"),
            }
        )
        return payload

    def bootstrap(self) -> dict[str, Any]:
        device_error = ""
        devices = [{"value": "", "label": "System default"}]
        try:
            devices.extend(
                {"value": str(index), "label": f"{index}: {name}"}
                for index, name in list_input_devices()
            )
        except Exception as exc:  # noqa: BLE001 - device enumeration varies by driver
            device_error = f"Microphones could not be listed: {exc}"
        return {
            "runtime": self.runtime(),
            "settings": self.settings_payload(),
            "history": self.history(),
            "devices": devices,
            "device_error": device_error,
            "hotkeys": [
                {"label": label, "value": value}
                for label, value in HOTKEY_CHOICES.items()
            ],
            "groq_models": list(GROQ_MODELS),
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self.state in {"listening", "transcribing"}:
                raise ValueError("Finish the current dictation before saving settings")

        provider = str(payload.get("provider", "local"))
        if provider not in {"local", "groq", "custom"}:
            raise ValueError("Choose a supported transcription provider")
        hotkey = normalize_hotkey(str(payload.get("hotkey", "")))
        local_model = Path(str(payload.get("local_model_dir", ""))).expanduser()
        if provider == "local":
            missing = [
                name for name in MODEL_FILES if not (local_model / name).is_file()
            ]
            if missing:
                raise ValueError("Local model folder is incomplete")

        groq_model = str(payload.get("groq_model", ""))
        if groq_model not in GROQ_MODELS:
            raise ValueError("Choose a supported Groq model")
        custom_url = str(payload.get("custom_base_url", "")).strip()
        custom_model = str(payload.get("custom_model", "")).strip()
        if provider == "custom":
            custom_url = validate_base_url(custom_url)
            if not custom_model or len(custom_model) > 200:
                raise ValueError("Enter a valid custom model ID")

        language = str(payload.get("language", "en")).strip().lower()
        if language and (len(language) > 10 or not language.replace("-", "").isalpha()):
            raise ValueError("Language must be an ISO code such as en or en-US")
        raw_device = payload.get("input_device")
        input_device = None if raw_device in {None, ""} else int(raw_device)
        groq_key = str(payload.get("groq_api_key", "")).strip()
        custom_key = str(payload.get("custom_api_key", "")).strip()
        if len(groq_key) > 4_096 or len(custom_key) > 4_096:
            raise ValueError("API key is unexpectedly long")
        if groq_key:
            self.secret_store.set("groq_api_key", groq_key)
        if custom_key:
            self.secret_store.set("custom_api_key", custom_key)
        if provider == "groq" and not self.secret_store.has("groq_api_key"):
            raise ValueError("Enter a Groq API key")
        if provider == "custom" and not self.secret_store.has("custom_api_key"):
            raise ValueError("Enter an API key for the custom provider")

        settings = UserSettings(
            provider=provider,
            hotkey=hotkey,
            input_device=input_device,
            local_model_dir=str(local_model),
            groq_model=groq_model,
            custom_base_url=custom_url,
            custom_model=custom_model,
            paste_result=bool(payload.get("paste_result", True)),
            restore_clipboard=bool(payload.get("restore_clipboard", True)),
            language=language,
            num_threads=self.settings.num_threads,
        )

        new_listener = self._make_hotkey_listener(settings.hotkey)
        new_listener.start()
        try:
            self.settings_store.save(settings)
        except Exception:
            new_listener.stop()
            raise

        with self._lock:
            old_listener = self.hotkey_listener
            self.hotkey_listener = new_listener
            self.settings = settings
            self.recorder = AudioRecorder(
                settings.input_device,
                max_recording_seconds=MAX_RECORDING_SECONDS,
            )
            self.version += 1
        if old_listener:
            old_listener.stop()
        return self.settings_payload()

    def clear_history(self) -> None:
        self.history_store.clear()
        with self._lock:
            self.latest_text = ""
            self.version += 1

    def copy_latest(self) -> bool:
        with self._lock:
            text = self.latest_text
        if not text:
            return False
        pyperclip.copy(text)
        return True

    def copy_text(self, text: str) -> bool:
        cleaned = text.strip()
        if not cleaned:
            return False
        pyperclip.copy(cleaned)
        return True

    def shutdown(self) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            self._cancel_timer("_recording_timer")
            self._cancel_timer("_settle_timer")
            listener = self.hotkey_listener
            self.hotkey_listener = None
            if self.recorder.recording:
                self.recorder.stop()
        if listener:
            listener.stop()
