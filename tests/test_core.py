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
