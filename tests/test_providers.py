import json
import urllib.request

import numpy as np
import pytest

from agent_whisper.audio import encode_wave
from agent_whisper.providers import (
    CloudTranscriber,
    ProviderRequest,
    transcription_endpoint,
    validate_base_url,
)


def test_base_url_validation() -> None:
    assert validate_base_url("https://example.com/v1/") == "https://example.com/v1"
    assert validate_base_url("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1"
    with pytest.raises(ValueError):
        validate_base_url("http://example.com/v1")
    with pytest.raises(ValueError):
        validate_base_url("file:///tmp/key")
    with pytest.raises(ValueError):
        validate_base_url("https://secret@example.com/v1")
    with pytest.raises(ValueError):
        validate_base_url("https://example.com/v1?token=secret")


def test_transcription_endpoint() -> None:
    assert (
        transcription_endpoint("https://example.com/v1")
        == "https://example.com/v1/audio/transcriptions"
    )


def test_encode_wave_has_riff_header() -> None:
    encoded = encode_wave(np.zeros(1_600, dtype=np.float32))
    assert encoded[:4] == b"RIFF"
    assert b"WAVE" in encoded[:16]


def test_cloud_transcription_request(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps({"text": "hello"}).encode()

    captured: dict[str, urllib.request.Request] = {}

    def fake_open(request, timeout):
        captured["request"] = request
        assert timeout == 60
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    result = CloudTranscriber().transcribe(
        np.zeros(1_600, dtype=np.float32),
        16_000,
        ProviderRequest(
            provider="groq",
            model="whisper-large-v3-turbo",
            api_key="test-key",
            language="en",
        ),
    )
    assert result.text == "hello"
    assert captured["request"].full_url.startswith("https://api.groq.com/")
    assert captured["request"].get_header("Authorization") == "Bearer test-key"
    assert captured["request"].get_header("User-agent") == "AgentWisper/0.4.0"
