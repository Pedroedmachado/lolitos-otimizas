"""Jogos instalados (Steam, Epic, Black Desert) e 'Preparar e jogar'.

'Preparar e jogar' só usa o que o próprio Windows oferece para qualquer processo
(prioridade, afinidade, plano de energia, liberar RAM). Nada é injetado no jogo e a
memória dele nunca é lida — seguro para anti-cheat."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from lolitos import POWER_PLAN_NAME
from lolitos.core import registry as reg
from lolitos.core import settings
from lolitos.core.actions import active_scheme, ensure_power_plan
from lolitos.core.system import IS_WIN, run


@dataclass
class Game:
    id: str
    name: str
    store: str            # 'steam' | 'epic' | 'bdo' | 'manual'
    folder: str
    launch: str           # URL steam://, comando, ou caminho do executável
    exes: list[str] = field(default_factory=list)   # nomes do processo do jogo


# ------------------------------------------------------------------ Steam
def _steam_games() -> list[Game]:
    r = reg.read("HKCU", r"Software\Valve\Steam", "SteamPath")
    if not r:
        return []
    steam = Path(str(r[1]))
    libs = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        libs += [Path(m.replace("\\\\", "\\")) for m in
                 re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore"))]
    out, seen = [], set()
    for lib in libs:
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            t = acf.read_text(encoding="utf-8", errors="ignore")
            appid = re.search(r'"appid"\s+"(\d+)"', t)
            name = re.search(r'"name"\s+"([^"]+)"', t)
            inst = re.search(r'"installdir"\s+"([^"]+)"', t)
            if not (appid and name and inst) or appid.group(1) in seen:
                continue
            if appid.group(1) in ("228980",) or "redistributable" in name.group(1).lower():
                continue
            seen.add(appid.group(1))
            folder = lib / "steamapps" / "common" / inst.group(1)
            out.append(Game(f"steam:{appid.group(1)}", name.group(1), "steam", str(folder),
                            f"steam://rungameid/{appid.group(1)}"))
    return out


# ------------------------------------------------------------------ Epic
def _epic_games() -> list[Game]:
    d = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    out = []
    for item in d.glob("*.item") if d.exists() else []:
        try:
            j = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "games" not in [c.lower() for c in j.get("AppCategories", [])]:
            continue
        exe = Path(j.get("LaunchExecutable", "")).name
        out.append(Game(f"epic:{j.get('AppName')}", j.get("DisplayName", j.get("AppName")), "epic",
                        j.get("InstallLocation", ""),
                        f"com.epicgames.launcher://apps/{j.get('CatalogNamespace')}%3A{j.get('CatalogItemId')}%3A"
                        f"{j.get('AppName')}?action=launch&silent=true", [exe] if exe else []))
    return out


def _bdo_game() -> list[Game]:
    from lolitos.bdo import game as bdo
    d = bdo.install_dir()
    if not d:
        return []
    if bdo.is_steam_install():
        launch = f"steam://rungameid/{bdo.STEAM_APPID}"
    else:
        lp = bdo.launcher_path()
        launch = str(lp) if lp else str(bdo.exe_path() or "")
    return [Game("bdo", "Black Desert", "bdo", str(d), launch, [bdo.EXE])]


def _manual_games() -> list[Game]:
    return [Game(g["id"], g["name"], "manual", str(Path(g["exe"]).parent), g["exe"], [Path(g["exe"]).name])
            for g in settings.get("manual_games", []) or []]


def add_manual_game(exe: str, name: str = "") -> None:
    items = settings.get("manual_games", []) or []
    items.append({"id": f"manual:{len(items)}:{Path(exe).stem}", "name": name or Path(exe).stem, "exe": exe})
    settings.set("manual_games", items)


# ------------------------------------------------------------------ GOG, Ubisoft e programas instalados
def _gog_games() -> list[Game]:
    out = []
    base = r"SOFTWARE\WOW6432Node\GOG.com\Games"
    for sub in reg.subkeys("HKLM", base):
        p = f"{base}\\{sub}"
        name, path, exe = (reg.read("HKLM", p, k) for k in ("gameName", "path", "exe"))
        if name and path:
            exes = [Path(str(exe[1])).name] if exe else []
            out.append(Game(f"gog:{sub}", str(name[1]), "gog", str(path[1]),
                            str(exe[1]) if exe else "", exes))
    return out


def _ubisoft_games() -> list[Game]:
    out = []
    base = r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"
    for sub in reg.subkeys("HKLM", base):
        d = reg.read("HKLM", f"{base}\\{sub}", "InstallDir")
        if d and Path(str(d[1])).exists():
            folder = Path(str(d[1]))
            out.append(Game(f"ubisoft:{sub}", folder.name, "ubisoft", str(folder), f"uplay://launch/{sub}/0"))
    return out


PUBLISHERS = ("riot games", "blizzard entertainment", "electronic arts", "rockstar games", "ubisoft", "pearl abyss",
              "garena", "gameforge", "nexon", "kakao games", "smilegate", "amazon games", "bungie",
              "activision", "bandai namco", "netease", "hoyoverse", "mihoyo", "cipsoft", "z8games",
              "krafton", "level infinite", "square enix", "embark studios")
NOT_GAMES = ("launcher", "battle.net", "ea app", "origin", "ubisoft connect", "redistributable", "anti-cheat",
             "anticheat", "vanguard", "social club", "uninstall", "updater")


def _uninstall_games() -> list[Game]:
    """Jogos instalados por launchers sem manifesto fácil (Riot, EA app, Battle.net, Rockstar, etc.)."""
    out = []
    for hive, base in (("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                       ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                       ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall")):
        for sub in reg.subkeys(hive, base):
            p = f"{base}\\{sub}"
            pub = reg.read(hive, p, "Publisher")
            name = reg.read(hive, p, "DisplayName")
            if not (pub and name):
                continue
            pub, name = str(pub[1]).lower(), str(name[1])
            if not any(x in pub for x in PUBLISHERS) or any(x in name.lower() for x in NOT_GAMES):
                continue
            loc = reg.read(hive, p, "InstallLocation")
            icon = reg.read(hive, p, "DisplayIcon")
            exe = str(icon[1]).split(",")[0].strip('"') if icon else ""
            folder = str(loc[1]) if loc and str(loc[1]).strip() else (str(Path(exe).parent) if exe else "")
            if not folder or not Path(folder).exists():
                continue
            exes = [Path(exe).name] if exe.lower().endswith(".exe") and "unins" not in exe.lower() else []
            out.append(Game(f"inst:{sub}", name, "instalado", folder,
                            exe if exes and Path(exe).exists() else "", exes))
    return out


_CACHE: dict = {"t": 0.0, "v": []}


def all_games(max_age: float = 0) -> list[Game]:
    if max_age and time.time() - _CACHE["t"] < max_age:
        return _CACHE["v"]
    out = []
    for f in (_bdo_game, _steam_games, _epic_games, _gog_games, _ubisoft_games, _uninstall_games, _manual_games):
        try:
            out += f()
        except OSError:
            pass
    from lolitos.bdo.game import STEAM_APPID
    if any(g.store == "bdo" for g in out):   # o BDO aparece só uma vez (como Black Desert)
        out = [g for g in out if g.id != f"steam:{STEAM_APPID}" and not (g.store == "instalado" and
                                                                          "black desert" in g.name.lower())]
    # remove duplicados pela pasta (o mesmo jogo visto pelo launcher e pela lista de programas)
    seen, uniq = set(), []
    for g in out:
        key = str(Path(g.folder)).lower().rstrip("\\/")
        if key and key in seen:
            continue
        seen.add(key)
        uniq.append(g)
    from lolitos.modules.known_games import lookup
    for g in uniq:
        k = lookup(g.name, g.folder, g.exes)
        if k and not g.exes:
            g.exes = list(k.exes)
    uniq.sort(key=lambda g: (g.store != "bdo", g.name.lower()))
    _CACHE.update(t=time.time(), v=uniq)
    return uniq


def exe_full_path(g: Game) -> Path | None:
    """Caminho completo do executável principal (necessário para GPU dedicada e tela cheia)."""
    if g.launch.lower().endswith(".exe") and Path(g.launch).exists() and \
            (not g.exes or Path(g.launch).name.lower() in {e.lower() for e in g.exes}):
        return Path(g.launch)
    folder = Path(g.folder)
    names = {e.lower() for e in guess_exes(g)}
    if not names or not folder.exists():
        return None
    for depth, p in enumerate(folder.rglob("*.exe")):
        if p.name.lower() in names:
            return p
        if depth > 4000:
            break
    return None


def guess_exes(g: Game) -> list[str]:
    if g.exes:
        return g.exes
    folder = Path(g.folder)
    if not folder.exists():
        return []
    cands = []
    for p in folder.rglob("*.exe"):
        n = p.name.lower()
        if any(x in n for x in ("unins", "crash", "setup", "redist", "launcher", "helper", "update",
                                "vc_redist", "dxsetup", "easyanticheat", "battleye", "report")):
            continue
        try:
            cands.append((p.stat().st_size, p.name))
        except OSError:
            pass
        if len(cands) > 200:
            break
    cands.sort(reverse=True)
    return [n for _, n in cands[:3]]


# ------------------------------------------------------------------ preparar e jogar
PRIORITY = {"normal": 0x20, "above": 0x8000, "high": 0x80}


def _set_priority(p, level: str) -> str:
    import psutil
    try:
        p.nice({"normal": psutil.NORMAL_PRIORITY_CLASS, "above": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
                "high": psutil.HIGH_PRIORITY_CLASS}[level])
        return f"prioridade {level}"
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return "prioridade não alterada (o jogo protege o próprio processo)"


def affinity_cpus(mode: str) -> list[int] | None:
    """Threads que o jogo deve usar em cada modo (None = todas, sem mexer)."""
    import psutil
    if mode in ("", "all"):
        return None
    n = psutil.cpu_count(logical=True)
    phys = psutil.cpu_count(logical=False) or n
    cpus = list(range(n))
    if mode == "skip0":
        cpus = [c for c in cpus if c not in (0, 1)] if n > 4 else cpus
    elif mode == "physical" and phys < n:
        step = n // phys
        cpus = list(range(0, n, step))
    elif mode == "pcores":
        from lolitos.modules.pcprofile import detect
        cpus = detect().pcores or cpus
    elif mode == "vcache":   # Ryzen X3D com 2 CCDs: o cache 3D fica no primeiro CCD
        cpus = list(range(n // 2))
    return cpus


def _affinity(p, mode: str) -> str:
    import psutil
    cpus = affinity_cpus(mode)
    if cpus is None:
        return ""
    try:
        p.cpu_affinity(cpus)
        return f"afinidade {len(cpus)} de {psutil.cpu_count(logical=True)} threads"
    except (psutil.AccessDenied, psutil.NoSuchProcess, ValueError):
        return "afinidade não alterada (o jogo protege o próprio processo)"


def keep_affinity(proc, mode: str, stop: threading.Event, every: float = 10.0, log=None) -> None:
    """Enquanto o jogo roda, confere os núcleos escolhidos e aplica de novo se o jogo os trocar."""
    import psutil
    cpus = affinity_cpus(mode)
    while not stop.wait(every):
        try:
            if not proc.is_running():
                return
            if cpus is not None and sorted(proc.cpu_affinity()) != sorted(cpus):
                proc.cpu_affinity(cpus)
                if log:
                    log("O jogo trocou os núcleos; os escolhidos foram aplicados de novo.")
        except (psutil.AccessDenied, psutil.NoSuchProcess, ValueError):
            return


class Session(threading.Thread):
    """Prepara o PC, abre o jogo, espera o processo, aplica prioridade e desfaz ao fechar."""

    def __init__(self, g: Game, log=None, on_start=None, on_end=None, wait_minutes: int = 15):
        super().__init__(daemon=True)
        self.g, self.log = g, log or (lambda s: None)
        self.on_start, self.on_end = on_start, on_end
        self.wait = wait_minutes * 60
        self.cancel = threading.Event()
        self.prev_plan = None

    def run(self):
        import psutil
        say = self.log
        opts = settings.get("game_opts", {}).get(self.g.id, {})
        if settings.get("play_free_ram"):
            from lolitos.modules.memory import free_ram
            r = free_ram()
            say(f"RAM liberada: {r['freed'] / 1024**2:.0f} MB")
        if settings.get("play_power_plan") and IS_WIN:
            self.prev_plan = active_scheme()
            try:
                guid = ensure_power_plan(POWER_PLAN_NAME)
                run(["powercfg", "/setactive", guid])
                say(f"Plano '{POWER_PLAN_NAME}' ativo até o jogo fechar")
            except Exception as e:  # noqa: BLE001
                say(f"Plano de energia não trocado: {e}")
        say(f"Abrindo {self.g.name}…")
        if self.g.launch.endswith(".exe") and Path(self.g.launch).exists():
            import subprocess
            subprocess.Popen([self.g.launch], cwd=str(Path(self.g.launch).parent))
        elif self.g.launch:
            os.startfile(self.g.launch) if IS_WIN else None  # noqa: B018
        exes = {e.lower() for e in guess_exes(self.g)}
        say("Esperando o jogo abrir (o launcher/patch pode demorar)…")
        proc, t0 = None, time.time()
        while not self.cancel.is_set() and time.time() - t0 < self.wait:
            for p in psutil.process_iter(["name"]):
                if (p.info["name"] or "").lower() in exes:
                    proc = p
                    break
            if proc:
                break
            time.sleep(2)
        if not proc:
            say("O jogo não abriu a tempo; preparação temporária desfeita.")
            self._restore()
            return
        time.sleep(5)   # deixa o anti-cheat/launcher terminar de subir
        msgs = [_set_priority(proc, opts.get("priority", settings.get("play_priority") or "high")),
                _affinity(proc, opts.get("affinity", ""))]
        say(f"{self.g.name} em execução: " + ", ".join(m for m in msgs if m) + ". Bom jogo!")
        if self.on_start:
            self.on_start(proc)
        stop = threading.Event()
        mode = opts.get("affinity", "")
        if mode not in ("", "all"):
            threading.Thread(target=keep_affinity, args=(proc, mode, stop), kwargs={"log": say},
                             daemon=True).start()
        try:
            proc.wait()
        except psutil.Error:
            pass
        stop.set()
        say(f"{self.g.name} fechou.")
        self._restore()

    def _restore(self):
        if self.prev_plan:
            run(["powercfg", "/setactive", self.prev_plan])
            self.log("Plano de energia anterior restaurado.")
        if self.on_end:
            self.on_end()
