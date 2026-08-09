from __future__ import annotations

import argparse
import sys
import threading
import time
import winsound
from pathlib import Path

import pyperclip
from pynput import keyboard

from agent_whisper.audio import AudioRecorder, list_input_devices, load_wave, record_for
from agent_whisper.config import AppConfig, load_config
from agent_whisper.hotkeys import ShortcutListener
from agent_whisper.transcriber import ParakeetTranscriber, Transcription
from agent_whisper.vocabulary import CorrectionEngine, CorrectionResult, scan_repository


def _beep(frequency: int) -> None:
    try:
        winsound.Beep(frequency, 90)
    except RuntimeError:
        pass


def _paste_text(text: str, restore_clipboard: bool) -> None:
    previous: str | None = None
    if restore_clipboard:
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous = None

    pyperclip.copy(text)
    controller = keyboard.Controller()
    with controller.pressed(keyboard.Key.ctrl):
        controller.press("v")
        controller.release("v")

    if restore_clipboard and previous is not None:
        time.sleep(0.35)
        pyperclip.copy(previous)


class DictationApp:
    def __init__(self, config: AppConfig, workspace: Path | None = None) -> None:
        self.config = config
        self.workspace = workspace or config.workspace_path
        repository_terms = scan_repository(self.workspace) if self.workspace else {}
        self.corrections = CorrectionEngine(config.custom_terms, repository_terms)
        self.recorder = AudioRecorder(
            device=config.input_device,
            max_recording_seconds=config.max_recording_seconds,
        )
        self.transcriber = ParakeetTranscriber(config.model_dir, config.num_threads)
        self._busy = False
        self._lock = threading.Lock()
        self._listener: ShortcutListener | None = None

    def process(self, samples, sample_rate: int = 16_000) -> tuple[Transcription, CorrectionResult]:
        transcription = self.transcriber.transcribe(samples, sample_rate)
        correction = self.corrections.correct(transcription.text)
        return transcription, correction

    def _finish_recording(self) -> None:
        samples = self.recorder.stop()
        _beep(620)
        if samples.size < 1_600:
            print("Recording too short; ignored.")
            with self._lock:
                self._busy = False
            return

        try:
            transcription, correction = self.process(samples)
            if not correction.text:
                print("No speech recognized.")
                return
            print(f"Raw: {transcription.text}")
            if correction.replacements:
                print(f"Corrected: {correction.text}")
                print(
                    "Terms: "
                    + ", ".join(f"{old}={new}" for old, new in correction.replacements)
                )
            print(
                f"Decoded {transcription.audio_seconds:.1f}s in "
                f"{transcription.elapsed_seconds:.2f}s "
                f"(RTF {transcription.real_time_factor:.2f})"
            )
            if self.config.paste_result:
                _paste_text(correction.text, self.config.restore_clipboard)
            _beep(960)
        except Exception as exc:  # noqa: BLE001 - keep the hotkey listener alive
            print(f"Transcription failed: {exc}", file=sys.stderr)
            _beep(320)
        finally:
            with self._lock:
                self._busy = False

    def toggle(self) -> None:
        with self._lock:
            if self.recorder.recording:
                self._busy = True
                threading.Thread(target=self._finish_recording, daemon=True).start()
                return
            if self._busy:
                print("Still transcribing; hotkey ignored.")
                _beep(320)
                return
            try:
                self.recorder.start()
            except Exception as exc:  # noqa: BLE001 - device backends vary
                print(f"Could not start microphone: {exc}", file=sys.stderr)
                _beep(320)
                return
        print("Recording...")
        _beep(880)

    def stop(self) -> None:
        if self.recorder.recording:
            self.recorder.stop()
        if self._listener:
            self._listener.stop()

    def run(self) -> None:
        print(f"Model: {self.config.model_dir}")
        print(f"Technical correction rules: {self.corrections.rule_count}")
        if self.workspace:
            print(f"Repository context: {self.workspace}")
        print(f"Toggle dictation: {self.config.hotkey}")
        print(f"Exit: {self.config.exit_hotkey}")
        print("Audio and text stay on this machine.")
        self._listener = ShortcutListener(
            self.config.hotkey,
            self.toggle,
            self.config.exit_hotkey,
            self.stop,
        )
        self._listener.start()
        self._listener.wait()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Private technical dictation")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--record", type=float, metavar="SECONDS")
    parser.add_argument("--transcribe", type=Path, metavar="WAV")
    parser.add_argument("--no-paste", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.list_devices:
        for index, name in list_input_devices():
            print(f"{index}: {name}")
        return

    config = load_config(args.config)
    if args.no_paste:
        config.paste_result = False
    workspace = args.workspace.resolve() if args.workspace else config.workspace_path
    if workspace is None and (Path.cwd() / ".git").exists():
        workspace = Path.cwd().resolve()

    print("Loading local Parakeet model...")
    app = DictationApp(config, workspace)

    if args.transcribe:
        samples, sample_rate = load_wave(args.transcribe)
        transcription, correction = app.process(samples, sample_rate)
        print(f"Raw: {transcription.text}")
        print(f"Corrected: {correction.text}")
        print(
            f"Decoded {transcription.audio_seconds:.1f}s in "
            f"{transcription.elapsed_seconds:.2f}s "
            f"(RTF {transcription.real_time_factor:.2f})"
        )
        return

    if args.record is not None:
        print(f"Recording for {args.record:.1f} seconds...")
        samples = record_for(args.record, config.input_device)
        transcription, correction = app.process(samples)
        print(f"Raw: {transcription.text}")
        print(f"Corrected: {correction.text}")
        print(
            f"Decoded {transcription.audio_seconds:.1f}s in "
            f"{transcription.elapsed_seconds:.2f}s "
            f"(RTF {transcription.real_time_factor:.2f})"
        )
        return

    app.run()


if __name__ == "__main__":
    main()
