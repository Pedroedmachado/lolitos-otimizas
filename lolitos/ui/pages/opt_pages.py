"""Telas de otimização separadas por assunto (Windows, Mouse, Teclado, GPU, Defender e IA), a Formatação
(Windows recém-instalado) e o comparador de placas de vídeo."""
from __future__ import annotations

import json
import re

from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QProgressBar, QTabWidget, QVBoxLayout, QWidget

from lolitos.core.system import resource_path
from lolitos.core.tweaks import CATALOG, CATS, by_cat
from lolitos.modules import antivirus
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import TweakList
from lolitos.ui.widgets import Card, Page, TaskDialog, button, confirm, hrow, info, label, run_async

MOUSE_IDS = ["mouse_accel_off", "mouse_sensitivity_default", "mouse_trails_off"]


def _keyboard():
    return [t for t in by_cat("entrada") if t.id not in MOUSE_IDS]


def _mouse():
    return [CATALOG[i] for i in MOUSE_IDS if i in CATALOG]


class _TweakPage(Page):
    """Página com uma lista de ajustes (montada na primeira visita)."""
    note = ""

    def tweaks(self):
        return []

    def build(self):
        if self.note:
            self.body.addWidget(label(self.note, "muted", rich=True))
        self.extra_top()
        self.tl = TweakList(self.tweaks(), self)
        self.body.addWidget(self.tl)
        self.extra_bottom()

    def extra_top(self):
        pass

    def extra_bottom(self):
        pass

    def on_show(self):
        if self._built:
            self.tl.refresh()


# ===================================================================== Windows (abas)
WIN_TABS = ["desempenho", "jogos", "rede", "privacidade", "interface", "atualizacoes", "seguranca", "apps"]


class WindowsPage(Page):
    title = "Windows"
    subtitle = ("Ajustes do sistema separados por assunto. Cada cartão diz o que muda, mostra o estado lido do seu "
                "Windows e pode ser desfeito. Essencial é seguro em qualquer PC; Recomendado tem uma contrapartida "
                "pequena; Avançado pede confirmação.")

    def build(self):
        self.tabs = QTabWidget()
        self.lists: dict[str, TweakList] = {}
        self.holders: dict[str, QVBoxLayout] = {}
        for cat in WIN_TABS:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 12, 0, 0)
            self.holders[cat] = lay
            self.tabs.addTab(w, CATS[cat])
        self.tabs.currentChanged.connect(self._ensure)
        self.body.addWidget(self.tabs)
        self._ensure(0)

    def _ensure(self, idx: int):
        cat = WIN_TABS[idx]
        if cat in self.lists:
            self.lists[cat].refresh()
            return
        tl = TweakList(by_cat(cat), self)
        self.lists[cat] = tl
        self.holders[cat].addWidget(tl)
        self.holders[cat].addStretch()

    def on_show(self):
        if self._built:
            cur = WIN_TABS[self.tabs.currentIndex()]
            if cur in self.lists:
                self.lists[cur].refresh()


# ===================================================================== Mouse / Teclado / GPU
class MousePage(_TweakPage):
    title = "Mouse"
    subtitle = ("Mira consistente: o Windows não acelera nem desacelera o cursor, e 1 cm na mesa é sempre a mesma "
                "distância na tela.")
    note = ("A sensibilidade e o DPI ficam no software do fabricante do mouse e no jogo; aqui só o que o Windows "
            "acrescenta por cima.")

    def tweaks(self):
        return _mouse()

    def extra_bottom(self):
        c = Card()
        c.lay.addWidget(label("<b>Teste do mouse</b> — veja se o polling rate do seu mouse está mesmo em 1000 Hz.",
                              rich=True))
        c.lay.addLayout(hrow(button("Abrir teste do mouse", on_click=lambda: self.main.go("teste_mouse")), None))
        self.body.addWidget(c)


class KeyboardPage(_TweakPage):
    title = "Teclado"
    subtitle = ("Atalhos do Windows que atrapalham no meio da partida (Teclas de Aderência, troca de idioma, "
                "Narrador) e a velocidade de repetição das teclas.")

    def tweaks(self):
        return _keyboard()


class GpuPage(_TweakPage):
    title = "GPU"
    subtitle = ("Placa de vídeo e monitor: agendamento da GPU, modo de jogo, taxa de atualização e o que mais pesa "
                "no quadro a quadro.")

    def tweaks(self):
        return by_cat("gpu")

    def extra_top(self):
        self.mon = label("Lendo os monitores…", "muted", rich=True)
        c = Card()
        c.lay.addWidget(label("Monitores", "h2"))
        c.lay.addWidget(self.mon)
        c.lay.addLayout(hrow(button("Teste de monitor", on_click=lambda: self.main.go("teste_monitor")),
                             button("Comparar placas", on_click=lambda: self.main.go("comparar")), None))
        self.body.addWidget(c)
        from lolitos.modules import display
        run_async(display.monitors, on_done=self._mons, on_error=lambda e: self.mon.setText("Não foi possível ler."))

    def _mons(self, mons):
        if not mons:
            self.mon.setText("Nenhum monitor encontrado.")
            return
        rows = []
        for m in mons:
            low = m["hz"] < m["max_hz"]
            hz = (f"<span style='color:{C['bad']}'>{m['hz']} Hz (o monitor aceita {m['max_hz']} Hz)</span>" if low
                  else f"<span style='color:{C['ok']}'>{m['hz']} Hz, a máxima</span>")
            rows.append(f"<b>{m['name']}</b>{' (principal)' if m['primary'] else ''} · {m['width']}×{m['height']} · {hz}")
        self.mon.setText("<br>".join(rows))


# ===================================================================== Defender e IA
class DefenderAiPage(_TweakPage):
    title = "Defender e IA"
    subtitle = ("O antivírus deste PC e os recursos de inteligência artificial do Windows (Copilot, Recall, "
                "sugestões). O app nunca desliga nem contorna a proteção do antivírus.")

    def tweaks(self):
        return by_cat("ia")

    def extra_top(self):
        av = Card()
        av.lay.addWidget(label("Antivírus", "h2"))
        av.lay.addWidget(label("Antivírus costumam bloquear mudanças no registro, serviços e tarefas, mesmo com o app "
                               "como administrador. Se um ajuste aparecer como BLOQUEADO, libere o app no seu "
                               "antivírus (ele só marca a si mesmo como confiável).", "muted"))
        self.av_lbl = label("Lendo o antivírus…", rich=True)
        av.lay.addWidget(self.av_lbl)
        av.lay.addLayout(hrow(button("Liberar este app no Microsoft Defender", on_click=self._def_add),
                              button("Remover a liberação", on_click=self._def_rm), None))
        self.body.addWidget(av)
        self.body.addWidget(label("Inteligência artificial do Windows", "h2"))
        run_async(antivirus.products, on_done=self._av)

    def _av(self, prods):
        if not prods:
            self.av_lbl.setText("Nenhum antivírus registrado na Central de Segurança do Windows.")
            return
        lines = []
        for p in prods:
            st = (f"<span style='color:{C['ok']}'>proteção em tempo real ligada</span>" if p["realtime"]
                  else f"<span style='color:{C['warn']}'>tempo real desligado</span>")
            g = "" if "defender" in p["name"].lower() else (f"<br><span style='color:{C['muted']}'>Como liberar: "
                                                             f"{antivirus.guide_for(p['name'])}</span>")
            lines.append(f"<b>{p['name']}</b> · {st}{g}")
        lines.append(f"<span style='color:{C['muted']}'>Pasta do app: {antivirus.app_folder()}</span>")
        self.av_lbl.setText("<br>".join(lines))

    def _def_add(self):
        ok, msg = antivirus.defender_add_app()
        info(self, "Defender", "O Defender agora confia neste app." if ok else msg or "Não foi possível.")

    def _def_rm(self):
        ok, msg = antivirus.defender_remove_app()
        info(self, "Defender", "Liberação removida." if ok else msg or "Não foi possível.")


# ===================================================================== Formatação
FRESH_APPS = [("Google Chrome", "Google.Chrome"), ("Firefox", "Mozilla.Firefox"), ("Brave", "Brave.Brave"),
              ("Discord", "Discord.Discord"), ("Steam", "Valve.Steam"), ("Epic Games", "EpicGames.EpicGamesLauncher"),
              ("Ubisoft Connect", "Ubisoft.Connect"), ("EA app", "ElectronicArts.EADesktop"),
              ("Battle.net", "Blizzard.BattleNet"), ("GOG Galaxy", "GOG.Galaxy"), ("7-Zip", "7zip.7zip"),
              ("WinRAR", "RARLab.WinRAR"), ("VLC", "VideoLAN.VLC"), ("OBS Studio", "OBSProject.OBSStudio"),
              ("Telegram", "Telegram.TelegramDesktop"), ("Notepad++", "Notepad++.Notepad++"),
              ("Visual C++ 2015-2022", "Microsoft.VCRedist.2015+.x64"),
              (".NET Desktop Runtime 8", "Microsoft.DotNet.DesktopRuntime.8")]
FRESH_DEFAULT = {"Google.Chrome", "Discord.Discord", "Valve.Steam", "7zip.7zip", "Microsoft.VCRedist.2015+.x64",
                 "Microsoft.DotNet.DesktopRuntime.8"}


class FreshPage(Page):
    title = "Formatação"
    subtitle = ("Acabou de formatar ou comprou um PC novo? Escolha o que fazer e o app deixa o Windows pronto para "
                "jogar de uma vez: ponto de restauração, ajustes recomendados para este PC, remoção do que vem "
                "sobrando, seus programas e limpeza.")

    def build(self):
        steps = Card(hero=True)
        steps.lay.addWidget(label("O que fazer", "h2"))
        self.s_rp = QCheckBox("Criar um ponto de restauração antes de tudo")
        self.s_boost = QCheckBox("Aplicar os ajustes recomendados para este PC (os mesmos do Boost)")
        self.s_debloat = QCheckBox("Remover apps pré-instalados que quase ninguém usa (só os recomendados)")
        self.s_apps = QCheckBox("Instalar os programas marcados abaixo (winget, fontes oficiais)")
        self.s_clean = QCheckBox("Limpar arquivos temporários no final")
        for ck in (self.s_rp, self.s_boost, self.s_debloat, self.s_apps, self.s_clean):
            ck.setChecked(True)
            steps.lay.addWidget(ck)
        self.body.addWidget(steps)

        apps = Card()
        apps.lay.addWidget(label("Programas", "h2"))
        grid = QGridLayout()
        self.app_cks: list[tuple[QCheckBox, str]] = []
        for i, (name, wid) in enumerate(FRESH_APPS):
            ck = QCheckBox(name)
            ck.setChecked(wid in FRESH_DEFAULT)
            ck.setToolTip(wid)
            grid.addWidget(ck, i // 3, i % 3)
            self.app_cks.append((ck, wid))
        apps.lay.addLayout(grid)
        apps.lay.addWidget(label("Mais de 300 outros programas em Instalar apps.", "muted"))
        self.body.addWidget(apps)

        drv = Card()
        drv.lay.addWidget(label("Drivers", "h2"))
        drv.lay.addWidget(label(
            "Instale o driver da placa de vídeo pelo site do fabricante (NVIDIA App, AMD Adrenalin ou Intel Arc) e "
            "o do chipset pelo site da placa-mãe. O Windows Update instala versões genéricas, mais antigas.",
            "muted"))
        drv.lay.addLayout(hrow(
            button("NVIDIA", on_click=lambda: _open("https://www.nvidia.com/pt-br/drivers/")),
            button("AMD", on_click=lambda: _open("https://www.amd.com/pt/support/download/drivers.html")),
            button("Intel", on_click=lambda: _open("https://www.intel.com.br/content/www/br/pt/download-center/home.html")),
            None))
        self.body.addWidget(drv)
        self.go_btn = button("Preparar meu Windows", "primary", self._run)
        self.go_btn.setMinimumHeight(42)
        self.body.addLayout(hrow(self.go_btn, None))

    def _run(self):
        ids = [w for ck, w in self.app_cks if ck.isChecked()] if self.s_apps.isChecked() else []
        todo = [n for ck, n in ((self.s_rp, "ponto de restauração"), (self.s_boost, "ajustes recomendados"),
                                (self.s_debloat, "remoção de apps"), (self.s_clean, "limpeza")) if ck.isChecked()]
        if ids:
            todo.insert(-1 if self.s_clean.isChecked() else len(todo), f"{len(ids)} programa(s)")
        if not todo:
            info(self, "Formatação", "Marque pelo menos uma etapa.")
            return
        if not confirm(self, "Preparar o Windows", "Vai fazer, nesta ordem:<br>• " + "<br>• ".join(todo) +
                       "<br><br>Pode levar de 5 a 30 minutos dependendo da internet. Tudo que for ajuste pode ser "
                       "desfeito em Restauração.", yes="Começar"):
            return
        TaskDialog(self, "Preparando o Windows", fresh_setup, self.s_rp.isChecked(), self.s_boost.isChecked(),
                   self.s_debloat.isChecked(), ids, self.s_clean.isChecked(),
                   on_done=lambda _: self._done()).exec()

    def _done(self):
        if self.main:
            self.main.changed()
        if confirm(self, "Formatação", "Pronto. Vários ajustes só valem depois de reiniciar. Reiniciar o PC agora?",
                   yes="Reiniciar agora", no="Depois"):
            from lolitos.core.system import run
            run(["shutdown", "/r", "/t", "5", "/c", "Lolitos Control: reiniciando para concluir os ajustes."])


def _open(url):
    import webbrowser
    webbrowser.open(url)


def fresh_setup(rp, boost, debloat, app_ids, clean, progress=None):
    from lolitos.catalog.debloat import DEBLOAT_TWEAKS
    from lolitos.catalog.presets import boost_ids
    from lolitos.core import restore
    from lolitos.core.system import human_size
    from lolitos.modules import cleanup, winget
    from lolitos.ui.tweaklist import bulk_apply
    say = progress or (lambda s: None)
    if rp:
        say("1. Ponto de restauração…")
        ok, msg = restore.create()
        say(f"   {msg}")
    if boost:
        say("2. Ajustes recomendados para este PC…")
        pend = [CATALOG[i] for i in boost_ids() if CATALOG[i].status() not in ("on", "na")]
        say("   " + (bulk_apply(pend, say, restore_point=False) if pend else "já estavam todos ativos.")
            .replace("\n", "\n   "))
    if debloat:
        say("3. Removendo apps pré-instalados…")
        pend = [t for t in DEBLOAT_TWEAKS if t.recommended_here() and t.status() not in ("on", "na")]
        say("   " + (bulk_apply(pend, say, restore_point=False) if pend else "nada a remover.").replace("\n", "\n   "))
    if app_ids:
        say("4. Instalando programas…")
        if not winget.ensure_winget():
            say("   O winget não está disponível neste PC; pulei esta etapa.")
        else:
            have = winget.installed_ids()
            for wid in app_ids:
                say(f"   {wid}…")
                r = winget.install_or_upgrade(wid, have)
                say("      ok" if r.ok else f"      código {r.code}")
    if clean:
        say("5. Limpando temporários…")
        freed = 0
        for tid in ("user_temp", "win_temp"):
            _, b, _ = cleanup.clean(cleanup.TARGETS_BY_ID[tid])
            freed += b
        say(f"   {human_size(freed)} liberados")
    return "Windows preparado. Reinicie o PC para concluir."


# ===================================================================== Comparar placas
def gpu_index() -> tuple[str, list[dict]]:
    try:
        d = json.loads(resource_path("gpu_index.json").read_text(encoding="utf-8"))
        return d.get("_sobre", ""), d.get("gpus", [])
    except (OSError, ValueError):
        return "", []


def _norm(s: str) -> str:
    s = re.sub(r"\((r|tm)\)|nvidia|amd|graphics|laptop gpu", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def match_gpu(detected: str, gpus: list[dict]) -> dict | None:
    """Acha a placa detectada no índice (o nome mais longo contido no nome do Windows)."""
    d = _norm(detected)
    best = None
    for g in gpus:
        n = _norm(g["name"])
        n_short = re.sub(r" \d+gb$", "", n)
        if n in d or n_short in d.replace(" 16gb", "").replace(" 8gb", "").replace(" 12gb", ""):
            if not best or len(n) > len(_norm(best["name"])):
                best = g
    return best


class GpuComparePage(Page):
    title = "Comparar placas"
    subtitle = ("Veja quanto mais rápida (ou mais lenta) uma placa de vídeo é em jogos em relação à sua, antes de "
                "comprar ou trocar.")

    def build(self):
        self.about, self.gpus = gpu_index()
        names = [g["name"] for g in self.gpus]
        self.a = QComboBox()
        self.b = QComboBox()
        for cb in (self.a, self.b):
            cb.setEditable(True)
            cb.addItems(names)
            cb.currentIndexChanged.connect(self._cmp)
        c = Card(hero=True)
        c.lay.addLayout(hrow(label("Sua placa", "muted", wrap=False), self.a, label("comparar com", "muted", wrap=False),
                             self.b, None))
        self.res = label("", rich=True)
        c.lay.addWidget(self.res)
        self.bars = QVBoxLayout()
        c.lay.addLayout(self.bars)
        self.body.addWidget(c)
        self.body.addWidget(label("Ranking geral", "h2"))
        self.rank = label("", rich=True)
        self.body.addWidget(self.rank)
        self.body.addWidget(label(self.about, "muted"))
        self.note = label("", "muted")
        c.lay.addWidget(self.note)
        from lolitos.modules import pcprofile
        run_async(pcprofile.detect, on_done=self._mine)

    def _mine(self, p):
        found = None
        for name in p.gpus:
            found = match_gpu(name, self.gpus)
            if found:
                break
        if found:
            self.mine = found["name"]
        else:
            found = next((g for g in self.gpus if g["name"] == "GeForce RTX 3060 12GB"), self.gpus[len(self.gpus) // 2])
            self.note.setText("Não encontrei a sua placa na lista (vídeo integrado ou modelo de notebook). "
                              "Escolha a mais parecida.")
        target = found["score"] * 1.5
        up = min(self.gpus, key=lambda g: abs(g["score"] - target))
        for cb in (self.a, self.b):
            cb.blockSignals(True)
        self.a.setCurrentIndex(self.gpus.index(found))
        self.b.setCurrentIndex(self.gpus.index(up))
        for cb in (self.a, self.b):
            cb.blockSignals(False)
        self._cmp()

    def _bar(self, name, score, top, color):
        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(int(score / top * 1000))
        bar.setFormat(f"{name} — {score:.0f}")
        bar.setTextVisible(True)
        bar.setStyleSheet(f"QProgressBar::chunk{{background:{color};}}")
        return bar

    def _cmp(self):
        if not self.gpus:
            self.res.setText("Índice de placas não encontrado.")
            return
        ga, gb = self.gpus[max(0, self.a.currentIndex())], self.gpus[max(0, self.b.currentIndex())]
        while self.bars.count():
            w = self.bars.takeAt(0).widget()
            if w:
                w.deleteLater()
        top = max(ga["score"], gb["score"])
        self.bars.addWidget(self._bar(ga["name"], ga["score"], top, C["accent"]))
        self.bars.addWidget(self._bar(gb["name"], gb["score"], top, C["accent2"]))
        r = gb["score"] / ga["score"] if ga["score"] else 0
        if abs(r - 1) < 0.04:
            txt = "Praticamente o mesmo desempenho."
        elif r > 1:
            txt = (f"A <b>{gb['name']}</b> é cerca de <b style='color:{C['ok']}'>{(r - 1) * 100:.0f}% mais rápida</b> "
                   f"que a {ga['name']} — por volta de {r:.1f}× os FPS no mesmo jogo e qualidade, se o processador "
                   "acompanhar.")
        else:
            txt = (f"A <b>{gb['name']}</b> é cerca de <b style='color:{C['bad']}'>{(1 - r) * 100:.0f}% mais lenta</b> "
                   f"que a {ga['name']}.")
        if r > 1.6:
            txt += (f"<br><span style='color:{C['muted']}'>Salto grande: confira se o processador e a fonte "
                    "aguentam a placa nova.</span>")
        self.res.setText(txt)
        mine = getattr(self, "mine", ga["name"])
        rows = []
        for i, g in enumerate(self.gpus, 1):
            st = f"color:{C['accent2']};font-weight:700" if g["name"] in (mine, ga["name"]) else ""
            rows.append(f"<tr style='{st}'><td>{i}.</td><td>{g['name']}</td><td align=right>{g['score']:.0f}</td></tr>")
        self.rank.setText("<table cellspacing=3>" + "".join(rows) + "</table>")


__all__ = ["WindowsPage", "MousePage", "KeyboardPage", "GpuPage", "DefenderAiPage", "FreshPage", "GpuComparePage"
           ]
