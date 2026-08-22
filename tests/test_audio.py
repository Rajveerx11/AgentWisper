import numpy as np

from agent_whisper.audio import trim_silence


def test_trim_silence_keeps_padding_around_speech() -> None:
    sample_rate = 1_000
    audio = np.concatenate(
        (
            np.zeros(1_000, dtype=np.float32),
            np.full(500, 0.1, dtype=np.float32),
            np.zeros(1_000, dtype=np.float32),
        )
    )

    trimmed = trim_silence(audio, sample_rate, padding_seconds=0.2)

    assert trimmed.size == 900
    assert np.allclose(trimmed[200:700], 0.1)


def test_trim_silence_keeps_quiet_and_short_recordings_unchanged() -> None:
    quiet = np.full(2_000, 0.0005, dtype=np.float32)
    short = np.ones(400, dtype=np.float32)

    assert np.array_equal(trim_silence(quiet, 1_000), quiet)
    assert np.array_equal(trim_silence(short, 1_000), short)
