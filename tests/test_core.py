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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
