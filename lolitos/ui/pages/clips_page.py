"""Ferramentas › Clipes: guardar os últimos segundos do jogo (Alt+Home) ou gravar (Alt+End), com o som só do jogo."""
from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from lolitos.core import settings
from lolitos.i18n import tr
from lolitos.modules import clips, procaudio
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, Toggle, button, card_header, hrow, info, label, pill

SECONDS = [(15, "15 segundos"), (30, "30 segundos"), (60, "1 minuto"), (120, "2 minutos")]
QUAL = [("alta", "Alta (20 Mb/s)"), ("media", "Média (12 Mb/s)"), ("leve", "Leve (6 Mb/s)")]
FPS = [(60, "60 FPS"), (30, "30 FPS")]
AUDIO = [("game", "Só o jogo"), ("pc", "Todo o som do PC"), ("none", "Sem áudio")]


def _combo(items, key, default):
    cb = QComboBox()
    for v, txt in items:
        cb.addItem(txt, v)
    cur = settings.get(key) or default
    idx = [v for v, _ in items].index(cur) if cur in [v for v, _ in items] else 0
    cb.setCurrentIndex(idx)
    cb.currentIndexChanged.connect(lambda _: settings.set(key, cb.currentData()))
    return cb


class ClipsPage(Page):
    title = "Clipes"
    subtitle = ("Salve os últimos segundos do jogo com Alt+Home ou grave com Alt+End, com o som só do jogo. "
                "A placa de vídeo faz o trabalho e o vídeo sai pronto na hora.")

    def build(self):
        self.state = pill("…")
        self.actions.addWidget(self.state, 0, Qt.AlignVCenter)

        # ------------------------------------------------ ativar
        hero = Card(hero=True)
        top = QHBoxLayout()
        top.addLayout(card_header("clips", "Clipes de jogo"), 1)
        top.addWidget(label("Ativar", "muted", wrap=False), 0, Qt.AlignVCenter)
        self.sw = Toggle(bool(settings.get("clips_enabled")))
        self.sw.clicked.connect(self._toggle)
        top.addWidget(self.sw, 0, Qt.AlignVCenter)
        hero.lay.addLayout(top)
        keys = QGridLayout()
        keys.setHorizontalSpacing(18)
        for i, (k, txt) in enumerate((("Alt + Home", "Salvar os últimos segundos"),
                                      ("Alt + End", "Começar / parar uma gravação"))):
            kb = label(k, "pill", wrap=False)
            keys.addWidget(kb, i, 0)
            keys.addWidget(label(txt, wrap=False), i, 1)
        keys.setColumnStretch(2, 1)
        hero.lay.addLayout(keys)
        hero.lay.addWidget(label("O gravador (ffmpeg, de código aberto) é baixado só quando você ativa os Clipes. "
                                 "Ele só roda enquanto um jogo está em primeiro plano; fora do jogo não grava nada. "
                                 "Nada é injetado no jogo.", "muted"))
        self.enc_lbl = label("", "muted", wrap=False)
        hero.lay.addWidget(self.enc_lbl)
        self.body.addWidget(hero)

        # ------------------------------------------------ opções
        op = Card()
        op.lay.addWidget(label("Opções", "h2"))
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(8)
        rows = [("Tamanho do buffer (Alt+Home salva)", _combo(SECONDS, "clips_seconds", 30)),
                ("Qualidade", _combo(QUAL, "clips_quality", "media")),
                ("Quadros por segundo", _combo(FPS, "clips_fps", 60)),
                ("Áudio", _combo(AUDIO, "clips_audio", "game")),
                ("Monitor gravado", _combo([(0, "Principal"), (1, "Segundo monitor"), (2, "Terceiro monitor")],
                                           "clips_monitor", 0))]
        for i, (t, w) in enumerate(rows):
            g.addWidget(label(t, wrap=False), i, 0)
            g.addWidget(w, i, 1)
        g.setColumnStretch(2, 1)
        op.lay.addLayout(g)
        if not procaudio.process_loopback_supported():
            op.lay.addWidget(label("Este Windows não tem a captura de som por programa (precisa do Windows 11 ou "
                                   "Windows 10 build 20348+): 'Só o jogo' grava o som do PC inteiro.", "tcwarn"))
        op.lay.addWidget(label("As opções valem a partir do próximo jogo aberto.", "muted"))
        self.folder_lbl = label("", "muted", wrap=False)
        op.lay.addWidget(self.folder_lbl)
        op.lay.addLayout(hrow(button("Abrir pasta dos clipes", on_click=self._open_folder),
                              button("Trocar pasta…", on_click=self._pick_folder),
                              button("Testar a placa de vídeo de novo", on_click=self._retest), None))
        self.body.addWidget(op)

        # ------------------------------------------------ últimos clipes
        rc = Card()
        hdr = QHBoxLayout()
        hdr.addWidget(label("Últimos clipes", "h2"))
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
    def _refresh(self):
        svc = getattr(self.main, "clips", None) if self.main else None
        if not settings.get("clips_enabled"):
            txt, col = "Desativado", C["muted"]
        elif svc and svc.is_alive():
            st = svc.status()
            txt = {"gravando": "● Gravando"}.get(st, "Buffer ativo" if st.startswith("buffer") else "Esperando um jogo")
            col = C["bad"] if st == "gravando" else (C["ok"] if st.startswith("buffer") else C["accent2"])
        else:
            txt, col = "Ativado", C["accent2"]
        self.state.setText(tr(txt))
        self.state.setStyleSheet(f"color:{col}; border-color:{col};")
        enc = settings.get("clips_encoder")
        self.enc_lbl.setText(tr("Codificador: {}").replace("{}", clips.encoder_label(enc)) if enc else "")
        try:
            self.folder_lbl.setText(tr("Pasta: {}").replace("{}", str(clips.clips_dir())))
        except OSError:
            self.folder_lbl.setText("")
        self._list()

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
            self.list_l.addWidget(label("Nenhum clipe ainda. Abra um jogo e aperte Alt+Home.", "muted"))
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
    def _toggle(self):
        if not self.sw.isChecked():
            settings.set("clips_enabled", False)
            if self.main:
                self.main.stop_clips()
            self._refresh()
            return
        self.sw.setChecked(False)

        def work(progress=None):
            exe = clips.install_ffmpeg(progress)
            if not settings.get("clips_encoder"):
                settings.set("clips_encoder", clips.pick_encoder(exe, progress))
            return "Clipes ativados. Abra um jogo: Alt+Home salva os últimos segundos, Alt+End grava."

        def done(_):
            if clips.find_ffmpeg() and settings.get("clips_encoder"):
                settings.set("clips_enabled", True)
                self.sw.setChecked(True)
                if self.main:
                    self.main.start_clips()
            self._refresh()
        TaskDialog(self, "Ativar Clipes", work, on_done=done).exec()

    def _retest(self):
        exe = clips.find_ffmpeg()
        if not exe:
            info(self, "Clipes", "Ative os Clipes primeiro (o gravador ainda não foi baixado).")
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
