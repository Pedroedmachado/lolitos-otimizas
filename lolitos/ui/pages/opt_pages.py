"""Telas de otimização separadas por assunto (Windows, Mouse, Teclado, GPU, Defender e IA), a Formatação
(Windows recém-instalado) e o comparador de placas de vídeo."""
from __future__ import annotations

import json
import re

from PySide6.QtWidgets import QComboBox, QProgressBar, QVBoxLayout

from lolitos.core.system import resource_path
from lolitos.core.tweaks import CATALOG, by_cat
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
    """Página com ajustes em cartões (montada na primeira visita)."""
    note = ""

    def tweaks(self):
        return []

    def build(self):
        from lolitos.ui.tweakgrid import TweakGrid
        if self.note:
            self.body.addWidget(label(self.note, "muted", rich=True))
        self.extra_top()
        self.tl = TweakGrid(self.tweaks(), self, header=self.actions, profile=False)
        self.body.addWidget(self.tl)
        self.extra_bottom()

    def extra_top(self):
        pass

    def extra_bottom(self):
        pass

    def on_show(self):
        if self._built:
            self.tl.refresh()


# ===================================================================== Windows (cartões com filtros)
WIN_GROUPS = [("Geral", {"atualizacoes", "seguranca", "apps"}), ("Aparência", {"interface"}),
              ("Desempenho", {"desempenho"}), ("Privacidade", {"privacidade"}), ("Jogos", {"jogos"}),
              ("Rede", {"rede"}), ("IA", {"ia"})]


class WindowsPage(Page):
    title = "Windows"
    subtitle = ("Configurações do sistema. Cada cartão diz o que muda, mostra o estado lido do seu Windows e pode ser "
                "desfeito a qualquer momento. Mouse, teclado e placa de vídeo têm telas próprias.")

    def build(self):
        from lolitos.ui.tweakgrid import TweakGrid
        cats = set().union(*(c for _, c in WIN_GROUPS))
        tweaks = [t for t in CATALOG.values() if t.cat in cats]
        self.tl = TweakGrid(tweaks, self, groups=WIN_GROUPS, header=self.actions)
        self.body.addWidget(self.tl)

    def on_show(self):
        if self._built:
            self.tl.refresh()


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
class DefenderAiPage(Page):
    title = "Defender e IA"
    subtitle = "Libere o Lolitos Control no seu antivírus para nenhum ajuste ser bloqueado e remova a IA do Windows."

    def build(self):
        import sys

        from lolitos.ui.widgets import card_header, pill
        self.body.addWidget(label("Liberar o Lolitos Control no antivírus", "h2"))
        self.body.addWidget(label("Funciona com qualquer antivírus registrado no Windows (Defender, Kaspersky, AVG, "
                                  "Avast, Norton, ESET, Bitdefender, McAfee…). O app nunca desliga nem contorna a "
                                  "proteção: só marca a si mesmo como confiável.", "muted"))
        self.def_card = Card()
        self.def_state = pill("…")
        self.def_card.lay.addLayout(card_header("shield", "Windows Defender", self.def_state))
        self.def_txt = label("Lendo o antivírus…", "muted", rich=True)
        self.def_card.lay.addWidget(self.def_txt)
        self.def_add = button("Liberar no Defender agora", "primary", self._def_add)
        self.def_rm = button("Remover a liberação", on_click=self._def_rm)
        self.def_card.lay.addLayout(hrow(self.def_add, self.def_rm, None))
        self.body.addWidget(self.def_card)
        self.others = QVBoxLayout()
        self.body.addLayout(self.others)
        exe = sys.executable if getattr(sys, "frozen", False) else str(antivirus.app_folder())
        self.exe = exe
        self.body.addWidget(label(f"Caminho do app: <b>{exe}</b><br>Pasta: <b>{antivirus.app_folder()}</b>",
                                  "muted", rich=True))
        self.body.addLayout(hrow(button("Copiar caminho do app", on_click=self._copy),
                                 button("Abrir pasta do app", on_click=lambda: _open(str(antivirus.app_folder()))),
                                 None))
        ia = Card(hero=True)
        self.ia_count = pill("…")
        ia.lay.addLayout(card_header("bolt", "Remover toda a IA do Windows", self.ia_count))
        ia.lay.addWidget(label("Desliga por política o Copilot, o Recall, o Clique para Fazer e a IA dos apps e da "
                               "pesquisa, e remove os componentes de IA. Tudo fica no histórico e pode ser desfeito "
                               "em Restauração.", "muted"))
        self.ia_state = label("", "muted")
        ia.lay.addWidget(self.ia_state)
        self.list_btn = button("Escolher item por item", on_click=self._toggle_list)
        ia.lay.addLayout(hrow(button("Remover toda a IA", "primary", self._remove_ai), self.list_btn, None))
        self.body.addWidget(ia)
        self.tl = TweakList(by_cat("ia"), self)
        self.tl.setVisible(False)
        self.body.addWidget(self.tl)
        run_async(antivirus.products, on_done=self._av)
        self._ia_status()

    def on_show(self):
        if self._built:
            self._ia_status()

    def _ia_status(self):
        def scan():
            ts = by_cat("ia")
            return sum(1 for t in ts if t.status() == "on"), len(ts)

        def done(r):
            on, tot = r
            self.ia_count.setText(f"{on}/{tot}")
            self.ia_count.setStyleSheet(f"color:{C['ok'] if on == tot else C['gold']};")
            self.ia_state.setText(f"{on} de {tot} bloqueios de IA ativos.")
        run_async(scan, on_done=done, _pool=__import__("lolitos.ui.widgets", fromlist=["x"]).status_pool())

    def _av(self, prods):
        from lolitos.ui.widgets import card_header, pill
        d = next((p for p in prods if "defender" in p["name"].lower()), None)
        has = antivirus.defender_has_app()
        if d:
            self.def_state.setText("ATIVO" if d["realtime"] else "DESLIGADO")
            self.def_state.setStyleSheet(f"color:{C['accent2'] if d['realtime'] else C['muted']};")
        else:
            self.def_state.setText("NÃO É O ANTIVÍRUS ATIVO")
        if has:
            self.def_txt.setText(f"<span style='color:{C['ok']}'>O Defender já confia no Lolitos Control.</span>")
        elif d and d["realtime"]:
            self.def_txt.setText("O Defender ainda verifica o Lolitos Control em tempo real e pode bloquear ajustes.")
        else:
            self.def_txt.setText("O Defender não está protegendo em tempo real; veja o seu antivírus abaixo.")
        self.def_add.setVisible(not has)
        self.def_rm.setVisible(bool(has))
        for p in prods:
            if "defender" in p["name"].lower():
                continue
            c = Card()
            st = pill("ATIVO" if p["realtime"] else "DESLIGADO", C["accent2"] if p["realtime"] else C["muted"])
            c.lay.addLayout(card_header("shield", p["name"], st))
            c.lay.addWidget(label("Como liberar: " + antivirus.guide_for(p["name"]), "muted"))
            self.others.addWidget(c)

    def _copy(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self.exe)
        info(self, "Copiado", "Caminho do app copiado.")

    def _def_add(self):
        ok, msg = antivirus.defender_add_app()
        info(self, "Defender", "O Defender agora confia neste app." if ok else msg or "Não foi possível.")
        run_async(antivirus.products, on_done=self._refresh_av)

    def _def_rm(self):
        ok, msg = antivirus.defender_remove_app()
        info(self, "Defender", "Liberação removida." if ok else msg or "Não foi possível.")
        run_async(antivirus.products, on_done=self._refresh_av)

    def _refresh_av(self, prods):
        while self.others.count():
            w = self.others.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._av(prods)

    def _toggle_list(self):
        self.tl.setVisible(not self.tl.isVisible())
        if self.tl.isVisible():
            self.tl.refresh()

    def _remove_ai(self):
        from lolitos.ui.tweaklist import bulk_apply
        if not confirm(self, "Remover toda a IA", "Aplicar todos os bloqueios de IA do Windows?<br><br>Tudo pode ser "
                       "desfeito em Restauração.", yes="Remover"):
            return

        def work(progress=None):
            ts = [t for t in by_cat("ia") if t.status() not in ("on", "na")]
            return bulk_apply(ts, progress) if ts else "Nada pendente."
        TaskDialog(self, "Remover toda a IA", work, on_done=lambda _: (self._ia_status(), self.tl.refresh())).exec()


# ===================================================================== Formatação
# programas por categoria (IDs conferidos no repositório oficial do winget, microsoft/winget-pkgs)
FRESH_GROUPS = [
    ("Essenciais para jogos", "Bibliotecas que a maioria dos jogos pede. Se faltar alguma, o jogo não abre ou dá erro de DLL.", [
        ("Visual C++ 2015-2022 (64 bits)", "Microsoft.VCRedist.2015+.x64"),
        ("Visual C++ 2015-2022 (32 bits)", "Microsoft.VCRedist.2015+.x86"),
        ("Visual C++ 2013 (64 bits)", "Microsoft.VCRedist.2013.x64"), ("Visual C++ 2013 (32 bits)", "Microsoft.VCRedist.2013.x86"),
        ("Visual C++ 2012 (64 bits)", "Microsoft.VCRedist.2012.x64"), ("Visual C++ 2010 (64 bits)", "Microsoft.VCRedist.2010.x64"),
        ("Visual C++ 2008 (64 bits)", "Microsoft.VCRedist.2008.x64"), ("Visual C++ 2005 (64 bits)", "Microsoft.VCRedist.2005.x64"),
        ("DirectX (runtime de usuário final)", "Microsoft.DirectX"), (".NET Desktop Runtime 9", "Microsoft.DotNet.DesktopRuntime.9"),
        (".NET Desktop Runtime 8", "Microsoft.DotNet.DesktopRuntime.8"), (".NET Desktop Runtime 6", "Microsoft.DotNet.DesktopRuntime.6"),
        ("XNA Framework 4.0", "Microsoft.XNARedist"), ("NVIDIA PhysX", "Nvidia.PhysX"),
        ("Java (Oracle JRE)", "Oracle.JavaRuntimeEnvironment"), ("WebView2 Runtime", "Microsoft.EdgeWebView2Runtime")]),
    ("Navegadores", "", [
        ("Google Chrome", "Google.Chrome"), ("Firefox", "Mozilla.Firefox"), ("Brave", "Brave.Brave"),
        ("Opera GX", "Opera.OperaGX"), ("Opera", "Opera.Opera"), ("Microsoft Edge", "Microsoft.Edge"),
        ("Vivaldi", "Vivaldi.Vivaldi")]),
    ("Comunicação", "", [
        ("Discord", "Discord.Discord"), ("Telegram", "Telegram.TelegramDesktop"),
        ("TeamSpeak 3", "TeamSpeakSystems.TeamSpeakClient"), ("Guilded", "Guilded.Guilded"), ("Zoom", "Zoom.Zoom"),
        ("Microsoft Teams", "Microsoft.Teams")]),
    ("Lojas e launchers de jogos", "", [
        ("Steam", "Valve.Steam"), ("Epic Games", "EpicGames.EpicGamesLauncher"), ("Ubisoft Connect", "Ubisoft.Connect"),
        ("EA app", "ElectronicArts.EADesktop"), ("Battle.net", "Blizzard.BattleNet"), ("GOG Galaxy", "GOG.Galaxy"),
        ("Amazon Games", "Amazon.Games"), ("League of Legends (BR)", "RiotGames.LeagueOfLegends.BR"),
        ("Valorant (BR)", "RiotGames.Valorant.BR"), ("Minecraft Launcher", "Mojang.MinecraftLauncher"),
        ("CurseForge", "Overwolf.CurseForge"), ("GeForce NOW", "Nvidia.GeForceNow"), ("osu!", "ppy.osu"),
        ("Playnite", "Playnite.Playnite"), ("Heroic Games Launcher", "HeroicGamesLauncher.HeroicGamesLauncher"),
        ("Prism Launcher", "PrismLauncher.PrismLauncher")]),
    ("Hardware e monitoramento", "", [
        ("MSI Afterburner", "Guru3D.Afterburner"), ("HWiNFO", "REALiX.HWiNFO"), ("CPU-Z", "CPUID.CPU-Z"),
        ("GPU-Z", "TechPowerUp.GPU-Z"), ("HWMonitor", "CPUID.HWMonitor"), ("CrystalDiskInfo", "CrystalDewWorld.CrystalDiskInfo"),
        ("CrystalDiskMark", "CrystalDewWorld.CrystalDiskMark"),
        ("Display Driver Uninstaller (DDU)", "Wagnardsoft.DisplayDriverUninstaller"),
        ("Intel Driver & Support Assistant", "Intel.IntelDriverAndSupportAssistant"), ("Logitech G HUB", "Logitech.GHUB"),
        ("SteelSeries GG", "SteelSeries.GG"), ("Corsair iCUE 5", "Corsair.iCUE.5"), ("Elgato Stream Deck", "Elgato.StreamDeck")]),
    ("Gravação e streaming", "", [
        ("OBS Studio", "OBSProject.OBSStudio"), ("Streamlabs Desktop", "Streamlabs.Streamlabs"), ("ShareX", "ShareX.ShareX"),
        ("Greenshot", "Greenshot.Greenshot"), ("Voicemeeter", "VB-Audio.Voicemeeter"),
        ("Voicemeeter Banana", "VB-Audio.Voicemeeter.Banana"), ("Audacity", "Audacity.Audacity")]),
    ("Música e vídeo", "", [
        ("VLC", "VideoLAN.VLC"), ("MPC-HC", "clsid2.mpc-hc"), ("K-Lite Codec Pack", "CodecGuide.K-LiteCodecPack.Standard"),
        ("Deezer", "Deezer.Deezer"), ("foobar2000", "PeterPawlowski.foobar2000"), ("Stremio", "Stremio.Stremio"),
        ("Plex", "Plex.Plex"), ("HandBrake", "HandBrake.HandBrake")]),
    ("Utilitários", "", [
        ("7-Zip", "7zip.7zip"), ("WinRAR", "RARLab.WinRAR"), ("Everything (busca)", "voidtools.Everything"),
        ("WizTree", "AntibodySoftware.WizTree"), ("WinDirStat", "WinDirStat.WinDirStat"), ("PowerToys", "Microsoft.PowerToys"),
        ("Notepad++", "Notepad++.Notepad++"), ("qBittorrent", "qBittorrent.qBittorrent"), ("AutoHotkey", "AutoHotkey.AutoHotkey"),
        ("Rufus", "Rufus.Rufus"), ("Ventoy", "Ventoy.Ventoy"), ("LocalSend", "LocalSend.LocalSend"),
        ("UniGetUI", "MartiCliment.UniGetUI"), ("Bulk Crap Uninstaller", "Klocman.BulkCrapUninstaller"),
        ("Revo Uninstaller", "RevoUninstaller.RevoUninstaller"), ("BleachBit", "BleachBit.BleachBit"),
        ("Malwarebytes", "Malwarebytes.Malwarebytes"), ("Bitwarden", "Bitwarden.Bitwarden"), ("Proton VPN", "Proton.ProtonVPN"),
        ("Speedtest by Ookla", "Ookla.Speedtest.Desktop"), ("AnyDesk", "AnyDesk.AnyDesk"), ("TeamViewer", "TeamViewer.TeamViewer"),
        ("Parsec", "Parsec.Parsec"), ("Google Drive", "Google.GoogleDrive"), ("Dropbox", "Dropbox.Dropbox"),
        ("MEGA", "Mega.MEGASync"), ("Windows Terminal", "Microsoft.WindowsTerminal")]),
    ("Documentos e criação", "", [
        ("Adobe Acrobat Reader", "Adobe.Acrobat.Reader.64-bit"), ("SumatraPDF", "SumatraPDF.SumatraPDF"),
        ("LibreOffice", "TheDocumentFoundation.LibreOffice"), ("ONLYOFFICE", "ONLYOFFICE.DesktopEditors"),
        ("Notion", "Notion.Notion"), ("Obsidian", "Obsidian.Obsidian"), ("GIMP", "GIMP.GIMP.3"), ("Krita", "KDE.Krita")]),
    ("Programação", "", [
        ("VS Code", "Microsoft.VisualStudioCode"), ("Git", "Git.Git"), ("Python 3.13", "Python.Python.3.13"),
        ("Node.js LTS", "OpenJS.NodeJS.LTS")]),
]
FRESH_APPS = [a for _, _, items in FRESH_GROUPS for a in items]
FRESH_DEFAULT = {"Google.Chrome", "Discord.Discord", "Valve.Steam", "7zip.7zip", "Microsoft.VCRedist.2015+.x64",
                 "Microsoft.VCRedist.2015+.x86", "Microsoft.DirectX", "Microsoft.DotNet.DesktopRuntime.8"}


def _open(url):
    import webbrowser
    webbrowser.open(url)


def fresh_setup(rp, boost, debloat, app_ids, clean, extras=(), progress=None):
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
    if extras:
        say("Extras…")
        ex = [CATALOG[i] for i in extras if i in CATALOG and CATALOG[i].status() not in ("on", "na")]
        say("   " + (bulk_apply(ex, say, restore_point=False) if ex else "já estavam aplicados.").replace("\n", "\n   "))
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


__all__ = ["WindowsPage", "MousePage", "KeyboardPage", "GpuPage", "DefenderAiPage", "GpuComparePage"]
