from agent_whisper import windows_runtime


class _FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_start_with_windows_writes_current_command(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        windows_runtime.winreg,
        "CreateKeyEx",
        lambda *args: _FakeKey(),
    )
    monkeypatch.setattr(
        windows_runtime.winreg,
        "SetValueEx",
        lambda *args: calls.append(args),
    )
    monkeypatch.setattr(windows_runtime, "startup_command", lambda: '"app.exe"')

    windows_runtime.set_start_with_windows(True)

    assert calls[0][1:] == (
        "AgentWisper",
        0,
        windows_runtime.winreg.REG_SZ,
        '"app.exe"',
    )


def test_start_with_windows_removal_is_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(
        windows_runtime.winreg,
        "CreateKeyEx",
        lambda *args: _FakeKey(),
    )
    monkeypatch.setattr(
        windows_runtime.winreg,
        "DeleteValue",
        lambda *_args: (_ for _ in ()).throw(FileNotFoundError()),
    )

    windows_runtime.set_start_with_windows(False)
