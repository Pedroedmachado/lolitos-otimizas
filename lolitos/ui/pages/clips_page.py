"""Ferramentas › Clipes: guardar os últimos segundos do jogo ou gravar, com o som só do jogo.

Partes da tela: componente de gravação (baixado só quando você pede), estado da captura com os botões e os
atalhos (que você escolhe), configurações em botões, ligar sozinho quando um jogo abrir, pasta e clipes recentes."""
from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QGridLayout, QHBoxLayout, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from lolitos.core import settings
from lolitos.i18n import tr
from lolitos.modules import clips, procaudio
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, Toggle, button, info, label

SECONDS = [(15, "15 s"), (30, "30 s"), (60, "1 min"), (120, "2 min"), (180, "3 min"), (300, "5 min")]
FPS = [(30, "30"), (60, "60")]
TARGET = [("window", "Janela do jogo"), ("screen", "Tela inteira")]
AUDIO = [("game", "Só o jogo"), ("pc", "Todo o PC"), ("none", "Sem som")]
QT_KEYS = {"PgUp": "PageUp", "PgDown": "PageDown", "Ins": "Insert", "ScrLk": "ScrollLock"}


class KeyEdit(QLineEdit):
    """Campo de atalho: clique e aperte a combinação (ex.: Alt+Home). Esc cancela."""

    def __init__(self, text: str, on_change):
        super().__init__(text)
        self.on_change = on_change
        self.setReadOnly(True)
        self.setFixedWidth(150)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("Clique e aperte a combinação de teclas"))
        self._old = text

    def focusInEvent(self, e):
        self._old = self.text()
        self.setText(tr("aperte as teclas…"))
        super().focusInEvent(e)

    def focusOutEvent(self, e):
        if self.text() == tr("aperte as teclas…"):
            self.setText(self._old)
        super().focusOutEvent(e)

    def keyPressEvent(self, e):
        from PySide6.QtGui import QKeySequence
        k = e.key()
        if k == Qt.Key_Escape:
            self.setText(self._old)
            self.clearFocus()
            return
        if k in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return
        parts = []
        m = e.modifiers()
        if m & Qt.ControlModifier:
            parts.append("Ctrl")
        if m & Qt.AltModifier:
            parts.append("Alt")
        if m & Qt.ShiftModifier:
            parts.append("Shift")
        name = QKeySequence(k).toString()
        parts.append(QT_KEYS.get(name, name))
        text = "+".join(parts)
        self.setText(text)
        self._old = text
        self.clearFocus()
        self.on_change(text)


def seg_row(items, key, default, on_change=None) -> QWidget:
    """Botões lado a lado (um escolhido), gravando a escolha nas configurações."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    grp = QButtonGroup(w)
    grp.setExclusive(True)
    cur = settings.get(key)
    if cur is None:
        cur = default
    for v, txt in items:
        b = QPushButton(tr(txt))
        b.setObjectName("chip")
        b.setCheckable(True)
        b.setChecked(v == cur)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, val=v: (settings.set(key, val), on_change and on_change()))
        grp.addButton(b)
        h.addWidget(b)
    h.addStretch()
    w._grp = grp
    return w


class ClipsPage(Page):
    title = "Clipes"
    subtitle = ("Salve os últimos segundos do jogo ou grave com um atalho, com o som só do jogo. O vídeo sai pronto "
                "na hora, sem reprocessar, e a placa de vídeo faz o trabalho pesado.")

    def build(self):
        # ------------------------------------------------ componente de gravação
        comp = Card(hero=True)
        comp.lay.addWidget(label("<b>Componente de gravação</b>", "h3", rich=True))
        self.comp_txt = label("", "muted")
        comp.lay.addWidget(self.comp_txt)
        self.comp_btn = button("Baixar e ativar Clipes", "primary", self._install)
        self.comp_btn.setMinimumHeight(40)
        comp.lay.addWidget(self.comp_btn)
        self.comp_row = QHBoxLayout()
        self.enc_lbl = label("", "muted", wrap=False)
        self.comp_row.addWidget(self.enc_lbl)
        self.comp_row.addStretch()
        self.retest_btn = button("Testar a placa de vídeo de novo", on_click=self._retest)
        self.comp_row.addWidget(self.retest_btn)
        comp.lay.addLayout(self.comp_row)
        self.body.addWidget(comp)

        # ------------------------------------------------ captura
        cap = Card()
        head = QHBoxLayout()
        self.dot = label("●", wrap=False)
        head.addWidget(self.dot)
        self.cap_title = label("", "h3", wrap=False)
        head.addWidget(self.cap_title)
        head.addStretch()
        cap.lay.addLayout(head)
        self.cap_sub = label("", "muted")
        cap.lay.addWidget(self.cap_sub)
        btns = QHBoxLayout()
        self.cap_btn = button("Ligar captura", on_click=self._toggle_capture)
        self.cap_btn.setObjectName("outline")
        self.save_btn = button("", on_click=lambda: self._job("save"))
        self.rec_btn = button("", on_click=lambda: self._job("record"))
        for b in (self.cap_btn, self.save_btn, self.rec_btn):
            b.setMinimumHeight(40)
            btns.addWidget(b, 1)
        cap.lay.addLayout(btns)
        keys = QHBoxLayout()
        keys.addWidget(label("Salvar clipe", wrap=False))
        self.key_save = KeyEdit(settings.get("clips_key_save") or "Alt+Home",
                                lambda t: self._set_key("clips_key_save", t))
        keys.addWidget(self.key_save)
        keys.addSpacing(16)
        keys.addWidget(label("Gravar e parar", wrap=False))
        self.key_rec = KeyEdit(settings.get("clips_key_record") or "Alt+End",
                               lambda t: self._set_key("clips_key_record", t))
        keys.addWidget(self.key_rec)
        keys.addStretch()
        cap.lay.addLayout(keys)
        self.key_warn = label("", "tcwarn")
        cap.lay.addWidget(self.key_warn)
        self.body.addWidget(cap)

        # ------------------------------------------------ configurações
        op = Card()
        op.lay.addWidget(label("Configurações", "h2"))
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(8)
        upd = self._estimate
        rows = [("Quanto guardar", seg_row(SECONDS, "clips_seconds", 30, upd)),
                ("Qualidade", seg_row(clips.QUALITY_NAMES, "clips_quality", "media", upd)),
                ("Quadros por segundo", seg_row(FPS, "clips_fps", 60, upd)),
                ("Tamanho do vídeo", seg_row(clips.RES_CHOICES, "clips_res", 1080, upd)),
                ("O que capturar", seg_row(TARGET, "clips_target", "window", upd)),
                ("Som", seg_row(AUDIO, "clips_audio", "game", upd))]
        for i, (t, w) in enumerate(rows):
            g.addWidget(label(t, wrap=False), i, 0, Qt.AlignVCenter)
            g.addWidget(w, i, 1)
        g.setColumnStretch(1, 1)
        op.lay.addLayout(g)
        self.est = label("", "muted")
        op.lay.addWidget(self.est)
        if not procaudio.process_loopback_supported():
            op.lay.addWidget(label("Este Windows não tem a captura de som por programa (precisa do Windows 11 ou "
                                   "Windows 10 build 20348+): 'Só o jogo' grava o som do PC inteiro.", "tcwarn"))
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C['border']};")
        op.lay.addWidget(sep)
        auto = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("Ligar sozinho quando um jogo abrir", wrap=False))
        col.addWidget(label("A captura liga quando um jogo aparece na tela e desliga quando ele fecha. Com ela "
                            "desligada, nada fica rodando.", "muted"))
        auto.addLayout(col, 1)
        self.auto_sw = Toggle(bool(settings.get("clips_auto", True)))
        self.auto_sw.clicked.connect(self._auto)
        auto.addWidget(self.auto_sw, 0, Qt.AlignVCenter)
        op.lay.addLayout(auto)
        folder = QHBoxLayout()
        self.folder_lbl = label("", "muted")
        folder.addWidget(self.folder_lbl, 1)
        folder.addWidget(button("Trocar pasta…", on_click=self._pick_folder))
        folder.addWidget(button("Abrir pasta", on_click=self._open_folder))
        op.lay.addLayout(folder)
        self.body.addWidget(op)

        # ------------------------------------------------ recentes
        rc = Card()
        hdr = QHBoxLayout()
        hdr.addWidget(label("Clipes recentes", "h2"))
        hdr.addStretch()
        hdr.addWidget(button("Atualizar", on_click=self._list))
        rc.lay.addLayout(hdr)
        self.list_w = QWidget()
        self.list_l = QVBoxLayout(self.list_w)
        self.list_l.setContentsMargins(0, 0, 0, 0)
        rc.lay.addWidget(self.list_w)
        self.body.addWidget(rc)
        self.body.addStretch()
        self._refresh()

    def on_show(self):
        if self._built:
            self._refresh()

    # ---------------------------------------------------------------- estado
    def _svc(self):
        return getattr(self.main, "clips", None) if self.main else None

    def _refresh(self):
        ready = bool(settings.get("clips_enabled")) and clips.find_ffmpeg() is not None
        enc = settings.get("clips_encoder")
        if ready:
            self.comp_txt.setText(tr("Gravador instalado (FFmpeg, código aberto). A captura de tela é feita pela "
                                     "placa de vídeo; nada é injetado no jogo."))
            self.comp_btn.hide()
            self.enc_lbl.setText(tr("Codificador: {}").replace("{}", clips.encoder_label(enc)) if enc else "")
            self.enc_lbl.show()
            self.retest_btn.show()
        else:
            self.comp_txt.setText(tr("Para não aumentar o instalador, o gravador (FFmpeg, código aberto) é baixado só "
                                     "agora, uma vez: cerca de 90 MB, da build oficial do Gyan pelo winget, que confere "
                                     "o arquivo antes de instalar."))
            self.comp_btn.show()
            self.enc_lbl.hide()
            self.retest_btn.hide()
        svc = self._svc()
        st = svc.status() if svc and svc.is_alive() else "desligada"
        if st == "gravando":
            title, col, sub = "Gravando", C["bad"], tr("Aperte {} de novo para parar e salvar.").replace(
                "{}", settings.get("clips_key_record") or "Alt+End")
        elif st.startswith("ligada"):
            title, col = "Captura ligada", C["ok"]
            sub = tr("Capturando {}. {} salva os últimos {} s.").replace("{}", st.split("·", 1)[-1].strip(), 1) \
                .replace("{}", settings.get("clips_key_save") or "Alt+Home", 1) \
                .replace("{}", str(settings.get("clips_seconds") or 30), 1)
        else:
            title, col = "Captura desligada", C["muted"]
            sub = (tr("Baixe o componente de gravação acima para começar.") if not ready else
                   tr("Ligue agora ou deixe ligar sozinha quando um jogo abrir.") if settings.get("clips_auto", True)
                   else tr("Ligue a captura para poder salvar clipes."))
        self.dot.setStyleSheet(f"color:{col}; font-size:14pt;")
        self.cap_title.setText(tr(title))
        self.cap_sub.setText(sub)
        on_now = st != "desligada"
        self.cap_btn.setText(tr("Desligar captura") if on_now else tr("Ligar captura"))
        on = ready and svc is not None
        for b in (self.cap_btn, self.save_btn, self.rec_btn):
            b.setEnabled(on)
        self.save_btn.setText(f"{tr('Salvar clipe')} · {settings.get('clips_key_save') or 'Alt+Home'}")
        self.rec_btn.setText((tr("Parar gravação") if st == "gravando" else tr("Gravar")) +
                             f" · {settings.get('clips_key_record') or 'Alt+End'}")
        errs = getattr(self.main, "clip_key_errors", []) if self.main else []
        self.key_warn.setText(tr("Atalho em uso por outro programa: {}. Escolha outro.").replace("{}", ", ".join(errs))
                              if errs else "")
        self.key_warn.setVisible(bool(errs))
        try:
            self.folder_lbl.setText(tr("Pasta dos clipes: {}").replace("{}", str(clips.clips_dir())))
        except OSError:
            self.folder_lbl.setText("")
        self._estimate()
        self._list()

    def _estimate(self):
        secs = int(settings.get("clips_seconds") or 30)
        res = settings.get("clips_res")
        res = 1080 if res is None else int(res)
        h = res or max((m.height for m in clips.monitors()), default=1080)
        mb = clips.buffer_mb(secs, settings.get("clips_quality") or "media", h)
        dur = f"{secs} s" if secs < 60 else f"{secs // 60} min"
        self.est.setText(tr("O clipe salva os últimos {}. O buffer ocupa uns {} MB no disco, só enquanto a captura "
                            "está ligada ({}p como referência).").replace("{}", dur, 1).replace("{}", str(mb), 1)
                         .replace("{}", str(h), 1))

    def _list(self):
        while self.list_l.count():
            w = self.list_l.takeAt(0).widget()
            if w:
                w.deleteLater()
        try:
            files = sorted(clips.clips_dir().glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]
        except OSError:
            files = []
        if not files:
            self.list_l.addWidget(label("Nenhum clipe ainda.", "muted"))
            return
        for f in files:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 2, 0, 2)
            mb = f.stat().st_size / 1024 ** 2
            when = time.strftime("%d/%m %H:%M", time.localtime(f.stat().st_mtime))
            h.addWidget(label(f"<b>{f.stem}</b>  <span style='color:{C['muted']}'>· {when} · {mb:.0f} MB</span>",
                              rich=True), 1)
            h.addWidget(button("Abrir", on_click=lambda _=False, p=f: os.startfile(str(p))))
            self.list_l.addWidget(row)

    # ---------------------------------------------------------------- ações
    def _install(self):
        def work(progress=None):
            exe = clips.install_ffmpeg(progress)
            if not settings.get("clips_encoder"):
                settings.set("clips_encoder", clips.pick_encoder(exe, progress))
            return tr("Clipes ativados. Ligue a captura ou abra um jogo: {} salva os últimos segundos, {} grava.") \
                .replace("{}", settings.get("clips_key_save") or "Alt+Home", 1) \
                .replace("{}", settings.get("clips_key_record") or "Alt+End", 1)

        def done(_):
            if clips.find_ffmpeg() and settings.get("clips_encoder"):
                settings.set("clips_enabled", True)
                if self.main:
                    self.main.start_clips()
            self._refresh()
        TaskDialog(self, "Baixar e ativar Clipes", work, on_done=done).exec()

    def _toggle_capture(self):
        svc = self._svc()
        if not svc:
            return
        svc.set_capture(svc.status() == "desligada")
        self._refresh()

    def _job(self, job):
        svc = self._svc()
        if svc:
            svc.request(job)

    def _auto(self):
        settings.set("clips_auto", self.auto_sw.isChecked())
        svc = self._svc()
        if svc:
            svc.request("tick")
        self._refresh()

    def _set_key(self, key, text):
        from lolitos.ui.overlay import parse_hotkey
        if not parse_hotkey(text):
            info(self, "Clipes", tr("Esse atalho não serve: use Ctrl, Alt ou Shift + uma tecla (letra, número, F1–F24, "
                                    "Home, End, Insert, Page Up/Down)."))
            self._refresh()
            return
        settings.set(key, text)
        if self.main and getattr(self.main, "clips", None):
            self.main.register_clip_keys()
        self._refresh()

    def _retest(self):
        exe = clips.find_ffmpeg()
        if not exe:
            info(self, "Clipes", "Baixe o componente de gravação primeiro.")
            return

        def work(progress=None):
            settings.set("clips_encoder", clips.pick_encoder(exe, progress))
            return tr("Codificador: {}").replace("{}", clips.encoder_label(settings.get("clips_encoder")))
        TaskDialog(self, "Clipes", work, on_done=lambda _: self._refresh()).exec()

    def _open_folder(self):
        os.startfile(str(clips.clips_dir()))

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, tr("Pasta dos clipes"), str(clips.clips_dir()))
        if d:
            settings.set("clips_dir", str(Path(d)))
            self._refresh()
