from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Self

ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258


class SingleInstance:
    """Windows named-object guard with a signal for reopening the primary UI."""

    def __init__(self, name: str = "AgentWisper.Desktop") -> None:
        self._kernel32 = None
        self._mutex: int | None = None
        self._open_event: int | None = None
        self.is_primary = True
        if os.name != "nt":
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateEventW.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateEventW.restype = wintypes.HANDLE
        kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        kernel32.SetEvent.restype = wintypes.BOOL
        kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
        kernel32.ResetEvent.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        mutex = kernel32.CreateMutexW(None, False, f"Local\\{name}.Mutex")
        if not mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        already_exists = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        open_event = kernel32.CreateEventW(
            None, True, False, f"Local\\{name}.OpenWindow"
        )
        if not open_event:
            kernel32.CloseHandle(mutex)
            raise ctypes.WinError(ctypes.get_last_error())

        self._kernel32 = kernel32
        self._mutex = int(mutex)
        self._open_event = int(open_event)
        self.is_primary = not already_exists

    def request_open(self) -> None:
        if self._kernel32 is not None and self._open_event is not None:
            self._kernel32.SetEvent(self._open_event)

    def wait_for_open(self, timeout_ms: int = 250) -> bool:
        if self._kernel32 is None or self._open_event is None:
            return False
        result = self._kernel32.WaitForSingleObject(self._open_event, timeout_ms)
        if result == WAIT_OBJECT_0:
            self._kernel32.ResetEvent(self._open_event)
            return True
        if result != WAIT_TIMEOUT:
            raise ctypes.WinError()
        return False

    def close(self) -> None:
        if self._kernel32 is None:
            return
        if self._open_event is not None:
            self._kernel32.CloseHandle(self._open_event)
            self._open_event = None
        if self._mutex is not None:
            self._kernel32.CloseHandle(self._mutex)
            self._mutex = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
