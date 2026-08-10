from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from agent_whisper import __version__
from agent_whisper.audio import encode_wave
from agent_whisper.transcriber import ParakeetTranscriber, Transcription

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    language: str = "en"
    prompt: str = ""


def validate_base_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urllib.parse.urlparse(raw)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(
            "Provider URL cannot contain credentials, query text, or fragments"
        )
    if parsed.scheme == "https" and parsed.netloc:
        return raw
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return raw
    raise ValueError("Use HTTPS, or HTTP only for localhost")


def transcription_endpoint(base_url: str) -> str:
    validated = validate_base_url(base_url)
    if validated.endswith("/audio/transcriptions"):
        return validated
    return validated + "/audio/transcriptions"


def _safe_field(value: str, field_name: str, max_length: int = 500) -> str:
    if not value or len(value) > max_length or "\r" in value or "\n" in value:
        raise ValueError(f"Invalid {field_name}")
    return value


def _multipart_audio(
    wav_bytes: bytes,
    model: str,
    language: str,
    prompt: str,
) -> tuple[bytes, str]:
    boundary = "----AgentWisper" + secrets.token_hex(16)
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    add_field("model", _safe_field(model, "model", 200))
    add_field("response_format", "json")
    add_field("temperature", "0")
    if language:
        add_field("language", _safe_field(language, "language", 10))
    if prompt:
        add_field("prompt", _safe_field(prompt, "prompt", 2_000))

    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n',
            b"Content-Type: audio/wav\r\n\r\n",
            wav_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(parts), boundary


class CloudTranscriber:
    def transcribe(
        self,
        samples: np.ndarray,
        sample_rate: int,
        request: ProviderRequest,
    ) -> Transcription:
        if not request.api_key:
            raise ValueError("API key is missing")
        endpoint = (
            GROQ_TRANSCRIPTION_URL
            if request.provider == "groq"
            else transcription_endpoint(request.base_url)
        )
        wav_bytes = encode_wave(samples, sample_rate)
        body, boundary = _multipart_audio(
            wav_bytes,
            request.model,
            request.language,
            request.prompt,
        )
        http_request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {request.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
                "User-Agent": f"AgentWisper/{__version__}",
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(http_request, timeout=60) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            message = "Cloud transcription failed"
            try:
                error_payload = exc.read(64_000)
                parsed = json.loads(error_payload)
                detail = parsed.get("error", {}).get("message")
                if isinstance(detail, str) and detail:
                    message = detail[:300]
            except (ValueError, TypeError, AttributeError):
                pass
            raise RuntimeError(message) from None
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach transcription provider: {exc.reason}"
            ) from None
        elapsed = time.perf_counter() - started
        if len(payload) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Provider response was unexpectedly large")
        try:
            data = json.loads(payload)
            text = data["text"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise RuntimeError("Provider returned an invalid response") from None
        if not isinstance(text, str):
            raise TypeError("Provider returned an invalid transcript")
        return Transcription(
            text=text.strip(),
            elapsed_seconds=elapsed,
            audio_seconds=len(samples) / sample_rate,
        )


class LocalTranscriberPool:
    def __init__(self) -> None:
        self._transcriber: ParakeetTranscriber | None = None
        self._model_dir: Path | None = None
        self._threads = 0
        self._lock = threading.Lock()

    def transcribe(
        self,
        samples: np.ndarray,
        sample_rate: int,
        model_dir: Path,
        num_threads: int,
    ) -> Transcription:
        with self._lock:
            if (
                self._transcriber is None
                or self._model_dir != model_dir
                or self._threads != num_threads
            ):
                self._transcriber = ParakeetTranscriber(model_dir, num_threads)
                self._model_dir = model_dir
                self._threads = num_threads
            return self._transcriber.transcribe(samples, sample_rate)
