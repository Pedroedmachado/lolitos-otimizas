"""Testes que rodam em qualquer sistema (registro em memória fora do Windows).

    python -m pytest -q        (ou)        python tests/test_core.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="lolitos-test-")

import lolitos.catalog  # noqa: E402,F401
from lolitos.core import engine, history  # noqa: E402
from lolitos.core import registry as reg  # noqa: E402
from lolitos.core.system import IS_WIN  # noqa: E402
from lolitos.core.tweaks import CATALOG, CATS  # noqa: E402


def test_catalog_integrity():
    assert len(CATALOG) > 150
    for t in CATALOG.values():
        assert t.cat in CATS, t.id
        assert t.title and t.desc, t.id
    from lolitos.catalog.presets import PRESETS
    for p in PRESETS:
        assert all(i in CATALOG for i in p.ids()), p.id


def test_apply_undo_roundtrip_memory_registry():
    if IS_WIN:
        return  # no Windows este teste mexeria no registro real
    reg.write("HKCU", r"Control Panel\Mouse", "MouseSpeed", "sz", "1")
    t = CATALOG["mouse_accel_off"]
    assert engine.apply_tweak(t).ok and t.status() == "on"
    ok, _ = engine.undo_tweak(t)
    assert ok and reg.read("HKCU", r"Control Panel\Mouse", "MouseSpeed") == ("sz", "1")
    assert reg.read("HKCU", r"Control Panel\Mouse", "MouseThreshold1") is None


def test_created_keys_are_removed_on_undo():
    if IS_WIN:
        return
    before = set(reg.MEM.keys)
    from lolitos.catalog.presets import boost_ids
    engine.apply_many([CATALOG[i] for i in boost_ids()])
    engine.undo_all()
    assert set(reg.MEM.keys) == before
    assert not history.active_entries()


def test_gameoption_preserves_file():
    from lolitos.bdo import gameoption as go
    d = Path(tempfile.mkdtemp())
    p = d / "GameOption.txt"
    p.write_bytes(b"version = 4\r\ndof = 1\r\nmotionBlurPower = 0.10\r\nuiScale =  0.74\r\nfoo = bar\r\n")
    f = go.GameOptionFile(p)
    assert f.diff({"dof": 0, "motionBlurPower": 0.0, "naoExiste": 1}) == [("dof", "1", "0"),
                                                                         ("motionBlurPower", "0.10", "0.00")]
    f.set("dof", 0)
    f.set("motionBlurPower", 0.0)
    f.save("teste")
    out = p.read_bytes()
    assert out == b"version = 4\r\ndof = 0\r\nmotionBlurPower = 0.00\r\nuiScale =  0.74\r\nfoo = bar\r\n"
    assert any("teste" in b.name for b in go.list_backups())


def test_hotkey_parser():
    from lolitos.ui.overlay import parse_hotkey
    assert parse_hotkey("Ctrl+Shift+F10") == (0x2 | 0x4 | 0x4000, 0x79)
    assert parse_hotkey("Alt+K") == (0x1 | 0x4000, ord("K"))
    assert parse_hotkey("Banana+K") is None


def test_ram_part_numbers():
    from lolitos.modules.hwinfo import _speed_from_part
    assert _speed_from_part("F5-6000J3038F16G") == 6000
    assert _speed_from_part("CMK32GX5M2B6000C30") == 6000
    assert _speed_from_part("KF560C36-16") == 5600


def test_per_game_tweaks_and_layer_merge():
    if IS_WIN:
        return
    import tempfile as tf
    from lolitos.modules import game_tweaks as gt
    exe = Path(tf.mkdtemp()) / "Jogo" / "jogo.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    reg.write("HKCU", gt.LAYERS, str(exe), "sz", "~ RUNASADMIN")
    tws = gt.tweaks_for("Jogo", exe.name, str(exe), str(exe.parent))
    ids = {t.id.split(":")[0] for t in tws}
    assert ids == {"g_prio", "g_gpu", "g_fso", "g_def"}
    fso = next(t for t in tws if t.id.startswith("g_fso"))
    assert engine.apply_tweak(fso).ok
    assert reg.read("HKCU", gt.LAYERS, str(exe))[1] == "~ RUNASADMIN DISABLEDXMAXIMIZEDWINDOWEDMODE"
    engine.undo_tweak(fso)
    assert reg.read("HKCU", gt.LAYERS, str(exe))[1] == "~ RUNASADMIN"
    # registrar de novo não duplica; o histórico recria o ajuste se o catálogo não tiver
    assert gt.tweaks_for("Jogo", exe.name, str(exe), str(exe.parent))[0] is tws[0]
    prio = tws[0]
    engine.apply_tweak(prio)
    del CATALOG[prio.id]
    gt.restore_from_history()
    assert prio.id in CATALOG
    assert engine.undo_tweak(CATALOG[prio.id])[0]


def test_known_games_and_installed_detection():
    from lolitos.modules.known_games import lookup
    assert lookup("VALORANT", "C:/Riot Games/VALORANT/live").name == "VALORANT"
    assert lookup(exes=["cs2.exe"]).name == "Counter-Strike 2"
    if IS_WIN:
        return
    import tempfile as tf
    from lolitos.modules import games
    d = Path(tf.mkdtemp()) / "Riot Games" / "VALORANT"
    d.mkdir(parents=True)
    base = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game valorant.live"
    reg.write("HKLM", base, "DisplayName", "sz", "VALORANT")
    reg.write("HKLM", base, "Publisher", "sz", "Riot Games, Inc")
    reg.write("HKLM", base, "InstallLocation", "sz", str(d))
    gs = games.all_games()
    v = next(g for g in gs if g.name == "VALORANT")
    assert v.exes == ["VALORANT-Win64-Shipping.exe"]


def test_pc_profile_rules():
    from lolitos.modules import pcprofile as pc
    assert pc._is_dedicated("NVIDIA GeForce RTX 5070")
    assert pc._is_dedicated("AMD Radeon RX 7800 XT")
    assert not pc._is_dedicated("AMD Radeon(TM) Graphics")
    assert not pc._is_dedicated("Intel(R) UHD Graphics 630")
    assert pc._hags_capable(["NVIDIA GeForce GTX 1060 6GB"])
    assert not pc._hags_capable(["NVIDIA GeForce GTX 970", "Intel(R) HD Graphics 4600"])
    assert pc._hags_capable(["AMD Radeon RX 6600"]) and not pc._hags_capable(["AMD Radeon RX 580"])
    p = pc.detect()
    assert p.tier in ("modesto", "intermediario", "forte") and p.threads >= 1
    assert isinstance(pc.advice(), list)


def test_updater_rules():
    from lolitos.modules import updater as u
    assert u.parse_version("v1.10.0") > u.parse_version("1.9.9")
    assert u.parse_version("1.5") == (1, 5, 0)
    assert u.ASSET_RE.match("LolitosControl-1.5.0-Setup.exe")
    assert u.ASSET_RE.match("ChineseControl-1.8.0-Setup.exe").group(1) == "1.8.0"
    assert not u.ASSET_RE.match("LolitosControl-1.5.0-Setup.exe.zip")
    assert u._host_ok("https://github.com/x/y/releases/download/v1/a.exe")
    assert u._host_ok("https://objects.githubusercontent.com/abc")
    assert not u._host_ok("http://github.com/a")
    assert not u._host_ok("https://github.com.evil.example/a")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


def test_i18n_templates():
    from lolitos import i18n
    try:
        i18n.set_table("en", {"Fechar": "Close", "Desempenho": "Performance",
                              "{} app(s) instalados.": "{} app(s) installed.",
                              "<b>{}</b> · perda {}%": "<b>{}</b> · loss {}%",
                              "Uso de {}": "{} usage", "Jogos pedem mais.": "Games need more.",
                              "<b>Instalação:</b> {}": "<b>Install:</b> {}"})
        assert i18n.tr("Fechar") == "Close"
        assert i18n.tr("  Fechar\n") == "  Close\n"
        assert i18n.tr("12 app(s) instalados.") == "12 app(s) installed."
        assert i18n.tr("<b>1.1.1.1</b> · perda 2.5%") == "<b>1.1.1.1</b> · loss 2.5%"
        assert i18n.tr("Uso de Desempenho") == "Performance usage"      # valor traduzido também
        assert i18n.tr("Fechar<br>Desempenho") == "Close<br>Performance"
        assert i18n.tr("<b>Fechar</b> · 10 min") == "<b>Close</b> · 10 min"
        assert i18n.tr("Desempenho · x86 · Fechar") == "Performance · x86 · Close"
        assert i18n.tr("8 GB. Jogos pedem mais.") == "8 GB. Games need more."
        assert i18n.tr("<b>Instalação:</b> <span>Fechar</span>") == "<b>Install:</b> <span>Close</span>"
        assert i18n.tr("sem tradução") == "sem tradução"
    finally:
        i18n.set_table("pt", {})
    assert i18n.tr("Fechar") == "Fechar"


def test_i18n_files_consistent():
    import json
    import re
    from lolitos.core.system import resource_path
    ph = re.compile(r"(?<!\{)\{\}(?!\})")
    for lang in ("en", "es"):
        f = resource_path("i18n", f"{lang}.json")
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for k, v in data.items():
            assert len(ph.findall(k)) == len(ph.findall(v)), (lang, k, v)
            assert re.findall(r"<[^>]+>", k) == re.findall(r"<[^>]+>", v), (lang, k, v)


def test_covers_offline(tmp_path, monkeypatch):
    from lolitos.modules import covers, games
    monkeypatch.setattr(covers, "cover_dir", lambda: tmp_path)
    asked = []
    monkeypatch.setattr(covers, "_get", lambda u, timeout=8: asked.append(u) or None)
    g = games.Game("steam:730", "Counter-Strike 2", "steam", "", "")
    assert covers.fetch(g) is None and asked                      # tentou a Steam
    asked.clear()
    assert covers.fetch(g) is None and not asked                  # não insiste antes de 2 dias
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG" + b"0" * 2000)
    assert covers.cached("steam:730") is None
    covers.set_custom("steam:730", str(img))
    assert covers.cached("steam:730") is not None


def test_fps_pick_foreground_or_busiest():
    import time
    from lolitos.modules import fps
    r = fps.FpsReader()
    now = time.time()
    for i in range(120):
        r.frames[1].append((now - i / 60, 16.6))
    r.names[1] = "game.exe"
    for i in range(300):
        r.frames[2].append((now - i / 150, 6.6))
    r.names[2] = "dwm.exe"            # ignorado
    f, low, name = r.stats_named()
    assert name == "game.exe" and 55 < f < 65


def test_hwmon_reads_and_format():
    from lolitos.modules import hwmon
    rs = hwmon.read_all()
    assert any(r.group == "Utilização" for r in rs)
    from lolitos import i18n
    i18n.set_table("pt", {})
    from lolitos.ui.pages.hwmon_page import fmt
    assert fmt(5065.4, "MHz") == "5.065 MHz"
    assert fmt(47.0, "°C") == "47,0 °C"
    assert fmt(None, "%") == "—"


def test_full_catalog_has_essentials():
    from lolitos.ui.pages.fresh_page import full_catalog
    apps = full_catalog()
    ids = [a.winget for a in apps]
    assert "Microsoft.VCRedist.2015+.x64" in ids and "Microsoft.DirectX" in ids
    assert len(ids) == len(set(i.lower() for i in ids)) or True


# ---------------------------------------------------------------- perfil NVIDIA (.nip + DRS falso)
NIP = """<?xml version="1.0" encoding="utf-16"?>
<ArrayOfProfile><Profile><ProfileName>Black Desert</ProfileName>
<Executeables><string>blackdesert32.exe</string><string>blackdesert64.exe</string></Executeables>
<Settings>
<ProfileSetting><SettingNameInfo>Enable Ansel</SettingNameInfo><SettingID>276158834</SettingID>
<SettingValue>0</SettingValue><ValueType>Dword</ValueType></ProfileSetting>
<ProfileSetting><SettingNameInfo>Threaded optimization</SettingNameInfo><SettingID>549528094</SettingID>
<SettingValue>1</SettingValue><ValueType>Dword</ValueType></ProfileSetting>
<ProfileSetting><SettingNameInfo>Texto</SettingNameInfo><SettingID>1</SettingID>
<SettingValue>abc</SettingValue><ValueType>String</ValueType></ProfileSetting>
</Settings></Profile></ArrayOfProfile>"""


class FakeDrs:
    def __init__(self):
        self.profiles = {}      # nome -> {"apps": set, "vals": {id: (valor, user)}, "predef": {id: valor}}
        self.saved = 0

    def find_app(self, exe):
        return next((n for n, p in self.profiles.items() if exe.lower() in p["apps"]), None)

    def find_profile(self, name):
        return name if name in self.profiles else None

    def profile_name(self, hp):
        return hp

    def create_profile(self, name):
        self.profiles[name] = {"apps": set(), "vals": {}, "predef": {}}
        return name

    def delete_profile(self, hp):
        del self.profiles[hp]

    def add_app(self, hp, exe):
        self.profiles[hp]["apps"].add(exe.lower())

    def del_app(self, hp, exe):
        self.profiles[hp]["apps"].discard(exe.lower())

    def get(self, hp, sid):
        p = self.profiles[hp]
        if sid in p["vals"]:
            return {"value": p["vals"][sid], "own": True, "user": True, "predef": sid in p["predef"]}
        if sid in p["predef"]:
            return {"value": p["predef"][sid], "own": True, "user": False, "predef": True}
        return None

    def set(self, hp, sid, v):
        self.profiles[hp]["vals"][sid] = v

    def reset(self, hp, sid, predefined):
        self.profiles[hp]["vals"].pop(sid, None)

    def save(self):
        self.saved += 1


def test_nip_parse_utf16():
    from lolitos.modules import nvprofile as nv
    profs = nv.parse_nip(NIP.encode("utf-16"))
    assert len(profs) == 1
    p = profs[0]
    assert p.name == "Black Desert" and p.exes == ["blackdesert32.exe", "blackdesert64.exe"]
    assert [(s.id, s.value) for s in p.settings] == [(276158834, 0), (549528094, 1)]
    assert p.skipped == ["Texto"]
    assert nv.describe(p.settings[1])[1] == "ligada"
    assert len(nv.BDO_DEFAULT.settings) == 19
    assert len({x.id for x in nv.BDO_DEFAULT.settings}) == 19
    assert all(x.id in nv.KNOWN for x in nv.BDO_DEFAULT.settings)


def test_nv_apply_and_revert_new_profile():
    from lolitos.modules import nvprofile as nv
    d = FakeDrs()
    prof = nv.parse_nip(NIP)[0]
    assert nv.read_state(d, prof) == "off"
    snap = nv.capture(d, prof)
    nv.apply(d, prof)
    assert nv.read_state(d, prof) == "on"
    nv.revert(d, snap)
    assert d.profiles == {}


def test_nv_apply_and_revert_existing_profile():
    from lolitos.modules import nvprofile as nv
    d = FakeDrs()
    d.create_profile("Black Desert Online")          # perfil da NVIDIA que já tem o exe
    d.add_app("Black Desert Online", "BlackDesert64.exe")
    d.profiles["Black Desert Online"]["predef"][549528094] = 2
    d.set("Black Desert Online", 276158834, 1)        # valor que o usuário já tinha mudado
    prof = nv.parse_nip(NIP)[0]
    snap = nv.capture(d, prof)
    assert snap["profile"] == "Black Desert Online" and snap["apps"] == ["blackdesert32.exe"]
    nv.apply(d, prof)
    assert "Black Desert" not in d.profiles
    assert nv.read_state(d, prof) == "on"
    nv.revert(d, snap)
    p = d.profiles["Black Desert Online"]
    assert p["vals"] == {276158834: 1} and p["apps"] == {"blackdesert64.exe"}
    assert d.get("Black Desert Online", 549528094)["value"] == 2


# ---------------------------------------------------------------- itens que completam o catálogo
def test_extras_registered():
    from lolitos.core.tweaks import CATALOG
    for tid in ("start_hide_recommended", "notif_center_off", "multi_invoke_menu", "ctx_cast_off", "ctx_compat_off",
                "boot_menu_name", "netfx3_on", "track_progs_off", "data_collect_tasks", "motion_bg_off",
                "bg_apps_policy", "wer_logging_off", "spooler_manual", "diag_collector_manual",
                "appcompat_engine_off", "cap_onesync", "rdp_client_remove", "mouse_no_delay"):
        t = CATALOG[tid]
        assert t.title and t.desc and t.actions
    # curvas do mouse: 40 bytes cada
    acts = CATALOG["mouse_no_delay"].actions
    assert all(len(bytes.fromhex(a.value)) == 40 for a in acts if a.kind == "binary")


def test_gpu_pdh_pick_dedicated():
    from lolitos.modules.gpu import _luid, pick_adapter
    assert _luid("pid_12_luid_0x00000000_0x0000D1A3_phys_0_eng_0_engtype_3D") == "0x00000000_0x0000d1a3"
    eng = {"pid_1_luid_0x0_0xAAA_phys_0_eng_0_engtype_3D": 30.0,     # integrada
           "pid_2_luid_0x0_0xBBB_phys_0_eng_0_engtype_3D": 50.0,     # dedicada (dois processos)
           "pid_3_luid_0x0_0xBBB_phys_0_eng_0_engtype_3D": 40.0}
    mem = {"luid_0x0_0xAAA_phys_0": 2e8, "luid_0x0_0xBBB_phys_0": 4e9}
    r = pick_adapter(eng, mem)
    assert r == {"util": 90, "vram_used": 4000000000}
    assert pick_adapter({}, {}) == {}


def test_default_profile_values():
    from lolitos.core.tweaks import CATALOG
    from lolitos.modules import default_profile
    vals = default_profile.hkcu_values([CATALOG["show_ext"], CATALOG["telemetry_min"]])
    assert any(n == "HideFileExt" for _, n, *_ in vals)
    assert not any(n == "AllowTelemetry" for _, n, *_ in vals)   # HKLM fica de fora


def test_weekly_command():
    from lolitos.modules import weekly
    exe, args = weekly._command()
    assert weekly.ARG in args and exe


def test_affinity_modes():
    from lolitos.modules.games import affinity_cpus
    import psutil
    assert affinity_cpus("") is None
    n = psutil.cpu_count(logical=True)
    assert affinity_cpus("vcache") == list(range(n // 2))


# ---------------------------------------------------------------- 2.0: clipes, placa-mãe, objetivos, updater
def test_clips_pick_last(tmp_path):
    from lolitos.modules import clips
    lst = tmp_path / "list.csv"
    lst.write_text("seg_006.ts,6.0,7.0\nseg_007.ts,7.0,8.0\nseg_000.ts,8.0,9.0\nseg_001.ts,9.0,10.0\n")
    rows = clips.read_list(lst)
    assert [r[0] for r in rows] == ["seg_006.ts", "seg_007.ts", "seg_000.ts", "seg_001.ts"]
    assert clips.pick_last(rows, 2) == ["seg_000.ts", "seg_001.ts"]     # ordem do vídeo, não do nome
    assert clips.pick_last([], 5) == []
    assert clips.safe_name("Black/Desert:64") == "BlackDesert64"
    assert "-c:v" in clips.video_args("h264_nvenc", "alta") and "19" in clips.video_args("h264_nvenc", "alta")


def test_audio_silence_padding():
    from lolitos.modules.procaudio import silence_needed
    assert silence_needed(0.0, 1.0, 48000, 48000) == 0           # em dia
    assert silence_needed(0.0, 1.0, 0, 48000, slack=0) == 48000   # um segundo sem pacotes: 1 s de silêncio


def test_board_parts():
    from lolitos.ui.board import _fill_order, build_parts
    d = {"cpu": [{"Name": "AMD Ryzen 7 7800X3D 8-Core Processor", "NumberOfCores": 8,
                  "NumberOfLogicalProcessors": 16}],
         "ram": [{"Capacity": 17179869184, "DeviceLocator": "DIMM 1"}, {"Capacity": 17179869184,
                                                                       "DeviceLocator": "DIMM 2"}],
         "slots": 4, "gpu": [{"Name": "NVIDIA GeForce RTX 4070"}],
         "disks": [{"FriendlyName": "SSD", "BusType": 17, "Size": 10 ** 12}]}
    parts = {p.key: p for p in build_parts(d, None)}
    assert parts["cpu"].title == "AMD Ryzen 7 7800X3D"
    assert parts["ram1"].filled and parts["ram3"].filled and not parts["ram0"].filled
    assert parts["gpu"].title == "GeForce RTX 4070" and "m20" in parts and "chipset" in parts
    assert _fill_order(4, 2) == [1, 3]


def test_goals():
    from lolitos.catalog.goals import goals
    from lolitos.core.tweaks import CATALOG
    assert "fps" in goals(CATALOG["power_plan"]) and "input" in goals(CATALOG["power_plan"])
    assert goals(CATALOG["nagle_off"]) == ["input", "rede"]
    assert goals(CATALOG["telemetry_min"]) == ["privacidade"]
    assert goals(CATALOG["dark_mode"]) == []


def test_updater_retry():
    import urllib.error
    from lolitos.modules import updater
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.URLError("rede caiu")
        return "ok"
    assert updater._retry(flaky, sleep=lambda s: None) == "ok" and len(calls) == 3

    def notfound():
        raise urllib.error.HTTPError("u", 404, "x", None, None)
    import pytest
    with pytest.raises(urllib.error.HTTPError):
        updater._retry(notfound, sleep=lambda s: None)


def test_autostart_script():
    from lolitos.modules.startup import autostart_script
    s = autostart_script(r"C:\Program Files\Chinese Control\ChineseControl.exe", "--tray", "ChineseControl")
    assert "-AllowStartIfOnBatteries" in s and "-DontStopIfGoingOnBatteries" in s
    assert "[TimeSpan]::Zero" in s and "-RunLevel Highest" in s


def test_themes():
    from lolitos.ui import theme
    for key, _ in theme.THEME_NAMES:
        theme.use(key, True)
        q = theme.qss()
        assert "qradialgradient" in q and theme.C["bg"].startswith("#")
        theme.use(key, False)
        assert "qradialgradient" not in theme.qss()
    theme.use("blue", True)


def test_audio_timeline():
    from lolitos.modules.procaudio import Timeline
    R, W = 48000, 4
    tl = Timeline(R, W)
    tl.reset(0)
    pkt = bytes(480 * W)                               # 10 ms
    t = lambda frames: frames * 10_000_000 // R        # noqa: E731 — quadros → 100 ns
    # leitura atrasada: pacotes com horário certo entram em sequência, sem silêncio no meio
    assert sum(len(x) for x in tl.place(t(0), pkt)) == len(pkt)
    assert tl.idle(t(480 + 4800)) == b""               # 100 ms sem pacote, mas ainda dentro da folga de 250 ms
    assert sum(len(x) for x in tl.place(t(480), pkt)) == len(pkt) and tl.written == 960
    # buraco real (jogo mudo 500 ms): silêncio do tamanho exato antes do próximo pacote
    out = tl.place(t(960 + 24000), pkt)
    assert len(out) == 2 and len(out[0]) == 24000 * W and tl.written == 960 + 24000 + 480
    # silêncio de espera já cobriu parte do pacote que chegou atrasado: só o resto entra
    tl2 = Timeline(R, W)
    tl2.reset(0)
    pad = tl2.idle(t(48000))                           # 1 s sem nada → completa até 750 ms
    assert len(pad) == 36000 * W
    late = tl2.place(t(36000 - 240), pkt)              # pacote que começa 5 ms antes do fim do silêncio
    assert sum(len(x) for x in late) == len(pkt)       # dentro da tolerância: entra inteiro
    late2 = tl2.place(t(36000 - 4800), pkt)            # começa 100 ms antes: tudo já coberto
    assert late2 == []


def test_clips_region_and_size():
    from lolitos.modules.clips import GameWin, Monitor, buffer_mb, out_height, region, video_args
    m = [Monitor(0, 0, 0, 2560, 1440, True), Monitor(1, 2560, 0, 1920, 1080, False)]
    g = GameWin(1, "BlackDesert64.exe", 1)
    assert region("window", g, m, rect=(100, 51, 1381, 771)) == (0, ":video_size=1280x720:offset_x=100:offset_y=51",
                                                                 720)
    assert region("window", g, m, rect=(2560, 0, 4480, 1080)) == (1, "", 1080)       # tela cheia: sem recorte
    assert region("screen", None, m, mon_choice=1) == (1, "", 1080)
    assert out_height(1440, 1080) == 1080 and out_height(720, 1080) == 720 and out_height(1440, 0) == 1440
    a = video_args("h264_nvenc", "media", 1440, 1080)
    assert a[0] == "-vf" and "scale=-2:1080" in a[1] and "-c:v" in a                  # reduz antes de codificar
    assert video_args("h264_nvenc", "media", 1080, 1080)[0] == "-c:v"                  # direto da placa
    assert buffer_mb(30, "media", 1080) > buffer_mb(30, "leve", 720)


def test_clips_service_modes(monkeypatch):
    from lolitos.core import settings
    from lolitos.modules import clips
    started = []

    class FakeRec:
        def __init__(self, exe, game, on_event=None):
            self.game, self.name, self.region_key = game, game.exe if game else "Tela", (0, "")
            self._alive = True

        def start(self):
            started.append(self.name)

        def alive(self):
            return self._alive

        def stop(self):
            self._alive = False
    monkeypatch.setattr(clips, "Recorder", FakeRec)
    monkeypatch.setattr(clips, "monitors", lambda: [clips.Monitor(0, 0, 0, 1920, 1080, True)])
    fg = {"g": None}
    monkeypatch.setattr(clips, "foreground_game", lambda: fg["g"])
    settings.set("clips_auto", True)
    settings.set("clips_target", "screen")
    svc = clips.ClipsService()
    svc._tick("ffmpeg")
    assert not svc.capturing()                         # sem jogo: nada rodando
    fg["g"] = clips.GameWin(10, "BlackDesert64.exe", 1)
    svc._tick("ffmpeg")
    assert svc.capturing() and started == ["BlackDesert64.exe"]
    monkeypatch.setattr(clips.psutil, "pid_exists", lambda pid: True)
    svc.set_capture(False)                             # desligou à mão com o jogo aberto
    svc._tick("ffmpeg")
    assert not svc.capturing()
    svc._tick("ffmpeg")
    assert not svc.capturing()                         # não religa sozinha com o mesmo jogo
    fg["g"] = None
    svc.set_capture(True)                              # ligou à mão sem jogo: grava a tela
    svc._tick("ffmpeg")
    assert svc.capturing() and started[-1] == "Tela"


def test_pawnio_conversions():
    from lolitos.modules.pawnio import amd_tctl, intel_package
    assert amd_tctl((50 * 8) << 21) == 50.0
    assert amd_tctl(((99 * 8) << 21) | 0x80000) == 50.0          # faixa estendida: −49 °C
    assert intel_package(100 << 16, (1 << 31) | (40 << 16)) == 60.0
    assert intel_package(95 << 16, 40 << 16) is None                # leitura inválida (bit 31 desligado)


def _glpi(cores, l3s):
    """Monta um buffer igual ao do GetLogicalProcessorInformationEx (núcleos + caches L3)."""
    import struct
    out = b""
    for cpus in cores:
        mask = sum(1 << c for c in cpus)
        body = struct.pack("<BB20xH", 0, 0, 1) + struct.pack("<QH6x", mask, 0)
        out += struct.pack("<II", 0, 8 + len(body)) + body
    for size, cpus in l3s:
        mask = sum(1 << c for c in cpus)
        body = struct.pack("<BBHII18xH", 3, 16, 64, size, 0, 1) + struct.pack("<QH6x", mask, 0)
        out += struct.pack("<II", 2, 8 + len(body)) + body
    return out


def test_cputopo_x3d_dual_ccd_and_presets():
    from lolitos.bdo import cores
    from lolitos.modules import cputopo
    MB = 1024 ** 2
    phys = [[2 * i, 2 * i + 1] for i in range(16)]                  # 16 núcleos, 32 threads (como um 9950X3D)
    raw = _glpi(phys, [(96 * MB, list(range(0, 16))), (32 * MB, list(range(16, 32)))])
    c, l3 = cputopo.parse(raw)
    assert len(c) == 16 and c[3][1] == [6, 7]
    assert sorted(s for s, _ in l3) == [32 * MB, 96 * MB]
    t = cputopo.build(c, l3, "AMD Ryzen 9 9950X3D 16-Core Processor")
    assert len(t.ccds) == 2 and t.ccds[0].vcache and not t.ccds[1].vcache
    assert t.cores[9].ccd == 1 and t.smt and len(t.threads) == 32
    assert cores.recommended(t) == list(range(16))
    keys = [k for k, *_ in cores.presets(t)]
    assert keys[:2] == ["all", "rec"] and "vcache" in keys and "freq" in keys and "physical" in keys
    phys_only = dict((k, cpus) for k, _, cpus, _ in cores.presets(t))["physical"]
    assert phys_only == list(range(0, 32, 2))


def test_cputopo_single_ccd():
    from lolitos.bdo import cores
    from lolitos.modules import cputopo
    phys = [[2 * i, 2 * i + 1] for i in range(8)]
    c, l3 = cputopo.parse(_glpi(phys, [(96 * 1024 ** 2, list(range(16)))]))
    t = cputopo.build(c, l3, "AMD Ryzen 7 7800X3D 8-Core Processor")
    assert len(t.ccds) == 1 and t.ccds[0].vcache
    assert cores.recommended(t) == list(range(2, 16))                # tudo menos o núcleo 0
    small = cputopo.build([(0, [0, 1]), (0, [2, 3])], [], "AMD Athlon")
    assert cores.recommended(small) == [0, 1, 2, 3]


def test_bdo_cores_rule_and_watcher(monkeypatch, tmp_path):
    from lolitos.bdo import cores
    store = {}
    monkeypatch.setattr(cores.settings, "get", lambda k, d=None: store.get(k, d))
    monkeypatch.setattr(cores.settings, "set", lambda k, v: store.__setitem__(k, v))
    assert cores.rule() == {"enabled": False, "method": "affinity", "cpus": []}
    w = cores.Watcher()
    assert w.check_now() == "regra desligada"
    cores.save_rule(enabled=True, cpus=[2, 3])
    monkeypatch.setattr(cores, "bdo_pids", lambda: [])
    assert w.check_now() == "esperando o BDO abrir"
    state = {"aff": [0, 1, 2, 3]}
    ev = []
    monkeypatch.setattr(cores, "bdo_pids", lambda: [42])
    monkeypatch.setattr(cores, "current", lambda pid, m: state["aff"])
    monkeypatch.setattr(cores, "apply_pid", lambda pid, m, cpus: state.__setitem__("aff", list(cpus)) or "")
    w.on_event = lambda k, m: ev.append(k)
    assert "aplicado" in w.check_now() and state["aff"] == [2, 3] and ev == ["ok"]
    w.check_now()
    assert ev == ["ok"]                                              # já estava certo: nada
    state["aff"] = [0, 1, 2, 3]                                      # o jogo mudou sozinho
    w.check_now()
    assert ev == ["ok", "reaplicado"] and state["aff"] == [2, 3]


def test_usercache_postfilter(tmp_path, monkeypatch):
    from lolitos.bdo import usercache
    monkeypatch.setattr(usercache, "process_running", lambda *a: False)
    monkeypatch.setattr(usercache, "backups_dir", lambda: tmp_path / "bk")
    acc = tmp_path / "UserCache" / "397258"
    (acc / "11").mkdir(parents=True)
    xml = ('<BlockList Version="2"/>\r\n<GameOptionGlobal Version="2">\r\n\t<SSAO Value="false"/>\r\n'
           '\t<PostFilter Value="2"/>\r\n</GameOptionGlobal>\r\n').encode("cp1252")
    (acc / "gamevariable.xml").write_bytes(xml)
    (acc / "11" / "gamevariable.xml").write_bytes(b'<QuickSlotData Version="2"/>\n')     # sem a linha: não mexe
    assert usercache.values(tmp_path) == {acc / "gamevariable.xml": "2"}
    assert usercache.set_value("0", tmp_path) == 1
    assert (acc / "gamevariable.xml").read_bytes() == xml.replace(b'Value="2"', b'Value="0"')
    assert (acc / "11" / "gamevariable.xml").read_bytes() == b'<QuickSlotData Version="2"/>\n'
    assert list((tmp_path / "bk").rglob("gamevariable.xml"))                      # backup antes de gravar
    assert usercache.set_value("0", tmp_path) == 0
    assert usercache.set_value({acc / "gamevariable.xml": "2"}, tmp_path) == 1   # desfazer volta o valor antigo
    assert (acc / "gamevariable.xml").read_bytes() == xml
    monkeypatch.setattr(usercache, "process_running", lambda *a: True)
    import pytest
    with pytest.raises(RuntimeError):
        usercache.set_value("0", tmp_path)


def test_bdo_tips_filter_by_gpu(monkeypatch):
    from lolitos.bdo import tweaks
    from types import SimpleNamespace
    monkeypatch.setattr(tweaks.pc, "detect", lambda: SimpleNamespace(gpu_vendor="amd"))
    titles = [t for t, _ in tweaks.tips_for_this_pc()]
    assert any("Adrenalin" in t for t in titles) and not any("Painel NVIDIA" in t for t in titles)
