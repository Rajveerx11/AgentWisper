from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sherpa_onnx


@dataclass(frozen=True, slots=True)
class Transcription:
    text: str
    elapsed_seconds: float
    audio_seconds: float

    @property
    def real_time_factor(self) -> float:
        if self.audio_seconds <= 0:
            return 0.0
        return self.elapsed_seconds / self.audio_seconds


class ParakeetTranscriber:
    def __init__(self, model_dir: Path, num_threads: int = 4) -> None:
        self.model_dir = model_dir
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_dir / "encoder.int8.onnx"),
            decoder=str(model_dir / "decoder.int8.onnx"),
            joiner=str(model_dir / "joiner.int8.onnx"),
            tokens=str(model_dir / "tokens.txt"),
            num_threads=num_threads,
            sample_rate=16_000,
            feature_dim=80,
            decoding_method="greedy_search",
            model_type="nemo_transducer",
            provider="cpu",
        )

    def transcribe(
        self,
        samples: np.ndarray,
        sample_rate: int = 16_000,
    ) -> Transcription:
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        audio_seconds = len(samples) / sample_rate if sample_rate else 0.0
        if samples.size == 0:
            return Transcription("", 0.0, 0.0)

        stream = self.recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples)
        started = time.perf_counter()
        self.recognizer.decode_stream(stream)
        elapsed = time.perf_counter() - started
        return Transcription(
            text=stream.result.text.strip(),
            elapsed_seconds=elapsed,
            audio_seconds=audio_seconds,
        )
