"""Nenhuma tela pode mostrar um widget sem pai (no Windows isso vira uma janelinha 'Chinese Control' piscando)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


def test_no_loose_windows(monkeypatch, tmp_path):
    from PySide6.QtCore import QEvent, QObject, QThreadPool
    from PySide6.QtWidgets import QApplication, QDialog, QMenu
    app = QApplication.instance() or QApplication([])
    from lolitos import i18n
    i18n.set_table("pt", {})
    import lolitos.catalog  # noqa: F401
    from lolitos.core import settings
    from lolitos.modules import appicons, covers, games, winget
    from lolitos.ui import widgets
    # nada de janelas que esperam clique (boas-vindas, avisos, busca de atualização)
    monkeypatch.setattr(widgets, "confirm", lambda *a, **k: False)
    monkeypatch.setattr(widgets, "info", lambda *a, **k: None)
    real_get = settings.get
    monkeypatch.setattr(settings, "get", lambda k, d=None: {"seen_analysis": True, "check_updates": False}.get(
        k, real_get(k, d) if d is not None else real_get(k)))
    G = games.Game
    monkeypatch.setattr(games, "all_games", lambda *a, **k: [G("steam:1", "Jogo A", "steam", "C:/x", "x"),
                                                              G("epic:2", "Jogo B", "epic", "C:/x", "x")])
    monkeypatch.setattr(covers, "fetch", lambda g: None)
    monkeypatch.setattr(appicons, "fetch", lambda wid, link: None)
    monkeypatch.setattr(winget, "installed_ids", lambda: set())
    monkeypatch.setattr(winget, "ensure_winget", lambda: False)
    from lolitos.ui import theme
    from lolitos.ui.main_window import MainWindow
    shown = []
    holder = {}

    class Spy(QObject):
        def eventFilter(self, o, e):
            if e.type() == QEvent.Show and isinstance(o, QtWidgets.QWidget) and o.isWindow() \
                    and o is not holder.get("w") and not isinstance(o, (QDialog, QMenu)) \
                    and type(o).__name__ not in ("QTipLabel", "Overlay", "QComboBoxPrivateContainer"):
                shown.append(type(o).__name__)
            return False
    spy = Spy()
    app.installEventFilter(spy)
    theme.use("dark")
    app.setStyleSheet(theme.qss())
    w = MainWindow()
    holder["w"] = w
    w.show()
    for k in list(w.index):
        w.go(k)
        QThreadPool.globalInstance().waitForDone(3000)
        app.processEvents()
        pg = w.stack.currentWidget()
        if hasattr(pg, "q"):
            pg.q.setText("a")
            app.processEvents()
            pg.q.setText("")
            app.processEvents()
    app.removeEventFilter(spy)
    w.overlay.hide()
    w.tray.hide()
    w.hide()
    assert shown == [], f"widgets mostrados como janela solta: {sorted(set(shown))}"
