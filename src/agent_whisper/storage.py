from __future__ import annotations

import base64
import ctypes
import json
import os
import sqlite3
import threading
from ctypes import wintypes
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_whisper.hotkeys import DEFAULT_HOTKEY, LEGACY_DEFAULT_HOTKEY

APP_NAME = "AgentWisper"
MAX_LEARNED_MAPPINGS = 500
MAX_ALIASES_PER_TERM = 20


def app_data_dir() -> Path:
    root = os.environ.get("APPDATA")
    if not root:
        raise RuntimeError("APPDATA is not defined")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(slots=True)
class UserSettings:
    settings_version: int = 3
    provider: str = "local"
    hotkey: str = DEFAULT_HOTKEY
    input_device: int | str | None = None
    local_model_dir: str = ""
    groq_model: str = "whisper-large-v3-turbo"
    custom_base_url: str = "https://api.openai.com/v1"
    custom_model: str = "gpt-4o-mini-transcribe"
    paste_result: bool = True
    restore_clipboard: bool = True
    language: str = "en"
    num_threads: int = 4
    project_path: str = ""


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "settings.json"

    def load(self) -> UserSettings:
        if not self.path.is_file():
            return UserSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return UserSettings()
        try:
            settings_version = int(raw.get("settings_version", 1))
        except (TypeError, ValueError):
            settings_version = 1
        if (
            settings_version < 2
            and raw.get("hotkey", LEGACY_DEFAULT_HOTKEY) == LEGACY_DEFAULT_HOTKEY
        ):
            raw["hotkey"] = DEFAULT_HOTKEY
        if settings_version < 3:
            raw["settings_version"] = 3
        defaults = asdict(UserSettings())
        values = {key: raw.get(key, default) for key, default in defaults.items()}
        return UserSettings(**values)

    def save(self, settings: UserSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class SecretStore:
    """Windows DPAPI-backed secrets, encrypted for the current Windows user."""

    def __init__(self, path: Path | None = None) -> None:
        if os.name != "nt":
            raise RuntimeError("SecretStore currently requires Windows DPAPI")
        self.path = path or app_data_dir() / "secrets.json"
        self._crypt32 = ctypes.windll.crypt32
        self._kernel32 = ctypes.windll.kernel32
        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p
        self._lock = threading.Lock()

    @staticmethod
    def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
        buffer = ctypes.create_string_buffer(data)
        blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        return blob, buffer

    def _protect(self, value: str) -> str:
        plain = value.encode("utf-8")
        input_blob, input_buffer = self._blob(plain)
        output_blob = _DataBlob()
        if not self._crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "AgentWisper API key",
            None,
            None,
            None,
            0,
            ctypes.byref(output_blob),
        ):
            raise ctypes.WinError()
        _ = input_buffer
        try:
            encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
            return base64.b64encode(encrypted).decode("ascii")
        finally:
            self._kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))

    def _unprotect(self, value: str) -> str:
        encrypted = base64.b64decode(value, validate=True)
        input_blob, input_buffer = self._blob(encrypted)
        output_blob = _DataBlob()
        if not self._crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(output_blob),
        ):
            raise ctypes.WinError()
        _ = input_buffer
        try:
            plain = ctypes.string_at(output_blob.pbData, output_blob.cbData)
            return plain.decode("utf-8")
        finally:
            self._kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))

    def _read(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {str(key): str(value) for key, value in data.items()}
        except (OSError, json.JSONDecodeError, TypeError):
            return {}

    def set(self, name: str, value: str) -> None:
        if not name or len(name) > 100:
            raise ValueError("Invalid secret name")
        with self._lock:
            data = self._read()
            if value:
                data[name] = self._protect(value)
            else:
                data.pop(name, None)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(self.path)

    def get(self, name: str) -> str:
        with self._lock:
            encrypted = self._read().get(name)
        if not encrypted:
            return ""
        try:
            return self._unprotect(encrypted)
        except (ValueError, OSError):
            return ""

    def has(self, name: str) -> bool:
        return bool(self.get(name))


def _vocabulary_value(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Enter {label}")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"Enter {label}")
    if len(cleaned) > 120 or any(ord(character) < 32 for character in cleaned):
        raise ValueError(f"{label.capitalize()} is too long or contains control text")
    return cleaned


class VocabularyStore:
    """Atomic local storage for corrections explicitly taught by the user."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "vocabulary.json"
        self._lock = threading.Lock()

    def _read(self) -> dict[str, list[str]]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            records = payload.get("terms", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            return {}

        terms: dict[str, list[str]] = {}
        seen_aliases: set[str] = set()
        if not isinstance(records, list):
            return terms
        for record in records:
            remaining = MAX_LEARNED_MAPPINGS - sum(
                len(aliases) for aliases in terms.values()
            )
            if remaining <= 0:
                break
            if not isinstance(record, dict):
                continue
            try:
                canonical = _vocabulary_value(record.get("canonical", ""), "spelling")
            except (TypeError, ValueError):
                continue
            aliases = record.get("aliases", [])
            if not isinstance(aliases, list):
                continue
            cleaned_aliases: list[str] = []
            for alias in aliases[: min(MAX_ALIASES_PER_TERM, remaining)]:
                try:
                    cleaned = _vocabulary_value(alias, "heard phrase")
                except (TypeError, ValueError):
                    continue
                if (
                    cleaned.casefold() != canonical.casefold()
                    and cleaned.casefold()
                    not in {item.casefold() for item in cleaned_aliases}
                    and cleaned.casefold() not in seen_aliases
                ):
                    cleaned_aliases.append(cleaned)
                    seen_aliases.add(cleaned.casefold())
            if cleaned_aliases:
                terms[canonical] = cleaned_aliases
        return terms

    def _write(self, terms: dict[str, list[str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {"canonical": canonical, "aliases": aliases}
            for canonical, aliases in sorted(
                terms.items(), key=lambda item: item[0].casefold()
            )
        ]
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"version": 1, "terms": records}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def load(self) -> dict[str, list[str]]:
        with self._lock:
            return self._read()

    def add(self, canonical: str, alias: str) -> dict[str, list[str]]:
        canonical = _vocabulary_value(canonical, "exact spelling")
        alias = _vocabulary_value(alias, "heard phrase")
        if canonical.casefold() == alias.casefold():
            raise ValueError("Heard phrase and exact spelling must be different")

        with self._lock:
            terms = self._read()
            existing_name = next(
                (name for name in terms if name.casefold() == canonical.casefold()),
                None,
            )
            name = existing_name or canonical
            aliases = terms.setdefault(name, [])
            if alias.casefold() in {item.casefold() for item in aliases}:
                return terms
            alias_key = alias.casefold()
            for other_name in list(terms):
                if other_name == name:
                    continue
                terms[other_name] = [
                    item for item in terms[other_name] if item.casefold() != alias_key
                ]
                if not terms[other_name]:
                    terms.pop(other_name)
            if len(aliases) >= MAX_ALIASES_PER_TERM:
                raise ValueError("This spelling already has the maximum spoken forms")
            if sum(len(items) for items in terms.values()) >= MAX_LEARNED_MAPPINGS:
                raise ValueError("Learned vocabulary limit reached")
            aliases.append(alias)
            self._write(terms)
            return terms

    def remove(self, canonical: str, alias: str) -> dict[str, list[str]]:
        canonical = _vocabulary_value(canonical, "exact spelling")
        alias = _vocabulary_value(alias, "heard phrase")
        with self._lock:
            terms = self._read()
            name = next(
                (item for item in terms if item.casefold() == canonical.casefold()),
                None,
            )
            if name is None:
                return terms
            terms[name] = [
                item for item in terms[name] if item.casefold() != alias.casefold()
            ]
            if not terms[name]:
                terms.pop(name)
            self._write(terms)
            return terms


@dataclass(frozen=True, slots=True)
class HistoryItem:
    id: int
    created_at: str
    text: str
    raw_text: str
    provider: str
    model: str
    audio_seconds: float
    elapsed_seconds: float


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "history.db"
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    text TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    audio_seconds REAL NOT NULL,
                    elapsed_seconds REAL NOT NULL
                )
                """
            )

    def add(
        self,
        text: str,
        raw_text: str,
        provider: str,
        model: str,
        audio_seconds: float,
        elapsed_seconds: float,
    ) -> int:
        created_at = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transcripts
                    (created_at, text, raw_text, provider, model, audio_seconds, elapsed_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    text,
                    raw_text,
                    provider,
                    model,
                    audio_seconds,
                    elapsed_seconds,
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int = 200) -> list[HistoryItem]:
        safe_limit = max(1, min(int(limit), 1_000))
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, text, raw_text, provider, model,
                       audio_seconds, elapsed_seconds
                FROM transcripts
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [HistoryItem(**dict(row)) for row in rows]

    def count(self) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM transcripts").fetchone()
        return int(row[0])

    def clear(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM transcripts")
