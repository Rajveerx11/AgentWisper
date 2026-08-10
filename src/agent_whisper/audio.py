from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000


class AudioRecorder:
    def __init__(
        self,
        device: int | str | None = None,
        max_recording_seconds: int = 120,
    ) -> None:
        self.device = device
        self.max_samples = SAMPLE_RATE * max_recording_seconds
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._recorded_samples = 0
        self._level = 0.0

    @property
    def recording(self) -> bool:
        return self._stream is not None

    @property
    def level(self) -> float:
        with self._lock:
            return self._level

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        del frames, time_info
        if status:
            print(f"Audio warning: {status}")
        with self._lock:
            remaining = self.max_samples - self._recorded_samples
            if remaining > 0:
                chunk = indata[:remaining, 0].copy()
                self._chunks.append(chunk)
                self._recorded_samples += chunk.shape[0]
                rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size else 0.0
                self._level = min(1.0, rms * 10.0)

    def start(self) -> None:
        if self.recording:
            return
        with self._lock:
            self._chunks.clear()
            self._recorded_samples = 0
            self._level = 0.0
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        stream = self._stream
        self._stream = None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            self._level = 0.0
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            return np.concatenate(self._chunks).astype(np.float32, copy=False)


def encode_wave(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    import io

    clipped = np.clip(np.asarray(samples, dtype=np.float32).reshape(-1), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2").tobytes()
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(pcm)
    return output.getvalue()


def record_for(
    seconds: float,
    device: int | str | None = None,
) -> np.ndarray:
    frames = int(seconds * SAMPLE_RATE)
    audio = sd.rec(
        frames,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    return audio[:, 0]


def load_wave(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.readframes(source.getnframes())

    if sample_width != 2:
        raise ValueError("Only 16-bit PCM WAV files are supported")
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, sample_rate


def list_input_devices() -> list[tuple[int, str]]:
    devices: list[tuple[int, str]] = []
    for index, device in enumerate(sd.query_devices()):
        if int(device["max_input_channels"]) > 0:
            devices.append((index, str(device["name"])))
    return devices
