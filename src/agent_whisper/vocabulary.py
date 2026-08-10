from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
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
MAX_REPOSITORY_TERMS = 500
MAX_REPOSITORY_FILES = 2_000
MAX_MANIFEST_BYTES = 1_000_000
MAX_MANIFEST_TERMS = 2_000


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


def _read_manifest_text(path: Path) -> str | None:
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            return None
        return raw.decode("utf-8")
    except (OSError, UnicodeError):
        return None


def _add_manifest_terms(
    terms: set[str],
    values: Iterable[str],
    remaining: int,
) -> int:
    inspected = 0
    for value in values:
        if inspected >= remaining:
            break
        inspected += 1
        if value:
            terms.add(value)
    return inspected


def _manifest_terms(workspace: Path, file_budget: int) -> tuple[set[str], int]:
    terms: set[str] = set()
    files_read = 0
    entries_inspected = 0

    package_json = workspace / "package.json"
    if files_read < file_budget and package_json.is_file():
        files_read += 1
        try:
            content = _read_manifest_text(package_json)
            data = json.loads(content) if content is not None else None
            if isinstance(data, dict):
                for section in (
                    "dependencies",
                    "devDependencies",
                    "peerDependencies",
                ):
                    dependencies = data.get(section, {})
                    if isinstance(dependencies, dict):
                        entries_inspected += _add_manifest_terms(
                            terms,
                            map(str, dependencies),
                            MAX_MANIFEST_TERMS - entries_inspected,
                        )
        except json.JSONDecodeError:
            pass

    pyproject = workspace / "pyproject.toml"
    if files_read < file_budget and pyproject.is_file():
        files_read += 1
        try:
            content = _read_manifest_text(pyproject)
            data = tomllib.loads(content) if content is not None else {}
            project = data.get("project", {})
            if isinstance(project, dict):
                dependencies = project.get("dependencies", [])
                if isinstance(dependencies, list):
                    entries_inspected += _add_manifest_terms(
                        terms,
                        (
                            _package_name(item)
                            for item in dependencies
                            if isinstance(item, str)
                        ),
                        MAX_MANIFEST_TERMS - entries_inspected,
                    )
            tool = data.get("tool", {})
            poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
            dependencies = (
                poetry.get("dependencies", {}) if isinstance(poetry, dict) else {}
            )
            if isinstance(dependencies, dict):
                entries_inspected += _add_manifest_terms(
                    terms,
                    (str(name) for name in dependencies if name.lower() != "python"),
                    MAX_MANIFEST_TERMS - entries_inspected,
                )
        except tomllib.TOMLDecodeError:
            pass

    cargo = workspace / "Cargo.toml"
    if files_read < file_budget and cargo.is_file():
        files_read += 1
        try:
            content = _read_manifest_text(cargo)
            data = tomllib.loads(content) if content is not None else {}
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                dependencies = data.get(section, {})
                if isinstance(dependencies, dict):
                    entries_inspected += _add_manifest_terms(
                        terms,
                        map(str, dependencies),
                        MAX_MANIFEST_TERMS - entries_inspected,
                    )
        except tomllib.TOMLDecodeError:
            pass

    return terms, files_read


def scan_repository(workspace: Path, max_files: int = 2_000) -> dict[str, list[str]]:
    if not workspace.is_dir():
        return {}

    file_limit = max(1, min(int(max_files), MAX_REPOSITORY_FILES))
    canonical_terms, visited = _manifest_terms(workspace, file_limit)
    skipped = {name.casefold() for name in SKIP_DIRECTORIES}
    for root, directories, filenames in os.walk(
        workspace,
        topdown=True,
        onerror=lambda _error: None,
        followlinks=False,
    ):
        directories[:] = sorted(
            name for name in directories if name.casefold() not in skipped
        )
        for filename in sorted(filenames):
            if visited >= file_limit:
                break
            visited += 1
            stem = Path(root, filename).stem
            if _is_distinct_identifier(stem) and 3 <= len(stem) <= 80:
                canonical_terms.add(stem)
        if visited >= file_limit:
            break

    result: dict[str, list[str]] = {}
    for canonical in sorted(canonical_terms, key=str.casefold):
        spoken = identifier_to_spoken(canonical)
        if spoken and spoken.casefold() != canonical.casefold():
            result[canonical] = [spoken]
            if len(result) >= MAX_REPOSITORY_TERMS:
                break
    return result


@dataclass(slots=True)
class _TrieNode:
    children: dict[str, _TrieNode] = field(default_factory=dict)
    rule_index: int | None = None


def _normalize_for_match(text: str) -> tuple[str, list[int], list[int]]:
    normalized: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    index = 0
    while index < len(text):
        start = index
        if text[index].isspace():
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            normalized.append(" ")
            starts.append(start)
            ends.append(index)
            continue

        folded = text[index].casefold()
        index += 1
        for character in folded:
            normalized.append(character)
            starts.append(start)
            ends.append(index)
    return "".join(normalized), starts, ends


def _is_word_character(character: str) -> bool:
    return character == "_" or character.isalnum()


class CorrectionEngine:
    def __init__(
        self,
        custom_terms: dict[str, Iterable[str]] | None = None,
        repository_terms: dict[str, Iterable[str]] | None = None,
    ) -> None:
        rules: list[tuple[str, str]] = []
        seen_aliases: set[str] = set()
        for source in (
            custom_terms or {},
            repository_terms or {},
            TECHNICAL_TERMS,
        ):
            for canonical, aliases in source.items():
                for alias in aliases:
                    clean_alias = re.sub(r"\s+", " ", str(alias)).strip()
                    alias_key = clean_alias.casefold()
                    if clean_alias and alias_key not in seen_aliases:
                        seen_aliases.add(alias_key)
                        rules.append((clean_alias, canonical))
        self._rules = sorted(rules, key=lambda item: len(item[0]), reverse=True)
        self._trie = _TrieNode()
        for rule_index, (alias, _canonical) in enumerate(self._rules):
            node = self._trie
            normalized_alias, _starts, _ends = _normalize_for_match(alias)
            for character in normalized_alias:
                node = node.children.setdefault(character, _TrieNode())
            node.rule_index = rule_index

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def correct(self, text: str) -> CorrectionResult:
        if not text or not self._trie.children:
            return CorrectionResult(text, ())

        normalized, starts, ends = _normalize_for_match(text)
        candidates: list[tuple[int, int, int]] = []
        for start in range(len(normalized)):
            if start and _is_word_character(normalized[start - 1]):
                continue
            node = self._trie
            for end in range(start, len(normalized)):
                node = node.children.get(normalized[end])
                if node is None:
                    break
                if node.rule_index is not None and (
                    end + 1 == len(normalized)
                    or not _is_word_character(normalized[end + 1])
                ):
                    candidates.append((starts[start], ends[end], node.rule_index))

        selected: list[tuple[int, int, int]] = []
        cursor = 0
        for candidate in sorted(candidates, key=lambda item: (item[0], item[2])):
            if candidate[0] >= cursor:
                selected.append(candidate)
                cursor = candidate[1]
        if not selected:
            return CorrectionResult(text, ())

        pieces: list[str] = []
        applied: list[tuple[str, str]] = []
        cursor = 0
        for start, end, rule_index in selected:
            alias, canonical = self._rules[rule_index]
            pieces.extend((text[cursor:start], canonical))
            applied.append((alias, canonical))
            cursor = end
        pieces.append(text[cursor:])
        return CorrectionResult("".join(pieces), tuple(applied))
