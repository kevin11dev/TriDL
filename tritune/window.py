"""The native application window (Qt 6 / PySide6)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from . import server

log = logging.getLogger("tritune.window")

ICON = Path(__file__).parent / "web" / "icon.svg"


def run(url: str, storage: Path) -> int:
    """Show the TriTune window and block until it is closed."""
    from PySide6.QtCore import QObject, QSettings, Qt, QUrl, Signal
    from PySide6.QtGui import QColor, QIcon
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("TriTune")
    app.setOrganizationName("TriTune")
    app.setDesktopFileName("tritune")      # matches tritune.desktop (taskbar icon on Wayland)
    app.setWindowIcon(QIcon(str(ICON)))

    # A named profile keeps UI state (queue, volume) between runs.
    profile = QWebEngineProfile("tritune", app)
    profile.setPersistentStoragePath(str(storage))
    profile.setCachePath(str(storage / "cache"))
    page = QWebEnginePage(profile)
    page.setBackgroundColor(QColor("#000000"))
    page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)

    view = QWebEngineView()
    view.setPage(page)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    class Window(QMainWindow):
        def closeEvent(self, event):
            QSettings().setValue("geometry", self.saveGeometry())
            super().closeEvent(event)

    win = Window()
    win.setWindowTitle("TriTune")
    win.setMinimumSize(820, 560)
    win.resize(1280, 820)
    win.setStyleSheet("background: #000;")
    win.setCentralWidget(view)
    geometry = QSettings().value("geometry")
    if geometry:
        win.restoreGeometry(geometry)
    page.titleChanged.connect(lambda t: win.setWindowTitle(t if t and "127.0.0.1" not in t else "TriTune"))

    def bring_to_front():
        win.setWindowState(win.windowState() & ~Qt.WindowState.WindowMinimized)
        win.show()
        win.raise_()
        win.activateWindow()

    class Bridge(QObject):          # lets the backend thread reach the Qt thread
        raise_window = Signal()

    bridge = Bridge()
    bridge.raise_window.connect(bring_to_front)
    server.on_raise = bridge.raise_window.emit

    def loaded(ok):
        if not ok:
            log.error("the interface failed to load from %s", url)
            page.setHtml("<body style='background:#121212;color:#fff;font:16px sans-serif;padding:40px'>"
                         "<h2>TriTune could not load its interface</h2>"
                         "<p>See ~/.cache/tritune/tritune.log, then try: tritune --safe-graphics</p></body>")

    page.loadFinished.connect(loaded)
    page.renderProcessTerminated.connect(
        lambda status, code: log.error("render process ended (%s, exit code %s) - try: tritune --safe-graphics", status, code))

    view.load(QUrl(url))
    win.show()
    code = app.exec()
    server.on_raise = None
    # Tear down in order: the page must be gone before its profile.
    win.hide()
    page.deleteLater()
    app.processEvents()
    app.sendPostedEvents(None, 52)   # QEvent.DeferredDelete
    return code
