"""Ponto de entrada: python -m lolitos  [--tray] [--no-admin]"""
from __future__ import annotations

import logging
import sys


def main() -> int:
    from lolitos.core.system import IS_WIN, data_dir, is_admin, migrate_old_data, relaunch_as_admin

    migrate_old_data()

    sys.setswitchinterval(0.001)   # a thread da interface recupera o GIL mais rápido
    logging.basicConfig(filename=str(data_dir() / "lolitos.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if IS_WIN and not is_admin() and "--no-admin" not in sys.argv:
        if relaunch_as_admin():
            return 0     # a cópia elevada assume

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication

    lock = QLockFile(str(data_dir() / "app.lock"))
    # reinício pedido pelo próprio app (troca de idioma): espera a janela antiga fechar
    if not lock.tryLock(15000 if "--restarted" in sys.argv else 100):
        return 0         # já existe uma janela aberta

    if IS_WIN:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Chinese.Control")

    from lolitos import i18n
    i18n.load()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    from lolitos import APP_NAME
    app.setApplicationName(APP_NAME)

    import lolitos.catalog  # noqa: F401  (registra o catálogo)
    from lolitos.core import settings
    from lolitos.ui import theme
    from lolitos.ui.main_window import MainWindow

    if IS_WIN and is_admin():
        import threading

        def migrate():   # nomes antigos do app: tarefa de inicialização e plano de energia
            from lolitos.core.actions import rename_legacy_power_plans
            from lolitos.modules.startup import migrate_old_autostart
            for fn in (migrate_old_autostart, rename_legacy_power_plans):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    logging.getLogger("lolitos").exception("migração %s", fn.__name__)
        threading.Thread(target=migrate, daemon=True).start()
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
