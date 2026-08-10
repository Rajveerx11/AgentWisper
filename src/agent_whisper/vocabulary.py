from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

TECHNICAL_TERMS: dict[str, tuple[str, ...]] = {
    "AgentWisper": ("agent whisper", "agent wisper"),
    "Supabase": ("super base", "zupa base", "supa base", "superbase"),
    "PostgreSQL": (
        "post grass sequel",
        "post grass sql",
        "postgrass sql",
        "post gres q l",
        "postgre sequel",
    ),
    "pgvector": ("p g vector", "pg vector"),
    "Kubernetes": ("kuber net ease", "kuber netes", "cube er net ease"),
    "kubectl": ("cube control", "kube control", "cube c t l"),
    "Cloudflare": ("cloud flare",),
    "Vercel": ("ver sell", "versel"),
    "Next.js": ("next j s", "next jay ess", "next js"),
    "Node.js": ("node j s", "node jay ess", "node js"),
    "TypeScript": ("type script",),
    "JavaScript": ("java script",),
    "GitHub": ("git hub",),
    "GitLab": ("git lab",),
    "OpenAI": ("open a i", "open ai"),
    "Claude Code": ("clawed code", "cloud code"),
    "Codex": ("code x", "cod x"),
    "Cursor": ("curser",),
    "FastAPI": ("fast a p i", "fast api"),
    "GraphQL": ("graph q l", "graph queue ell"),
    "shadcn/ui": ("shad c n", "shad c n u i", "shadcn ui"),
    "Tailwind CSS": ("tailwind c s s",),
    "llama.cpp": ("llama c p p", "lama c p p"),
    "Ollama": ("o llama", "oh llama"),
    "Hugging Face": ("huggingface",),
    "PyTorch": ("pie torch",),
    "TensorFlow": ("tensor flow",),
    "ONNX": ("on n x", "o n n x"),
    "CUDA": ("cooda", "cuda"),
    "Redis": ("red is",),
    "MongoDB": ("mongo d b",),
    "LangChain": ("lang chain",),
    "LangGraph": ("lang graph",),
    "MCP": ("m c p",),
    "API": ("a p i",),
    "CLI": ("c l i",),
    "LLM": ("l l m",),
    "RAG": ("r a g",),
    "JSON": ("j son", "jay son"),
    "YAML": ("yam l",),
    "SQL": ("s q l",),
}

SKIP_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".venv",
    "node_modules",
    "target",
    "dist",
    "build",
    "vendor",
    "__pycache__",
}


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    text: str
    replacements: tuple[tuple[str, str], ...]


def identifier_to_spoken(identifier: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier)
    value = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", value)
    value = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", value)
    value = re.sub(r"[@_./\\-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def _is_distinct_identifier(value: str) -> bool:
    return bool(
        re.search(r"[_./-]", value)
        or re.search(r"[a-z][A-Z]", value)
        or re.search(r"[A-Za-z][0-9]|[0-9][A-Za-z]", value)
    )


def _package_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[ ;]", requirement, maxsplit=1)[0].strip()


def _manifest_terms(workspace: Path) -> set[str]:
    terms: set[str] = set()

    package_json = workspace / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                terms.update(str(name) for name in data.get(section, {}))
        except (OSError, json.JSONDecodeError):
            pass

    pyproject = workspace / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = data.get("project", {})
            terms.update(
                _package_name(item) for item in project.get("dependencies", [])
            )
            poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            terms.update(str(name) for name in poetry if name.lower() != "python")
        except (OSError, tomllib.TOMLDecodeError):
            pass

    cargo = workspace / "Cargo.toml"
    if cargo.is_file():
        try:
            data = tomllib.loads(cargo.read_text(encoding="utf-8"))
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                terms.update(str(name) for name in data.get(section, {}))
        except (OSError, tomllib.TOMLDecodeError):
            pass

    return {term for term in terms if term}


def scan_repository(workspace: Path, max_files: int = 2_000) -> dict[str, list[str]]:
    if not workspace.is_dir():
        return {}

    canonical_terms = _manifest_terms(workspace)
    visited = 0
    for path in workspace.rglob("*"):
        if visited >= max_files:
            break
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        if not path.is_file():
            continue
        visited += 1
        stem = path.stem
        if _is_distinct_identifier(stem) and 3 <= len(stem) <= 80:
            canonical_terms.add(stem)

    result: dict[str, list[str]] = {}
    for canonical in sorted(canonical_terms, key=str.casefold):
        spoken = identifier_to_spoken(canonical)
        if spoken and spoken.casefold() != canonical.casefold():
            result[canonical] = [spoken]
    return result


def _phrase_pattern(alias: str) -> re.Pattern[str]:
    pieces = [re.escape(piece) for piece in alias.split()]
    body = r"\s+".join(pieces)
    return re.compile(rf"(?<!\w){body}(?!\w)", flags=re.IGNORECASE)


class CorrectionEngine:
    def __init__(
        self,
        custom_terms: dict[str, Iterable[str]] | None = None,
        repository_terms: dict[str, Iterable[str]] | None = None,
    ) -> None:
        merged: dict[str, list[str]] = {
            canonical: list(aliases) for canonical, aliases in TECHNICAL_TERMS.items()
        }
        for source in (repository_terms or {}, custom_terms or {}):
            for canonical, aliases in source.items():
                merged.setdefault(canonical, []).extend(str(alias) for alias in aliases)

        rules: list[tuple[re.Pattern[str], str, str]] = []
        for canonical, aliases in merged.items():
            for alias in aliases:
                clean_alias = re.sub(r"\s+", " ", alias).strip()
                if clean_alias:
                    rules.append((_phrase_pattern(clean_alias), clean_alias, canonical))
        self._rules = sorted(rules, key=lambda item: len(item[1]), reverse=True)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def correct(self, text: str) -> CorrectionResult:
        corrected = text
        applied: list[tuple[str, str]] = []
        for pattern, alias, canonical in self._rules:
            corrected, count = pattern.subn(canonical, corrected)
            if count:
                applied.append((alias, canonical))
        return CorrectionResult(corrected, tuple(applied))
