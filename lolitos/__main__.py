"""Ponto de entrada: python -m lolitos  [--tray] [--no-admin]"""
from __future__ import annotations

import logging
import sys


def main() -> int:
    from lolitos.core.system import IS_WIN, data_dir, is_admin, relaunch_as_admin

    sys.setswitchinterval(0.001)   # a thread da interface recupera o GIL mais rápido
    logging.basicConfig(filename=str(data_dir() / "lolitos.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if IS_WIN and not is_admin() and "--no-admin" not in sys.argv:
        if relaunch_as_admin():
            return 0     # a cópia elevada assume

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication

    lock = QLockFile(str(data_dir() / "app.lock"))
    if not lock.tryLock(100):
        return 0         # já existe uma janela aberta

    if IS_WIN:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Lolitos.Otimizacoes")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    from lolitos import APP_NAME
    app.setApplicationName(APP_NAME)

    import lolitos.catalog  # noqa: F401  (registra o catálogo)
    from lolitos.core import settings
    from lolitos.ui import theme
    from lolitos.ui.main_window import MainWindow

    theme.use(settings.get("theme"))
    app.setStyleSheet(theme.qss())
    w = MainWindow()
    if "--tray" not in sys.argv:
        w.show()
    logging.getLogger("lolitos").info("iniciado | admin=%s", is_admin())
    rc = app.exec()
    lock.unlock()
    return rc


if __name__ == "__main__":
    sys.exit(main())
