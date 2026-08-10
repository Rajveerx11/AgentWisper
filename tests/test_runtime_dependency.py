import os
from pathlib import Path

import pytest
import sherpa_onnx


@pytest.mark.skipif(os.name != "nt", reason="AgentWisper currently targets Windows")
def test_sherpa_onnx_runtime_dll_is_installed() -> None:
    runtime = Path(sherpa_onnx.__file__).parent / "lib" / "onnxruntime.dll"
    assert runtime.is_file()
    assert runtime.stat().st_size > 1_000_000
