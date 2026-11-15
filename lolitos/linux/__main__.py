"""Entrada da versão Linux:  python -m lolitos.linux"""
import logging
import sys


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("Esta é a versão para Linux. No Windows, use:  python -m lolitos")
        return 1
    from lolitos.__main__ import _setup_logging
    from lolitos.core.system import data_dir
    _setup_logging(data_dir() / "lolitos-linux.log")

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication
    lock = QLockFile(str(data_dir() / "linux.lock"))
    if not lock.tryLock(100):
        return 0
    from lolitos import APP_NAME, i18n
    i18n.load()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("chinese-control")

    from lolitos.core import settings
    from lolitos.linux import catalog
    from lolitos.ui import fx, theme
    catalog.load()
    theme.use(settings.get("theme"), fx.current_from_settings())
    app.setStyleSheet(theme.qss())
    fx.install(app)
    from lolitos.linux.window import LinuxWindow
    w = LinuxWindow()
    w.show()
    logging.getLogger("lolitos").info("iniciado (linux)")
    rc = app.exec()
    lock.unlock()
    return rc


if __name__ == "__main__":
    sys.exit(main())
