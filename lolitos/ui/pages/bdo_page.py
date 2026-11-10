"""Black Desert: Windows para o BDO, GameOption.txt, rede do servidor, travamentos e caches."""
from __future__ import annotations

import statistics
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFileDialog, QGridLayout, QLineEdit,
                               QTabWidget, QVBoxLayout, QWidget)

from lolitos.bdo import game as bdo
from lolitos.bdo import gameoption as go
from lolitos.bdo.tweaks import INGAME_TIPS
from lolitos.catalog.presets import PRESETS_BY_ID
from lolitos.core.system import human_size, process_running, run
from lolitos.core.tweaks import CATALOG, by_cat
from lolitos.core import history
from lolitos.i18n import tr
from lolitos.modules import games, nvprofile
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import TweakList, bulk_apply
from lolitos.ui.widgets import (ui_call, Card, Page, TaskDialog, button, confirm, hrow, info, label, run_async)


class BdoPage(Page):
    title = "Black Desert"
    subtitle = ("Otimizações específicas do BDO para Guerra de Nodes e Cerco. Nada é injetado no jogo e a memória "
                "dele nunca é lida: só o Windows e o arquivo de opções que o próprio jogo usa.")

    def build(self):
        # ------------------------------------------------------------ instalação
        top = Card(hero=True)
        self.install_lbl = label("Procurando o Black Desert…", rich=True)
        top.lay.addWidget(self.install_lbl)
        self.state_lbl = label("", "muted")
        top.lay.addWidget(self.state_lbl)
        self.play_btn = button("▶  Preparar e jogar", "primary", self._play)
        top.lay.addLayout(hrow(self.play_btn, button("Escolher pasta do jogo…", on_click=self._pick_dir),
                               button("Procurar de novo", on_click=lambda: self._locate(True)),
                               button("Abrir pasta de opções", on_click=self._open_docs), None))
        self.play_log = label("", "muted")
        top.lay.addWidget(self.play_log)
        self.body.addWidget(top)

        tabs = QTabWidget()
        tabs.addTab(self._tab_windows(), "Windows para o BDO")
        from lolitos.ui.bdo_cores import CoresPanel
        tabs.addTab(CoresPanel(self), "Núcleos da CPU")
        tabs.addTab(self._tab_options(), "Opções do jogo (GameOption)")
        tabs.addTab(self._tab_network(), "Rede do servidor")
        tabs.addTab(self._tab_crashes(), "Travamentos e caches")
        tabs.addTab(self._tab_tips(), "Checklist fora do app")
        self.body.addWidget(tabs)
        self._locate()

    # ================================================================ instalação
    def _locate(self, refresh=False):
        def work():
            d = bdo.install_dir(refresh)
            return d, bdo.exe_path(), go.find_gameoption()
        run_async(work, on_done=self._located)

    def _located(self, r):
        d, exe, gof = r
        self.gof_path = gof
        ok, bad = C["ok"], C["bad"]
        lines = ["<b>Instalação:</b> " + (f"<span style='color:{ok}'>{d}</span>" if d else
                                            f"<span style='color:{bad}'>não encontrada — escolha a pasta</span>"),
                 f"<b>Executável:</b> {exe or '—'}",
                 f"<b>GameOption.txt:</b> {gof or 'não encontrado (abra o jogo uma vez)'}"]
        self.install_lbl.setText("<br>".join(lines))
        self.state_lbl.setText("O jogo está aberto." if process_running(bdo.EXE) else "O jogo está fechado.")
        self.play_btn.setEnabled(bool(d))
        if hasattr(self, "win_list"):
            self.win_list.refresh()
        if hasattr(self, "opt_box"):
            self._load_options()

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Pasta do Black Desert (onde fica o bin64)")
        if d:
            p = Path(d)
            if p.name.lower() == "bin64":
                p = p.parent
            bdo.set_install_dir(str(p))
            self._locate()

    def _open_docs(self):
        run(["explorer", str(bdo.DOCS)])

    def _play(self):
        g = next((x for x in games.all_games() if x.id == "bdo"), None)
        if not g:
            info(self, "Black Desert", "Instalação não encontrada.")
            return
        self.play_btn.setEnabled(False)
        self.play_log.setText("Preparando…")

        def log(s):
            ui_call(lambda: self.play_log.setText(s))

        def started(proc):
            ui_call(lambda: self.state_lbl.setText("O jogo está aberto."))
            if self.main:
                ui_call(self.main.overlay_auto_on)

        def ended():
            def fin():
                self.play_btn.setEnabled(True)
                self.state_lbl.setText("O jogo está fechado.")
                self.play_log.setText("Jogo fechado: plano de energia e overlay voltaram ao normal.")
            ui_call(fin)
            if self.main:
                ui_call(self.main.overlay_auto_off)

        self.session = games.Session(g, log, started, ended)
        self.session.start()

    # ================================================================ Windows
    def _tab_windows(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        p = PRESETS_BY_ID["bdo_guerra"]
        c = Card()
        c.lay.addWidget(label(f"<b>{p.name}</b>", rich=True))
        c.lay.addWidget(label(p.desc, "muted"))
        c.lay.addLayout(hrow(button("Aplicar pacote do Windows para Guerra", "primary", self._apply_pack), None))
        lay.addWidget(c)
        lay.addWidget(self._nvidia_card())
        lay.addWidget(label("Ajustes do executável do BDO", "h2"))
        self.win_list = TweakList(by_cat("bdo") + [CATALOG["nagle_off"], CATALOG["net_throttling_off"]], self,
                                  search=False)
        lay.addWidget(self.win_list)
        lay.addStretch()
        return w

    # ---------------------------------------------------------------- perfil NVIDIA
    def _nvidia_card(self):
        c = Card()
        c.lay.addWidget(label("<b>Painel de Controle NVIDIA para o BDO</b>", "h3", rich=True))
        c.lay.addWidget(label("As configurações 3D do Black Desert gravadas direto no driver, pela interface oficial "
                              "da NVIDIA — o mesmo lugar que o Painel NVIDIA usa. Dá para desfazer a qualquer hora.",
                              "muted"))
        self.nv_src = label("", "muted", wrap=False)
        c.lay.addWidget(self.nv_src)
        self.nv_grid = QGridLayout()
        self.nv_grid.setHorizontalSpacing(16)
        self.nv_grid.setVerticalSpacing(3)
        c.lay.addLayout(self.nv_grid)
        self.nv_state = label("", rich=True)
        c.lay.addWidget(self.nv_state)
        self.nv_apply = button("Aplicar no driver", "primary", self._nv_apply)
        self.nv_undo = button("Desfazer", on_click=self._nv_undo)
        c.lay.addLayout(hrow(self.nv_apply, self.nv_undo, button("Importar arquivo .nip…", on_click=self._nv_import),
                             button("Usar o perfil do app", on_click=self._nv_default),
                             button("Abrir Painel NVIDIA", on_click=self._nv_panel), None))
        self._nv_fill()
        return c

    def _nv_fill(self):
        prof = nvprofile.bdo_profile()
        custom = nvprofile.custom_file().exists()
        self.nv_src.setText(tr("Perfil: {} · {}").replace("{}", prof.name, 1).replace(
            "{}", tr("importado por você") if custom else tr("o que acompanha o app"), 1)
            + " · " + ", ".join(prof.exes))
        while self.nv_grid.count():
            it = self.nv_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.nv_vals = {}
        for i, s in enumerate(prof.settings):
            name, val = nvprofile.describe(s)
            self.nv_grid.addWidget(label(tr(name), "barname", wrap=False), i, 0)
            self.nv_grid.addWidget(label(tr(val), wrap=False), i, 1)
            cur = label("", "muted", wrap=False)
            self.nv_grid.addWidget(cur, i, 2)
            self.nv_vals[s.id] = cur
        self.nv_grid.setColumnStretch(3, 1)
        self.nv_state.setText(tr("Lendo o driver…"))

        def work():
            t = CATALOG["bdo_nvidia_profile"]
            if not t.applicable():
                return None
            return t.status(), nvprofile.current_values(prof)

        def done(r):
            on = bool(history.active_for("bdo_nvidia_profile"))
            self.nv_undo.setEnabled(on)
            if r is None:
                self.nv_apply.setEnabled(False)
                self.nv_state.setText(f"<span style='color:{C['muted']}'>"
                                      + tr("Placa NVIDIA ou driver não encontrados neste PC.") + "</span>")
                return
            st, vals = r
            self.nv_apply.setEnabled(st != "on")
            for s in prof.settings:
                v = vals.get(s.id)
                ok = v == s.value
                self.nv_vals[s.id].setText(tr("✓ no driver") if ok else (
                    tr("hoje: {}").replace("{}", tr(nvprofile.describe(nvprofile.NipSetting(s.id, v))[1]))
                    if v is not None else tr("hoje: padrão")))
                self.nv_vals[s.id].setStyleSheet(f"color:{C['ok'] if ok else C['muted']};")
            txt, col = {"on": ("Aplicado no driver", C["ok"]), "partial": ("Aplicado em parte", C["gold"])}.get(
                st, ("Ainda não aplicado", C["muted"]))
            self.nv_state.setText(f"<b style='color:{col}'>{tr(txt)}</b>")
        run_async(work, on_done=done)

    def _nv_after(self, *_):
        self._nv_fill()
        self.win_list.refresh()
        if self.main:
            self.main.changed()

    def _nv_apply(self):
        t = CATALOG["bdo_nvidia_profile"]
        TaskDialog(self, "Perfil NVIDIA do BDO", bulk_apply, [t], restore_point=False, on_done=self._nv_after).exec()

    def _nv_undo(self):
        from lolitos.core import engine
        t = CATALOG["bdo_nvidia_profile"]

        def work(progress=None):
            ok, msg = engine.undo_tweak(t, progress)
            return "Perfil NVIDIA voltou como estava." if ok else msg
        TaskDialog(self, "Perfil NVIDIA do BDO", work, on_done=self._nv_after).exec()

    def _nv_switch(self, prof):
        """Troca o perfil usado; se o antigo estava aplicado, desfaz e aplica o novo."""
        from lolitos.core import engine
        t = CATALOG["bdo_nvidia_profile"]
        was_on = bool(history.active_for(t.id))

        def work(progress=None):
            if was_on:
                engine.undo_tweak(t, progress)
            nvprofile.save_custom(prof)
            if was_on or t.applicable():
                r = engine.apply_tweak(t, progress)
                return r.msg or "Perfil aplicado no driver."
            return "Perfil salvo. Ele é aplicado quando houver uma placa NVIDIA."
        TaskDialog(self, "Perfil NVIDIA do BDO", work, on_done=self._nv_after).exec()

    def _nv_import(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("Importar perfil NVIDIA"), "",
                                           tr("Perfil do NVIDIA Profile Inspector") + " (*.nip);;XML (*.xml)")
        if not f:
            return
        try:
            profs = nvprofile.parse_nip(f)
        except (OSError, ValueError) as e:
            info(self, "Importar perfil NVIDIA", str(e))
            return
        prof = next((p for p in profs if any("blackdesert" in e.lower() for e in p.exes)), profs[0])
        lines = "<br>".join(f"• {tr(n)}: <b>{tr(v)}</b>" for n, v in map(nvprofile.describe, prof.settings))
        extra = ""
        if prof.skipped:
            extra = "<br><br>" + tr("Ignorados (não são números): {}").replace("{}", ", ".join(prof.skipped))
        if not any("blackdesert" in e.lower() for e in prof.exes):
            prof.exes = list(nvprofile.BDO_DEFAULT.exes)
            extra += "<br><br>" + tr("O arquivo não cita o BlackDesert64.exe; os .exe do BDO serão usados.")
        if not confirm(self, "Importar perfil NVIDIA",
                       tr("Usar o perfil '{}' para o BDO e aplicar no driver?").replace("{}", prof.name)
                       + "<br><br>" + lines + extra, yes="Aplicar"):
            return
        self._nv_switch(prof)

    def _nv_default(self):
        if not nvprofile.custom_file().exists():
            info(self, "Perfil NVIDIA do BDO", "Já está usando o perfil que acompanha o app.")
            return
        self._nv_switch(None)

    def _nv_panel(self):
        import os
        import subprocess
        for exe in (r"%ProgramFiles%\NVIDIA Corporation\Control Panel Client\nvcplui.exe",):
            p = os.path.expandvars(exe)
            if os.path.exists(p):
                subprocess.Popen([p])
                return
        try:
            subprocess.Popen(["explorer.exe", "shell:AppsFolder\\NVIDIACorp.NVIDIAControlPanel_56jybvy8sckqj!"
                              "NVIDIACorp.NVIDIAControlPanel"])
        except OSError:
            info(self, "Painel NVIDIA", "Não encontrei o Painel de Controle NVIDIA neste PC.")

    def _apply_pack(self):
        ts = [CATALOG[i] for i in PRESETS_BY_ID["bdo_guerra"].ids()]
        pend = [t for t in ts if t.status() not in ("on", "na")]
        if not pend:
            info(self, "Pacote de Guerra", "Tudo já está aplicado neste PC.")
            return
        TaskDialog(self, f"Pacote de Guerra ({len(pend)} ajustes)", bulk_apply, pend,
                   on_done=lambda _: (self.win_list.refresh(), self.main and self.main.changed())).exec()

    # ================================================================ GameOption
    def _tab_options(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addWidget(label("Predefinições", "h2"))
        lay.addWidget(label("Cada uma só mexe em chaves que já existem no seu GameOption.txt, mostra o que vai "
                            "mudar e faz backup antes. Feche o jogo antes de aplicar (ele regrava o arquivo ao sair).",
                            "muted"))
        grid = QGridLayout()
        for i, p in enumerate(go.PRESETS):
            c = Card()
            c.lay.addWidget(label(f"<b>{p.name}</b>", rich=True))
            c.lay.addWidget(label(p.desc, "muted"))
            c.lay.addLayout(hrow(button("Ver e aplicar", "primary", lambda _=False, pr=p: self._preset(pr)), None))
            grid.addWidget(c, i // 2, i % 2)
        lay.addLayout(grid)
        lay.addWidget(label("Editor das opções conhecidas", "h2"))
        lay.addWidget(label("Valores lidos do seu arquivo agora. Altere e clique em Salvar.", "muted"))
        self.opt_box = QGridLayout()
        self.opt_box.setHorizontalSpacing(18)
        lay.addLayout(self.opt_box)
        self.opt_widgets = {}
        lay.addLayout(hrow(button("Salvar alterações", "primary", self._save_options),
                           button("Recarregar", on_click=self._load_options),
                           button("Backups…", on_click=self._backups), None))
        lay.addStretch()
        return w

    def _gof(self):
        if not getattr(self, "gof_path", None):
            info(self, "GameOption.txt", "Arquivo não encontrado. Abra o BDO uma vez e feche, depois tente de novo.")
            return None
        return go.GameOptionFile(self.gof_path)

    def _preset(self, p):
        f = self._gof()
        if not f:
            return
        ch = f.diff(p.values)
        if not ch:
            info(self, p.name, "Seu arquivo já está assim. Nada a mudar.")
            return
        rows = "".join(f"<tr><td>{go.KNOWN.get(k, (k,))[0]}</td><td style='color:{C['muted']}'>{a}</td>"
                       f"<td>→</td><td style='color:{C['accent2']}'><b>{b}</b></td></tr>" for k, a, b in ch)
        if not confirm(self, p.name, f"<p>{len(ch)} opção(ões) vão mudar:</p><table cellspacing=6>{rows}</table>"
                       "<p>Um backup é salvo antes.</p>", yes="Aplicar"):
            return
        try:
            changes, bk = go.apply_preset(f, p)
            info(self, p.name, f"{len(changes)} opção(ões) alteradas. Backup: {bk.name}")
        except RuntimeError as e:
            info(self, p.name, str(e))
        self._load_options()

    def _load_options(self):
        while self.opt_box.count():
            it = self.opt_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.opt_widgets = {}
        if not getattr(self, "gof_path", None):
            self.opt_box.addWidget(label("GameOption.txt não encontrado.", "muted"), 0, 0)
            return
        f = go.GameOptionFile(self.gof_path)
        i = 0
        for key, (name, kind, tip) in go.KNOWN.items():
            val = f.get(key)
            if val is None:
                continue
            val = val.strip()
            if kind == "bool" and val in ("0", "1"):
                wdg = QCheckBox()
                wdg.setChecked(val == "1")
            elif kind == "float":
                wdg = QDoubleSpinBox()
                wdg.setRange(-10, 10000)
                wdg.setDecimals(2)
                wdg.setSingleStep(0.05)
                try:
                    wdg.setValue(float(val))
                except ValueError:
                    wdg = QLineEdit(val)
            else:
                wdg = QLineEdit(val)
                wdg.setMaximumWidth(140)
            lb = label(name)
            lb.setToolTip(f"{key}" + (f" — {tip}" if tip else ""))
            wdg.setToolTip(lb.toolTip())
            self.opt_box.addWidget(lb, i // 2, (i % 2) * 2)
            self.opt_box.addWidget(wdg, i // 2, (i % 2) * 2 + 1, Qt.AlignLeft)
            self.opt_widgets[key] = wdg
            i += 1

    def _save_options(self):
        f = self._gof()
        if not f:
            return
        changed = 0
        for k, wdg in self.opt_widgets.items():
            if isinstance(wdg, QCheckBox):
                v = 1 if wdg.isChecked() else 0
            elif isinstance(wdg, QDoubleSpinBox):
                v = wdg.value()
            else:
                v = wdg.text().strip()
            changed += f.set(k, v)
        if not changed:
            info(self, "Opções", "Nada mudou.")
            return
        try:
            bk = f.save("editor")
            info(self, "Opções", f"{changed} opção(ões) salvas. Backup: {bk.name}")
        except RuntimeError as e:
            info(self, "Opções", str(e))

    def _backups(self):
        items = go.list_backups()
        if not items:
            info(self, "Backups", "Nenhum backup ainda.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Escolha o backup para restaurar", str(items[0].parent),
                                              "GameOption (*.txt)")
        if not path or not getattr(self, "gof_path", None):
            return
        if confirm(self, "Restaurar", f"Restaurar <b>{Path(path).name}</b> sobre o seu GameOption.txt atual?"):
            try:
                go.restore_backup(Path(path), self.gof_path)
                info(self, "Restaurar", "Backup restaurado.")
            except RuntimeError as e:
                info(self, "Restaurar", str(e))
            self._load_options()

    # ================================================================ rede
    def _tab_network(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addWidget(label("Com o BDO aberto, o app lê na tabela de conexões do Windows com qual servidor o jogo "
                            "está falando e mede a latência real até ele (handshake TCP na mesma porta do jogo — "
                            "funciona mesmo quando o servidor ignora ping).", "muted"))
        self.net_btn = button("Detectar servidor e medir 30 s", "primary", self._net_start)
        lay.addLayout(hrow(self.net_btn, None))
        self.net_out = label("", rich=True)
        lay.addWidget(self.net_out)
        lay.addStretch()
        return w

    def _net_start(self):
        conns = bdo.server_connections()
        if not conns:
            self.net_out.setText("Abra o Black Desert e entre no personagem; depois clique de novo.")
            return
        c = conns[0]
        self.net_btn.setEnabled(False)
        others = ", ".join(f"{x.ip}:{x.port}" for x in conns[1:4])
        self.net_out.setText(f"Servidor do jogo: <b>{c.ip}:{c.port}</b>" + (f" · outras: {others}" if others else "")
                             + "<br>Medindo…")

        def measure(progress=None):
            rtts, lost = [], 0
            for i in range(60):
                v = bdo.tcp_ping(c.ip, c.port)
                if v is None:
                    lost += 1
                else:
                    rtts.append(v)
                if progress and i % 5 == 4:
                    progress(f"{i + 1}/60")
                time.sleep(0.5)
            return rtts, lost

        def done(r):
            rtts, lost = r
            self.net_btn.setEnabled(True)
            if not rtts:
                self.net_out.setText(f"Servidor {c.ip}:{c.port} não respondeu ao teste.")
                return
            avg, mn, mx = statistics.mean(rtts), min(rtts), max(rtts)
            jit = statistics.mean(abs(a - b) for a, b in zip(rtts, rtts[1:])) if len(rtts) > 1 else 0
            verdict = ("excelente para PvP" if avg < 40 and jit < 5 else "bom" if avg < 80 and jit < 10
                       else "alto — teste com cabo e veja a aba Rede › Analisar rota")
            col = C["ok"] if "excelente" in verdict else C["warn"] if verdict == "bom" else C["bad"]
            self.net_out.setText(
                f"Servidor do jogo: <b>{c.ip}:{c.port}</b><br>"
                f"Latência média <b>{avg:.0f} ms</b> (mín {mn:.0f} / máx {mx:.0f}) · variação {jit:.1f} ms · "
                f"falhas {lost}/60<br><span style='color:{col}'>Resultado: {verdict}</span><br>"
                f"<span style='color:{C['muted']}'>Para ver onde está a perda, use Rede › Analisar rota com o IP "
                f"{c.ip}.</span>")
        run_async(measure, on_done=done, on_progress=lambda s: self.net_out.setText(
            f"Servidor do jogo: <b>{c.ip}:{c.port}</b><br>Medindo… {s}"))

    # ================================================================ travamentos e caches
    def _tab_crashes(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        self.crash_lbl = label("Lendo relatórios de travamento…", rich=True)
        lay.addWidget(self.crash_lbl)
        lay.addWidget(label("Caches do BDO que podem ser limpos", "h2"))
        lay.addWidget(label("A pasta UserCache nunca é tocada: ela guarda seus atalhos, barra de skills e layout.",
                            "muted"))
        self.cache_box = QVBoxLayout()
        lay.addLayout(self.cache_box)
        lay.addLayout(hrow(button("Limpar selecionados", "primary", self._clean), None))
        run_async(lambda: (bdo.crash_summary(), bdo.cache_sizes()), on_done=self._crashes_loaded)
        lay.addStretch()
        return w

    def _crashes_loaded(self, r):
        s, caches = r
        if s["total"] == 0:
            self.crash_lbl.setText(f"<span style='color:{C['ok']}'>Nenhum relatório de travamento do BDO.</span>")
        else:
            last = time.strftime("%d/%m %H:%M", time.localtime(s["last"])) if s["last"] else "—"
            tips = []
            if s["d7"] >= 2:
                tips.append("Mais de um crash na semana: limpe o cache de shaders (Limpeza), confira se o EXPO/XMP "
                            "está estável (o check-up mostra desligamentos inesperados) e use o driver de vídeo "
                            "estável mais recente.")
            if s["repeat"] >= 2:
                tips.append("O mesmo endereço de crash se repete: costuma ser driver de vídeo ou overlay "
                            "(desligue overlays de terceiros e teste).")
            self.crash_lbl.setText(
                f"<b>{s['total']}</b> travamento(s) registrados · <b>{s['d7']}</b> nos últimos 7 dias · "
                f"<b>{s['d30']}</b> em 30 dias · último: {last}<br>"
                + (f"<span style='color:{C['muted']}'>{s['gpu']}</span><br>" if s["gpu"] else "")
                + "".join(f"<br>• {t}" for t in tips))
        self.cache_checks = {}
        while self.cache_box.count():
            it = self.cache_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for c in caches:
            ck = QCheckBox(f"{c['name']} — {c['human']} ({c['files']} arquivo(s))")
            ck.setChecked(c["bytes"] > 0)
            ck.setEnabled(c["bytes"] > 0)
            ck.setToolTip(c["desc"])
            self.cache_checks[c["id"]] = ck
            holder = Card()
            holder.lay.addWidget(ck)
            holder.lay.addWidget(label(c["desc"], "muted"))
            self.cache_box.addWidget(holder)

    def _clean(self):
        ids = [k for k, ck in self.cache_checks.items() if ck.isChecked()]
        if not ids:
            return
        try:
            n, freed = bdo.clean_caches(ids)
            info(self, "Caches do BDO", f"{n} arquivo(s) removidos, {human_size(freed)} liberados.")
        except RuntimeError as e:
            info(self, "Caches do BDO", str(e))
        run_async(lambda: (bdo.crash_summary(), bdo.cache_sizes()), on_done=self._crashes_loaded)

    # ================================================================ dicas
    def _tab_tips(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addWidget(label("O que não dá (ou não deve) ser mudado por arquivo — faça uma vez e pronto.", "muted"))
        for t, d in INGAME_TIPS:
            c = Card()
            c.lay.addWidget(label(f"<b>{t}</b>", rich=True))
            c.lay.addWidget(label(d, "muted"))
            lay.addWidget(c)
        lay.addStretch()
        return w

