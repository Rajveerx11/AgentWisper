from __future__ import annotations

import ctypes
import logging
import multiprocessing
import threading
from importlib.resources import files
from typing import Any

import webview

from agent_whisper.desktop import DesktopController
from agent_whisper.overlay import OverlayProcess
from agent_whisper.windows_runtime import SingleInstance

logger = logging.getLogger(__name__)

LOADING_INTERFACE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body{height:100%;margin:0}body{display:grid;place-items:center;background:#f3f5f7;color:#263548;font:14px 'Segoe UI',sans-serif}.boot{display:grid;gap:8px;text-align:center}.boot b{color:#111c2e;font-size:18px}.boot i{width:8px;height:8px;margin:auto;border-radius:50%;background:#2f67e8;box-shadow:0 0 0 6px #e8efff}</style>
</head><body><div class="boot"><i></i><b>AgentWisper</b><span>Loading local workspace…</span></div></body></html>"""


def _load_interface() -> str:
    assets = files("agent_whisper").joinpath("web")
    html = assets.joinpath("index.html").read_text(encoding="utf-8")
    css = assets.joinpath("styles.css").read_text(encoding="utf-8")
    script = assets.joinpath("app.js").read_text(encoding="utf-8")
    return html.replace(
        "<!-- AGENTWISPER_STYLES -->",
        f"<style>{css}</style>",
    ).replace(
        "<!-- AGENTWISPER_SCRIPT -->",
        f"<script>{script}</script>",
    )


class DesktopApi:
    """Small, explicit bridge exposed to local AgentWisper JavaScript."""

    def __init__(self, controller: DesktopController) -> None:
        self._controller = controller
        self._window: webview.Window | None = None
        self._overlay: OverlayProcess | None = None

    def attach(self, window: webview.Window, overlay: OverlayProcess) -> None:
        self._window = window
        self._overlay = overlay

    def get_bootstrap(self) -> dict[str, Any]:
        return self._controller.bootstrap()

    def get_runtime(self) -> dict[str, Any]:
        return self._controller.runtime()

    def get_history(self) -> list[dict[str, Any]]:
        return self._controller.history()

    def toggle_recording(self) -> bool:
        return self._controller.toggle_recording()

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._controller.save_settings(payload)

    def clear_history(self) -> bool:
        self._controller.clear_history()
        return True

    def copy_latest(self) -> bool:
        return self._controller.copy_latest()

    def copy_text(self, text: str) -> bool:
        return self._controller.copy_text(text)

    def begin_hotkey_capture(self) -> bool:
        return self._controller.begin_hotkey_capture()

    def end_hotkey_capture(self) -> bool:
        return self._controller.end_hotkey_capture()

    def preview_hotkey(self, value: str) -> dict[str, str]:
        return self._controller.preview_hotkey(value)

    def hide_window(self) -> bool:
        if self._window:
            self._window.hide()
        if self._overlay:
            self._overlay.notice("Hold the hotkey whenever you want to dictate")
        return True


def _set_windows_app_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "AgentWisper.Desktop"
        )
    except (AttributeError, OSError):
        pass


def main() -> None:
    multiprocessing.freeze_support()
    _set_windows_app_id()

    instance = SingleInstance()
    if not instance.is_primary:
        instance.request_open()
        instance.close()
        return

    controller = DesktopController()
    controller.start()
    api = DesktopApi(controller)
    interface = _load_interface()
    window = webview.create_window(
        "AgentWisper",
        html=LOADING_INTERFACE,
        js_api=api,
        width=1000,
        height=640,
        min_size=(860, 580),
        background_color="#F3F5F7",
        text_select=True,
    )
    if window is None:
        controller.shutdown()
        instance.close()
        raise RuntimeError("Could not create AgentWisper window")

    def open_window() -> None:
        try:
            window.show()
            window.restore()
        except Exception:
            logger.debug("Window is not ready to reopen yet", exc_info=True)

    overlay = OverlayProcess(
        controller.runtime,
        controller.toggle_recording,
        open_window,
    )
    api.attach(window, overlay)

    def background_window() -> bool:
        try:
            controller.end_hotkey_capture()
        except Exception:
            logger.exception("Could not restore the hotkey listener before hiding")
        window.hide()
        overlay.notice("Hold the hotkey whenever you want to dictate")
        return False

    window.events.closing += background_window
    overlay.start()

    stop_instance_watcher = threading.Event()

    def watch_instance_requests() -> None:
        while not stop_instance_watcher.is_set():
            try:
                if instance.wait_for_open(250):
                    open_window()
            except OSError:
                return

    watcher = threading.Thread(
        target=watch_instance_requests,
        daemon=True,
        name="AgentWisperInstanceWatcher",
    )
    watcher.start()

    def load_desktop_interface() -> None:
        if not window.events.loaded.wait(15):
            logger.error("Initial WebView page did not finish loading")
            return
        window.load_html(interface)

    try:
        webview.start(
            load_desktop_interface,
            gui="edgechromium",
            debug=False,
            http_server=False,
            private_mode=True,
            user_agent="AgentWisper/0.5.0",
        )
    finally:
        stop_instance_watcher.set()
        overlay.stop()
        controller.shutdown()
        instance.close()


if __name__ == "__main__":
    main()
