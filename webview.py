from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice, QObject, QUrl, Qt
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView

WEB_DIR = Path(__file__).resolve().parent / "web"


def _qwebchannel_source() -> str:
    """qwebchannel.js ships inside the QtWebChannel module; a file:// page can't load qrc: itself."""
    resource = QFile(":/qtwebchannel/qwebchannel.js")
    if not resource.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError("qwebchannel.js is missing from the Qt resources")
    try:
        return bytes(resource.readAll().data()).decode("utf-8")
    finally:
        resource.close()


def _script(name: str, source: str, at_document_ready: bool = False) -> QWebEngineScript:
    script = QWebEngineScript()
    script.setName(name)
    script.setInjectionPoint(
        QWebEngineScript.InjectionPoint.DocumentReady
        if at_document_ready
        else QWebEngineScript.InjectionPoint.DocumentCreation
    )
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(False)
    script.setSourceCode(source)
    return script


def _icon_sprite_script() -> QWebEngineScript:
    """Chromium blocks <use href="other.svg#id"> across file:// documents, so inject the sprite."""
    sprite = (WEB_DIR / "icons.html").read_text(encoding="utf-8")
    return _script(
        "icons",
        f"document.body.insertAdjacentHTML('afterbegin', {json.dumps(sprite)});",
        at_document_ready=True,
    )


def build_web_view(page: str, bridge: QObject, *, transparent: bool) -> QWebEngineView:
    """A web view wired to `bridge` (exposed to JS as `backend`) and showing web/<page>."""
    view = QWebEngineView()
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    channel = QWebChannel(view)
    channel.registerObject("backend", bridge)
    view.page().setWebChannel(channel)

    if transparent:
        view.page().setBackgroundColor(QColor(Qt.GlobalColor.transparent))

    view.page().scripts().insert(_script("qwebchannel", _qwebchannel_source()))
    view.page().scripts().insert(_icon_sprite_script())

    view.setUrl(QUrl.fromLocalFile(str(WEB_DIR / page)))
    return view
