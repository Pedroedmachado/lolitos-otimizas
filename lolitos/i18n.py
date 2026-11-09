"""Idiomas: português (original), inglês e espanhol.

Os textos da interface são escritos em português no código. As traduções ficam em lolitos/data/i18n/<idioma>.json
como {"texto em português": "tradução"}; textos montados com f-string viram modelos com {} no lugar dos valores
(tools/extract_strings.py gera a lista). Em vez de espalhar tr() por todo o código, os métodos do Qt que mostram
texto passam pela tradução quando o idioma não é português."""
from __future__ import annotations

import json
import re
from functools import lru_cache

LANGS = {"pt": "Português (Brasil)", "en": "English", "es": "Español"}
_lang = "pt"
_exact: dict[str, str] = {}
_tpl: list[tuple[str, re.Pattern, str]] = []
_PH = re.compile(r"(?<!\{)\{\}(?!\})")


def current() -> str:
    return _lang


def load(lang: str | None = None) -> None:
    """Carrega o idioma escolhido nas Configurações e liga a tradução nos widgets."""
    if lang is None:
        from lolitos.core import settings
        lang = settings.get("lang") or _installer_lang() or _system_lang()
    lang = lang if lang in LANGS else "pt"
    data = {}
    if lang != "pt":
        from lolitos.core.system import resource_path
        try:
            data = json.loads(resource_path("i18n", f"{lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    set_table(lang, data)
    if lang != "pt":
        install()


def set_table(lang: str, data: dict) -> None:
    """Define o idioma e a tabela de traduções (usado também nos testes)."""
    global _lang
    _lang = lang
    _exact.clear()
    _tpl.clear()
    _cached.cache_clear()
    for pt, tr_ in data.items():
        if not tr_ or not isinstance(tr_, str):
            continue
        if _PH.search(pt):
            parts = _PH.split(pt)
            lit = [p.replace("{{", "{").replace("}}", "}") for p in parts]
            if sum(len(re.sub(r"[^A-Za-zÀ-ú]", "", p)) for p in lit) < 3:
                continue     # modelo genérico demais ("<b>{}</b>")
            rx = re.compile("(.+?)".join(re.escape(p) for p in lit), re.S)
            _tpl.append((max(lit, key=len), rx, tr_))
        else:
            _exact[pt] = tr_
    _tpl.sort(key=lambda t: -len(t[0]))


def _installer_lang() -> str | None:
    """Idioma escolhido no instalador (lang.txt ao lado do .exe)."""
    import sys
    from pathlib import Path
    if not getattr(sys, "frozen", False):
        return None
    try:
        code = (Path(sys.executable).parent / "lang.txt").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None
    return code if code in LANGS else None


def _system_lang() -> str:
    try:
        import locale
        code = (locale.getlocale()[0] or "").lower()
    except (ValueError, TypeError):
        code = ""
    if code.startswith(("es", "spanish")):
        return "es"
    if code.startswith(("pt", "portuguese")):
        return "pt"
    return "en" if code else "pt"


def tr(s):
    """Traduz um texto (ou devolve igual)."""
    if _lang == "pt" or not isinstance(s, str) or not s.strip():
        return s
    return _cached(s)


@lru_cache(maxsize=4096)
def _cached(s: str) -> str:
    core = s.strip()
    pre, post = s[:len(s) - len(s.lstrip())], s[len(s.rstrip()):]
    hit = _exact.get(core)
    if hit is not None:
        return pre + hit + post
    for frag, rx, out in _tpl:
        if frag and frag not in core:
            continue
        m = rx.fullmatch(core)
        if m:
            vals = [_exact.get(g.strip(), g) for g in m.groups()]
            try:
                return pre + _fill(out, vals) + post
            except (IndexError, KeyError, ValueError):
                break
    # linhas separadas por <br> ou quebra de linha: traduz cada uma
    for sep in ("<br>", "\n"):
        if sep in core:
            pieces = core.split(sep)
            if len(pieces) > 1:
                return pre + sep.join(_cached(p) if p.strip() else p for p in pieces) + post
    return s


def _fill(template: str, vals: list[str]) -> str:
    it = iter(vals)
    return _PH.sub(lambda _m: next(it), template).replace("{{", "{").replace("}}", "}")


def restart_text(lang: str) -> str:
    return {"en": "The app will restart to switch the language.",
            "es": "La aplicación se reiniciará para cambiar el idioma."}.get(
        lang, "O app vai reiniciar para trocar o idioma.")


# ---------------------------------------------------------------------- ganchos no Qt
_installed = False


def install() -> None:
    """Faz os métodos do Qt que exibem texto passarem por tr()."""
    global _installed
    if _installed:
        return
    _installed = True
    from PySide6.QtWidgets import (QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QListWidgetItem,
                                   QMenu, QSystemTrayIcon, QTableWidget, QTabWidget, QWidget)

    def wrap(cls, name, pos=0):
        orig = getattr(cls, name)

        def f(self, *a, **k):
            if len(a) > pos and isinstance(a[pos], str):
                a = (*a[:pos], tr(a[pos]), *a[pos + 1:])
            return orig(self, *a, **k)
        setattr(cls, name, f)

    wrap(QLabel, "setText")
    wrap(QAbstractButton, "setText")
    wrap(QWidget, "setToolTip")
    wrap(QWidget, "setWindowTitle")
    wrap(QLineEdit, "setPlaceholderText")
    wrap(QGroupBox, "setTitle")
    wrap(QListWidgetItem, "setText")
    wrap(QListWidgetItem, "setToolTip")
    wrap(QTabWidget, "addTab", 1)
    wrap(QTabWidget, "setTabText", 1)
    wrap(QMenu, "addAction")
    wrap(QSystemTrayIcon, "showMessage")
    wrap(QSystemTrayIcon, "showMessage", 1)
    wrap(QSystemTrayIcon, "setToolTip")

    orig_add = QComboBox.addItem

    def add_item(self, *a, **k):
        a = list(a)
        i = 0 if a and isinstance(a[0], str) else 1
        if len(a) > i and isinstance(a[i], str):
            a[i] = tr(a[i])
        return orig_add(self, *a, **k)
    QComboBox.addItem = add_item
    orig_items = QComboBox.addItems
    QComboBox.addItems = lambda self, items: orig_items(self, [tr(x) for x in items])
    orig_hdr = QTableWidget.setHorizontalHeaderLabels
    QTableWidget.setHorizontalHeaderLabels = lambda self, labels: orig_hdr(self, [tr(x) for x in labels])


def translate_tree(root) -> None:
    """Traduz textos passados no construtor (QPushButton("..."), QCheckBox("...")) depois da tela montada."""
    if _lang == "pt" or root is None:
        return
    from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QTabWidget, QWidget
    widgets = [root] + root.findChildren(QWidget)
    for w in widgets:
        if isinstance(w, QLabel):
            t = w.text()
            n = tr(t)
            if n != t:
                w.setText(n)
        elif isinstance(w, QAbstractButton):
            t = w.text()
            n = tr(t)
            if n != t:
                w.setText(n)
        elif isinstance(w, QGroupBox):
            w.setTitle(tr(w.title()))
        elif isinstance(w, QTabWidget):
            for i in range(w.count()):
                w.setTabText(i, tr(w.tabText(i)))
        tip = w.toolTip()
        if tip:
            w.setToolTip(tr(tip))
