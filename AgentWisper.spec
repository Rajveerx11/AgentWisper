from pathlib import Path
from importlib.metadata import distribution

from PyInstaller.utils.hooks import collect_all


datas, binaries, hiddenimports = collect_all("sherpa_onnx")
datas += [(str(Path("src/agent_whisper/web")), "agent_whisper/web")]

runtime_distributions = (
    "numpy",
    "pynput",
    "six",
    "pyperclip",
    "pywebview",
    "bottle",
    "proxy-tools",
    "pythonnet",
    "clr-loader",
    "cffi",
    "typing-extensions",
    "sherpa-onnx",
    "sherpa-onnx-core",
    "sounddevice",
    "pycparser",
)
license_prefixes = ("license", "copying", "notice")
for distribution_name in runtime_distributions:
    package = distribution(distribution_name)
    for entry in package.files or ():
        relative = Path(str(entry))
        if not relative.name.casefold().startswith(license_prefixes):
            continue
        source = Path(package.locate_file(entry))
        if source.is_file():
            destination = Path("licenses") / distribution_name / relative.parent
            datas.append((str(source), str(destination)))

datas += [
    (str(Path("LICENSE")), "."),
    (str(Path("NOTICE.md")), "."),
    (str(Path("THIRD_PARTY_NOTICES.md")), "."),
    (
        str(Path("third_party/proxy-tools/LICENSE.txt")),
        "licenses/proxy-tools",
    ),
]

analysis = Analysis(
    ["src/agent_whisper/gui.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3", "gi"],
    noarchive=False,
    optimize=1,
)
archive = PYZ(analysis.pure)

executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="AgentWisper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AgentWisper",
)
