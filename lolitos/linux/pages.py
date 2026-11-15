"""Telas da versão Linux."""
from __future__ import annotations

import time

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
                               QLineEdit, QPushButton, QSpinBox, QVBoxLayout)

from lolitos import APP_NAME, VERSION
from lolitos.core import engine, history, settings
from lolitos.core.system import data_dir, human_size
from lolitos.core.tweaks import ADVANCED
from lolitos.linux import catalog, mangohud, steam, sysinfo
from lolitos.ui.pages.hardware_page import COLORS, _Chart, rate
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import TweakList, bulk_apply
from lolitos.ui.widgets import (Card, Page, StatTile, TaskDialog, Toggle, button, card_header, confirm, hrow, info,
                                label, pill, run_async)


def _kv(card: Card, rows) -> None:
    g = QGridLayout()
    g.setHorizontalSpacing(18)
    g.setVerticalSpacing(7)
    g.setColumnStretch(1, 1)
    for i, (k, v) in enumerate(rows):
        g.addWidget(label(k, "muted", wrap=False), i, 0, Qt.AlignTop)
        g.addWidget(label(f"<b>{v}</b>", rich=True), i, 1)
    card.lay.addLayout(g)


# ---------------------------------------------------------------------------------------------- Painel
class Dashboard(Page):
    title = "Painel"
    subtitle = "Resumo do PC e dos ajustes de Linux aplicados."

    def build(self):
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        self.t_on = StatTile("Ajustes ativos", "—", "", "check")
        self.t_pend = StatTile("Recomendados pendentes", "—", "", "bolt")
        self.t_gov = StatTile("Processador", "—", "governador", "cpu")
        self.t_gm = StatTile("GameMode", "—", "", "games")
        for t in (self.t_on, self.t_pend, self.t_gov, self.t_gm):
            tiles.addWidget(t, 1)
        self.body.addLayout(tiles)

        act = Card(hero=True)
        act.lay.addLayout(card_header("bolt", "Aplicar recomendados"))
        self.act_lbl = label("Lendo o estado dos ajustes…", "muted")
        act.lay.addWidget(self.act_lbl)
        self.apply_btn = button("Aplicar recomendados", "primary", self._apply)
        act.lay.addLayout(hrow(self.apply_btn, button("Ver todos os ajustes", on_click=lambda: self.main.go("ajustes")),
                               None))
        act.lay.addWidget(label("Aplica os ajustes essenciais e recomendados que valem neste PC. Os avançados e a "
                                "instalação de pacotes ficam na tela Ajustes. A senha de administrador é pedida "
                                "uma vez por sessão.", "small"))
        self.body.addWidget(act)

        self.info = Card()
        self.info.lay.addLayout(card_header("pc", "Informações do Sistema"))
        self.info_box = QVBoxLayout()
        self.info.lay.addLayout(self.info_box)
        self.info_box.addWidget(label("Lendo o sistema…", "muted"))
        self.body.addWidget(self.info)
        run_async(sysinfo.summary, on_done=self._info)

    def _info(self, rows):
        while self.info_box.count():
            w = self.info_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        c = Card()
        c.setObjectName("")
        c.lay.setContentsMargins(0, 0, 0, 0)
        _kv(c, rows)
        self.info_box.addWidget(c)

    def on_show(self):
        if self._built:
            run_async(self._state, on_done=self._show)

    @staticmethod
    def _state():
        import shutil
        tw = catalog.linux_tweaks()
        st = {t.id: t.status() for t in tw}
        rec = [t for t in catalog.recommended() if st[t.id] in ("off", "partial")]
        return {"on": sum(1 for s in st.values() if s == "on"), "valid": sum(1 for s in st.values() if s != "na"),
                "pending": rec, "gov": sysinfo.governor(), "gm": bool(shutil.which("gamemoderun"))}

    def _show(self, s):
        self.pending = s["pending"]
        self.t_on.set(str(s["on"]), f"de {s['valid']} neste PC")
        self.t_pend.set(str(len(self.pending)))
        self.t_gov.set(s["gov"])
        self.t_gm.set("Instalado" if s["gm"] else "Não instalado")
        self.apply_btn.setEnabled(bool(self.pending))
        self.act_lbl.setText("Tudo o que é recomendado para este PC já está aplicado." if not self.pending else
                             f"{len(self.pending)} ajuste(s) recomendado(s) ainda não aplicados: "
                             + ", ".join(t.title for t in self.pending[:6]) + ("…" if len(self.pending) > 6 else ""))

    def _apply(self):
        if not self.pending:
            return
        TaskDialog(self, f"Aplicando {len(self.pending)} ajuste(s)", bulk_apply, list(self.pending),
                   restore_point=False, on_done=lambda _: self.on_show()).exec()


# ---------------------------------------------------------------------------------------------- Desempenho
class PerformancePage(Page):
    title = "Desempenho"
    subtitle = "Monitor em tempo real: processador, memória, placa de vídeo, disco e rede."

    def build(self):
        self.cpu = _Chart("Processador", COLORS["cpu"], height=170)
        self.ram = _Chart("Memória", COLORS["ram"])
        self.gpu = _Chart("Placa de vídeo", COLORS["gpu"])
        self.disk = _Chart("Disco", COLORS["disk"])
        self.net = _Chart("Rede", COLORS["net"], fixed=False, fmt=lambda v: rate(v).replace(",0 ", " "))
        g = QGridLayout()
        g.setSpacing(14)
        g.addWidget(self.cpu, 0, 0, 1, 2)
        g.addWidget(self.ram, 1, 0)
        g.addWidget(self.gpu, 1, 1)
        g.addWidget(self.disk, 2, 0)
        g.addWidget(self.net, 2, 1)
        self.body.addLayout(g)
        self.model = sysinfo.cpu_model()
        self.g: dict = {}
        self.prev_net, self.prev_disk, self.prev_t = psutil.net_io_counters(), psutil.disk_io_counters(), time.time()
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(1000)

    def _tick(self):
        if not self.isVisible():
            return
        now = time.time()
        dt = max(0.1, now - self.prev_t)
        n, d = psutil.net_io_counters(), psutil.disk_io_counters()
        down = (n.bytes_recv - self.prev_net.bytes_recv) / dt
        up = (n.bytes_sent - self.prev_net.bytes_sent) / dt
        rd = wr = busy = 0.0
        if d and self.prev_disk:
            rd = (d.read_bytes - self.prev_disk.read_bytes) / dt
            wr = (d.write_bytes - self.prev_disk.write_bytes) / dt
            if hasattr(d, "busy_time"):
                busy = max(0.0, min(100.0, (d.busy_time - self.prev_disk.busy_time) / (dt * 10)))
        self.prev_net, self.prev_disk, self.prev_t = n, d, now
        run_async(sysinfo.gpu, on_done=lambda v: setattr(self, "g", v or {}))     # nvidia-smi fora da interface
        cpu, vm, f, temp = psutil.cpu_percent(), psutil.virtual_memory(), psutil.cpu_freq(), sysinfo.cpu_temp()
        foot = [f"<b>{self.model}</b>", f"{psutil.cpu_count(logical=False)} núcleos / {psutil.cpu_count()} threads",
                f"{f.current / 1000:.2f} GHz".replace(".", ",") if f and f.current else "",
                f"{temp:.0f} °C" if temp else "", sysinfo.governor()]
        self.cpu.set(f"{cpu:.0f}%", cpu, " · ".join(x for x in foot if x))
        self.ram.set(f"{vm.used / 1024 ** 3:.1f} / {vm.total / 1024 ** 3:.0f} GB ({vm.percent:.0f}%)", vm.percent,
                     f"{human_size(vm.available)} disponível")
        g = self.g
        if g.get("util") is not None:
            foot = [f"<b>{g.get('name', '')}</b>",
                    f"VRAM {g['vram_used'] / 1024:.1f} de {g['vram_total'] / 1024:.0f} GB"
                    if g.get("vram_total") and g.get("vram_used") is not None else "",
                    f"{g['temp']:.0f} °C" if g.get("temp") is not None else "",
                    f"{g['power']:.0f} W" if g.get("power") is not None else ""]
            self.gpu.set(f"{g['util']:.0f}%", g["util"], " · ".join(x for x in foot if x))
        else:
            self.gpu.set("—", 0, "Uso da placa de vídeo: precisa do nvidia-smi (driver NVIDIA).")
        self.disk.set(f"{busy:.0f}%", busy, f"Leitura {rate(rd)} · Escrita {rate(wr)}")
        self.net.set(f"↓ {rate(down)}", down, f"Recebendo {rate(down)} · Enviando {rate(up)} "
                     f"<span style='color:{C['muted']}'>(linha cinza)</span>", up)


# ---------------------------------------------------------------------------------------------- Meu PC
class MyPcPage(Page):
    title = "Meu PC"
    subtitle = "As peças do computador, lidas do Linux."

    def build(self):
        self.actions.addWidget(button("Atualizar", on_click=self._load))
        self.box = QVBoxLayout()
        self.box.setSpacing(14)
        self.body.addLayout(self.box)
        self._load()

    def _load(self):
        run_async(lambda: (sysinfo.summary(), sysinfo.disks(), sysinfo.gpu(0)), on_done=self._show)

    def _show(self, res):
        rows, disks, g = res
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        d = dict(rows)
        for icon, title, keys in (("pc", "Sistema", ["Sistema", "Sessão", "Ligado há"]),
                                  ("cpu", "Processador", ["Processador", "Núcleos"]),
                                  ("ram", "Memória", ["Memória RAM"]),
                                  ("gpu", "Placa de vídeo", ["Placa de vídeo"]),
                                  ("pc", "Placa-mãe", ["Placa-mãe", "BIOS"])):
            c = Card()
            c.lay.addLayout(card_header(icon, title))
            extra = []
            if title == "Placa de vídeo" and g.get("vram_total"):
                extra = [("Memória de vídeo", f"{g['vram_total'] / 1024:.0f} GB")]
            if title == "Memória":
                sw = psutil.swap_memory()
                extra = [("Swap", human_size(sw.total) + (" (zram)" if catalog.has_zram() else "") if sw.total
                          else "sem swap")]
            _kv(c, [(k, d.get(k, "—")) for k in keys] + extra)
            self.box.addWidget(c)
        c = Card()
        c.lay.addLayout(card_header("disk", "Discos"))
        _kv(c, [(x["dev"], f"{x['model']} · {x['kind']} · {human_size(x['size'])} · agendador {x['scheduler'] or '—'}")
                for x in disks] or [("—", "nenhum disco encontrado")])
        self.box.addWidget(c)


# ---------------------------------------------------------------------------------------------- Ajustes
class TweaksPage(Page):
    title = "Ajustes"
    subtitle = ("Cada ajuste mostra o que faz, o que se perde e o estado neste PC. Tudo o que tem desfazer volta "
                "ao valor anterior pela coluna Desfazer ou pela tela Restauração.")

    def build(self):
        self.count = label("", "counter", wrap=False)
        self.actions.addWidget(self.count)
        self.actions.addWidget(button("Marcar recomendados", on_click=self._mark))
        self.actions.addWidget(button("Aplicar selecionados", "primary", self._apply))
        self.lists: list[TweakList] = []
        tw = catalog.linux_tweaks()
        for cat, name in catalog.LINUX_CATS.items():
            items = [t for t in tw if t.cat == cat]
            if not items:
                continue
            c = Card()
            c.lay.addWidget(label(name, "h2"))
            lst = TweakList(items, self, search=False, bar=False, table=True, on_selection=self._count,
                            on_states=self._count)
            self.lists.append(lst)
            c.lay.addWidget(lst)
            self.body.addWidget(c)
        self.body.addWidget(label("Os ajustes de sistema gravam um arquivo em /etc (sysctl.d, tmpfiles.d ou "
                                  "modules-load.d) com 'chinese-control' no nome, para valerem depois de reiniciar. "
                                  "Desfazer apaga o arquivo e devolve o valor anterior.", "muted"))

    def on_show(self):
        if self._built:
            for lst in self.lists:
                lst.refresh()

    def _selected(self):
        return [t for lst in self.lists for t in lst.selected()]

    def _count(self):
        on = sum(1 for lst in self.lists for s in lst.states.values() if s == "on")
        valid = sum(1 for lst in self.lists for s in lst.states.values() if s != "na")
        sel = len(self._selected())
        self.count.setText(f"{on} de {valid} ativos" + (f" · {sel} marcado(s)" if sel else ""))

    def _mark(self):
        for lst in self.lists:
            for r in lst.rows.values():
                if r.chk.isEnabled():
                    r.chk.setChecked(r.t.recommended_here() and r.state in ("off", "partial"))

    def _apply(self):
        sel = self._selected()
        if not sel:
            info(self, "Nada selecionado", "Marque os ajustes (ou clique em 'Marcar recomendados').")
            return
        adv = [t for t in sel if t.level == ADVANCED or not t.reversible]
        if adv and not confirm(self, "Itens avançados", "Você marcou itens com contrapartida:<br>• "
                               + "<br>• ".join(t.title for t in adv) + "<br><br>Continuar?"):
            return
        TaskDialog(self, f"Aplicando {len(sel)} ajuste(s)", bulk_apply, sel, restore_point=False,
                   on_done=lambda _: self.on_show()).exec()


# ---------------------------------------------------------------------------------------------- Jogos
class GamesPage(Page):
    title = "Jogos"
    subtitle = "Jogos instalados pela Steam e as opções de inicialização para colar em cada um."

    def build(self):
        self.actions.addWidget(button("Atualizar", on_click=self._load))
        opt = Card(hero=True)
        opt.lay.addLayout(card_header("bolt", "Opções de inicialização"))
        opt.lay.addWidget(label("Marque o que quer usar e cole a linha em Steam › botão direito no jogo › "
                                "Propriedades › Opções de inicialização.", "muted"))
        saved = set(settings.get("lx_launch_parts", ["gamemode", "mangohud"]))
        self.parts: dict[str, QCheckBox] = {}
        row = QGridLayout()
        row.setVerticalSpacing(8)
        for n, (key, text, _v) in enumerate(steam.LAUNCH_PARTS):
            cb = QCheckBox(text)
            cb.setChecked(key in saved)
            cb.toggled.connect(self._line)
            self.parts[key] = cb
            row.addWidget(cb, n // 2, n % 2)
        opt.lay.addLayout(row)
        self.line = QLineEdit()
        self.line.setReadOnly(True)
        self.copy_btn = button("Copiar", "primary", self._copy)
        opt.lay.addLayout(hrow(self.line, self.copy_btn, stretch_first=True))
        self.warn = label("", "small")
        opt.lay.addWidget(self.warn)
        self.body.addWidget(opt)

        bdo = Card()
        bdo.lay.addLayout(card_header("bdo", "Black Desert no Linux"))
        bdo.lay.addWidget(label(
            "O Black Desert roda pelo Proton desde que trocou o anticheat para o XIGNCODE3. Dicas a partir de "
            "relatos de jogadores (não testadas por este app):<br>"
            "• Use a versão da Steam com o Proton Experimental ou o GE-Proton mais recente (Propriedades › "
            "Compatibilidade).<br>"
            "• Há relatos do launcher aparecer todo preto; trocar a versão do Proton costuma resolver.<br>"
            "• Em tela cheia no Niri, prefira 'tela cheia em janela' no jogo.<br>"
            "• Este app não lê nem altera nada do jogo no Linux.", "muted", rich=True))
        self.body.addWidget(bdo)

        self.list_card = Card()
        self.list_card.lay.addLayout(card_header("games", "Biblioteca da Steam"))
        self.box = QVBoxLayout()
        self.box.setSpacing(0)
        self.list_card.lay.addLayout(self.box)
        self.body.addWidget(self.list_card)
        self._line()
        self._load()

    def _line(self, *_):
        import shutil
        keys = [k for k, cb in self.parts.items() if cb.isChecked()]
        settings.set("lx_launch_parts", keys)
        self.line.setText(steam.launch_options(keys))
        missing = [n for k, n in (("gamemode", "gamemoderun"), ("mangohud", "mangohud"))
                   if k in keys and not shutil.which(n)]
        self.warn.setText("Atenção: " + " e ".join(missing) + " não está instalado; com ele na linha o jogo não "
                          "abre. Instale pela tela Ajustes." if missing else "")

    def _copy(self):
        QApplication.clipboard().setText(self.line.text())
        self.copy_btn.setText("Copiado")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copiar"))

    def _load(self):
        run_async(steam.games, on_done=self._show)

    def _show(self, games):
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not games:
            self.box.addWidget(label("Nenhum jogo da Steam encontrado (procurei em ~/.local/share/Steam, "
                                     "~/.steam e no Flatpak).", "muted"))
            return
        from PySide6.QtWidgets import QFrame
        for g in games:
            row = QFrame()
            row.setObjectName("listrow")
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 8, 4, 8)
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(label(f"<b>{g['name']}</b>", rich=True, wrap=False))
            col.addWidget(label(f"appid {g['appid']} · {g['library']}", "small"))
            h.addLayout(col, 1)
            h.addWidget(button("Jogar", on_click=lambda _=False, a=g["appid"]: steam.launch(a) or info(
                self, "Jogar", "Não encontrei o comando 'steam' para abrir o jogo.")))
            self.box.addWidget(row)


# ---------------------------------------------------------------------------------------------- MangoHud
class MangoHudPage(Page):
    title = "MangoHud"
    subtitle = ("O contador de FPS e sensores por cima do jogo. No Linux ele substitui o overlay do app, que não "
                "funciona em compositores Wayland como o Niri.")

    def build(self):
        cur = mangohud.read()
        st = Card(hero=True)
        st.lay.addLayout(card_header("overlay", "Estado", pill("INSTALADO", C["ok"]) if mangohud.installed()
                                     else pill("NÃO INSTALADO", C["warn"])))
        msg = (f"Arquivo: {mangohud.path()}" if cur["exists"] else "Ainda não há arquivo de configuração.")
        if cur["exists"] and not cur["ours"]:
            msg += "<br>O arquivo atual não foi feito por este app. Ao salvar, ele é guardado ao lado com o nome " \
                   "'MangoHud.conf.antes-do-chinese-control'."
        st.lay.addWidget(label(msg, "muted", rich=True))
        if not mangohud.installed():
            st.lay.addLayout(hrow(button("Instalar pela tela Ajustes", on_click=lambda: self.main.go("ajustes")), None))
        self.body.addWidget(st)

        c = Card()
        c.lay.addLayout(card_header("check", "O que mostrar"))
        g = QGridLayout()
        g.setVerticalSpacing(8)
        self.items: dict[str, QCheckBox] = {}
        for i, (key, text, _d) in enumerate(mangohud.ITEMS):
            cb = QCheckBox(text)
            cb.setChecked(key in cur["items"])
            self.items[key] = cb
            g.addWidget(cb, i // 2, i % 2)
        c.lay.addLayout(g)
        self.body.addWidget(c)

        o = Card()
        o.lay.addLayout(card_header("settings", "Aparência e limite"))
        self.pos = QComboBox()
        for key, text in mangohud.POSITIONS:
            self.pos.addItem(text, key)
        self.pos.setCurrentIndex(max(0, [p for p, _ in mangohud.POSITIONS].index(cur["position"])
                                     if cur["position"] in dict(mangohud.POSITIONS) else 0))
        self.font = QSpinBox()
        self.font.setRange(12, 48)
        self.font.setValue(cur["font_size"])
        self.limit = QSpinBox()
        self.limit.setRange(0, 1000)
        self.limit.setSpecialValueText("sem limite")
        self.limit.setValue(cur["fps_limit"])
        self.compact = Toggle(cur["compact"])
        fg = QGridLayout()
        fg.setHorizontalSpacing(16)
        fg.setVerticalSpacing(10)
        for i, (t, w) in enumerate((("Posição", self.pos), ("Tamanho da letra", self.font),
                                    ("Limite de FPS", self.limit), ("Formato compacto", self.compact))):
            fg.addWidget(label(t, wrap=False), i, 0)
            fg.addWidget(w, i, 1, Qt.AlignLeft)
        fg.setColumnStretch(2, 1)
        o.lay.addLayout(fg)
        o.lay.addWidget(label("Shift direito + F12 mostra e esconde o MangoHud dentro do jogo. Para ele aparecer, "
                              "o jogo precisa ter 'mangohud' nas opções de inicialização (tela Jogos).", "small"))
        self.body.addWidget(o)
        self.saved = label("", "muted")
        self.body.addLayout(hrow(button("Salvar configuração", "primary", self._save), self.saved, None))

    def _save(self):
        text = mangohud.render({k for k, cb in self.items.items() if cb.isChecked()}, self.pos.currentData(),
                               self.limit.value(), self.font.value(), 0.4, self.compact.isChecked())
        try:
            p = mangohud.write(text)
        except OSError as e:
            info(self, "MangoHud", f"Não consegui gravar: {e}")
            return
        self.saved.setText(f"Salvo em {p}. Vale na próxima vez que abrir o jogo.")


# ---------------------------------------------------------------------------------------------- Restauração
class RestorePage(Page):
    title = "Restauração"
    subtitle = "Tudo o que este app aplicou pode ser desfeito aqui: cada ajuste volta ao valor que existia antes."

    def build(self):
        self.body.addLayout(hrow(label("Histórico", "h2"), None, button("Reverter tudo", "danger", self._undo_all),
                                 button("Limpar histórico", on_click=self._clear)))
        self.box = QVBoxLayout()
        self.body.addLayout(self.box)

    def on_show(self):
        if self._built:
            self._load()

    def _load(self):
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = list(reversed(history.load()))
        if not items:
            self.box.addWidget(label("Nada no histórico ainda.", "muted"))
        for e in items[:150]:
            c = Card()
            row = QHBoxLayout()
            when = time.strftime("%d/%m %H:%M", time.localtime(e["time"]))
            st = "desfeito" if e["undone"] else "ativo"
            col = C["muted"] if e["undone"] else C["ok"]
            row.addWidget(label(f"<b>{e['title']}</b> <span style='color:{C['muted']}'>· {e['group']} · {when}</span>"
                                f" <span style='color:{col}'>· {st}</span>", rich=True), 1)
            if not e["undone"] and e.get("reversible", True):
                row.addWidget(button("Desfazer", on_click=lambda _=False, ee=e: self._undo(ee)))
            c.lay.addLayout(row)
            if e.get("detail"):
                c.lay.addWidget(label(e["detail"][:300], "muted"))
            self.box.addWidget(c)

    def _undo(self, e):
        if confirm(self, "Desfazer", f"Voltar ao estado anterior?<br><b>{e['title']}</b>"):
            run_async(engine.undo_entry, e, on_done=lambda r: (r[0] or not r[1] or info(self, "Desfazer", r[1]),
                                                               self._load()))

    def _undo_all(self):
        n = len([e for e in history.active_entries() if e.get("reversible", True)])
        if not n:
            info(self, "Reverter tudo", "Nenhum ajuste ativo aplicado por este app.")
            return
        if confirm(self, "Reverter tudo", f"Desfazer {n} ajuste(s) e voltar aos valores anteriores?"):
            def work(progress=None):
                cnt, errs = engine.undo_all(progress)
                return f"{cnt} desfeito(s)." + ("\n" + "\n".join(errs) if errs else "")
            TaskDialog(self, "Reverter tudo", work, on_done=lambda _: self._load()).exec()

    def _clear(self):
        if confirm(self, "Limpar histórico", "Apagar o histórico? Depois disso nada do que está listado poderá ser "
                   "desfeito por aqui."):
            history.clear()
            self._load()


# ---------------------------------------------------------------------------------------------- Configurações
class SettingsPage(Page):
    title = "Configurações"
    subtitle = "Aparência e dados do Chinese Control para Linux."

    def build(self):
        from lolitos.ui import fx
        from lolitos.ui.theme import THEME_NAMES
        ap = Card()
        ap.lay.addWidget(label("Aparência", "h2"))
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.group = QButtonGroup(self)
        for key, name in THEME_NAMES:
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(key == settings.get("theme"))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.main.set_theme(k))
            self.group.addButton(b)
            seg.addWidget(b)
        seg.addStretch()
        ap.lay.addLayout(hrow(label("Tema", wrap=False), None))
        ap.lay.addLayout(seg)
        self.fx_cb = QComboBox()
        for lv, name in fx.LEVELS:
            self.fx_cb.addItem(name, lv)
        self.fx_cb.setCurrentIndex(fx.current_from_settings())
        self.fx_cb.currentIndexChanged.connect(lambda _: self.main.set_effects(self.fx_cb.currentData()))
        ap.lay.addLayout(hrow(label("Efeitos visuais", wrap=False), self.fx_cb, None))
        self.body.addWidget(ap)

        dd = Card()
        dd.lay.addWidget(label("Dados do aplicativo", "h2"))
        dd.lay.addWidget(label(f"{data_dir()}<br>Histórico (com os valores anteriores de cada ajuste) e "
                               "configurações.", "muted", rich=True))
        self.body.addWidget(dd)

        ab = Card()
        ab.lay.addWidget(label(f"{APP_NAME} {VERSION} · Linux", "h2"))
        ab.lay.addWidget(label("Versão enxuta para Linux: ajustes de kernel e energia, jogos da Steam e MangoHud. "
                               "Tudo roda localmente. Ajustes de sistema passam por um ajudante com privilégio de "
                               "administrador (pkexec) que só aceita as operações deste catálogo.", "muted"))
        self.body.addWidget(ab)
