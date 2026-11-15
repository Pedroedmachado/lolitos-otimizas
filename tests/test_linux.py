"""Versão Linux: ajudante root (com raiz falsa), ações com aplicar/desfazer, Steam, MangoHud e a janela."""
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="só no Linux")


@pytest.fixture
def fake(tmp_path, monkeypatch):
    root = tmp_path / "root"
    for d in ("proc/sys/vm", "proc/sys/kernel", "proc/sys/net/ipv4", "proc/sys/net/core", "etc",
              "sys/devices/system/cpu/cpu0/cpufreq", "sys/devices/system/cpu/cpu1/cpufreq",
              "sys/kernel/mm/transparent_hugepage", "sys/block/nvme0n1/queue"):
        (root / d).mkdir(parents=True)
    (root / "proc/sys/vm/swappiness").write_text("60\n")
    (root / "proc/sys/vm/max_map_count").write_text("65530\n")
    for c in ("cpu0", "cpu1"):
        (root / f"sys/devices/system/cpu/{c}/cpufreq/scaling_governor").write_text("powersave\n")
        (root / f"sys/devices/system/cpu/{c}/cpufreq/scaling_available_governors").write_text("performance powersave\n")
    (root / "sys/kernel/mm/transparent_hugepage/enabled").write_text("[always] madvise never\n")
    (root / "sys/block/nvme0n1/queue/scheduler").write_text("none\n")
    (root / "proc/swaps").write_text("Filename Type Size Used Priority\n")
    monkeypatch.setenv("CC_FAKE_ROOT", str(root))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    return root


def test_helper_only_accepts_listed_paths(fake):
    from lolitos.core.actions import ActionError
    from lolitos.linux import root
    assert root.call("ping") == "pong"
    for bad in ("/etc/passwd", "/etc/sysctl.d/outro.conf", "/etc/sysctl.d/99-chinese-control-../x.conf",
                "/etc/sudoers.d/chinese-control-x.conf"):
        with pytest.raises(ActionError):
            root.call("write_file", path=bad, content="x")
    with pytest.raises(ActionError):
        root.call("sysfs", path="/sys/kernel/mm/../../etc/x", value="1")
    with pytest.raises(ActionError):
        root.call("sysfs", path="/sys/block/sda/device/delete", value="1")
    with pytest.raises(ActionError):
        root.call("sysctl", key="vm.swappiness", value="10; rm -rf /")
    with pytest.raises(ActionError):
        root.call("sysctl", key="../../etc/x", value="1")
    with pytest.raises(ActionError):
        root.call("pacman", pkgs=["gamemode", "qualquer-coisa"])
    with pytest.raises(ActionError):
        root.call("modprobe", name="outro")
    with pytest.raises(ActionError):
        root.call("rodar", cmd="id")


def test_sysctl_apply_and_undo(fake):
    from lolitos.linux.actions import Sysctl
    a = Sysctl("vm.swappiness", 10)
    assert a.applicable() and a.is_applied() is False
    snap = a.capture()
    a.apply()
    assert a.is_applied() and "vm.swappiness = 10" in (fake / "etc/sysctl.d/99-chinese-control-vm_swappiness.conf").read_text()
    a.revert(snap)
    assert (fake / "proc/sys/vm/swappiness").read_text().strip() == "60"
    assert not (fake / "etc/sysctl.d/99-chinese-control-vm_swappiness.conf").exists()
    assert not Sysctl("vm.nao_existe", 1).applicable()
    m = Sysctl("vm.max_map_count", 1048576, at_least=True)
    assert m.is_applied() is False
    (fake / "proc/sys/vm/max_map_count").write_text("2147483642\n")      # maior que o pedido: conta e não é reduzido
    assert m.is_applied()
    m.apply()
    assert (fake / "proc/sys/vm/max_map_count").read_text().strip() == "2147483642"


def test_sysfs_glob_choice_and_undo(fake):
    from lolitos.linux.actions import Sysfs
    g = Sysfs("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor", "performance", "governor")
    assert g.applicable() and g.is_applied() is False
    snap = g.capture()
    assert set(snap["prev"].values()) == {"powersave"} and all(k.startswith("/sys/") for k in snap["prev"])
    g.apply()
    assert g.is_applied()
    assert "w /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor - - - - performance" in \
        (fake / "etc/tmpfiles.d/chinese-control-governor.conf").read_text()
    g.revert(snap)
    assert (fake / "sys/devices/system/cpu/cpu1/cpufreq/scaling_governor").read_text().strip() == "powersave"
    assert not (fake / "etc/tmpfiles.d/chinese-control-governor.conf").exists()
    t = Sysfs("/sys/kernel/mm/transparent_hugepage/enabled", "madvise")
    assert t.applicable() and t.is_applied() is False            # '[always] madvise never' → always
    assert not Sysfs("/sys/kernel/mm/transparent_hugepage/enabled", "inexistente").applicable()
    assert not Sysfs("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor", "schedutil").applicable()
    assert not Sysfs("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference", "performance").applicable()


def test_user_env_and_catalog_through_engine(fake):
    from lolitos.core import engine, history
    from lolitos.core.tweaks import CATALOG
    from lolitos.linux import catalog
    from lolitos.linux.actions import UserEnv, env_file
    e = UserEnv("__GL_SHADER_DISK_CACHE_SKIP_CLEANUP", "1")
    assert e.is_applied() is False
    e.apply()
    assert e.is_applied() and "SKIP_CLEANUP=1" in env_file().read_text()
    e.revert({"prev": None})
    assert not env_file().exists()

    tw = catalog.load()
    assert len(tw) == len(catalog.linux_tweaks()) >= 18 and len({t.id for t in tw}) == len(tw)
    assert all(t.cat in catalog.LINUX_CATS and t.title and t.desc for t in tw)
    t = CATALOG["lx_swappiness"]
    assert t.status() == "off" and t.recommended_here()
    assert engine.apply_tweak(t).ok and t.status() == "on"
    assert history.active_for("lx_swappiness")
    assert engine.undo_tweak(t)[0] and t.status() == "off"
    assert CATALOG["lx_nvme_sched"].status() == "on"                    # já estava assim
    assert CATALOG["lx_epp"].status() == "na"                           # este PC falso não tem EPP
    gm = CATALOG["lx_gamemode"]
    assert not gm.reversible and gm not in catalog.recommended()
    assert engine.apply_tweak(gm).ok and gm.status() == "on"
    assert "gamemode lib32-gamemode" in (fake / "pacman.log").read_text()
    (fake / "proc/swaps").write_text("Filename Type Size Used Priority\n/dev/zram0 partition 1 0 100\n")
    assert catalog.has_zram() and not t.recommended_here()              # com zram, swappiness baixo não é indicado


def test_steam_library_and_launch_line(tmp_path):
    from lolitos.linux import steam
    lib2 = tmp_path / "lib2"
    base = tmp_path / "Steam"
    (base / "steamapps").mkdir(parents=True)
    (lib2 / "steamapps").mkdir(parents=True)
    (base / "steamapps/libraryfolders.vdf").write_text(f'"libraryfolders"\n{{ "0" {{ "path" "{base}" }} "1" {{ "path" "{lib2}" }} }}')
    (base / "steamapps/appmanifest_1.acf").write_text('"AppState" { "appid" "1" "name" "Proton Experimental" }')
    (lib2 / "steamapps/appmanifest_582660.acf").write_text('"AppState"\n{\n\t"appid"\t\t"582660"\n\t"name"\t\t"Black Desert"\n}')
    g = steam.games([str(base)])
    assert [x["name"] for x in g] == ["Black Desert"] and g[0]["appid"] == "582660"
    assert steam.launch_options(["gamemode", "mangohud"]) == "gamemoderun mangohud %command%"
    assert steam.launch_options(["mangohud", "shader"]) == "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 mangohud %command%"
    assert steam.launch_options([]) == "%command%"
    assert steam.launch("1; rm -rf ~") is False


def test_mangohud_roundtrip_keeps_old_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from lolitos.linux import mangohud
    p = mangohud.path()
    p.parent.mkdir(parents=True)
    p.write_text("fps\nposition=top-right\nfps_limit=144\ncoisa_minha=1\n")
    cur = mangohud.read()
    assert cur["exists"] and not cur["ours"] and cur["items"] == {"fps"} and cur["fps_limit"] == 144
    text = mangohud.render({"fps", "gpu_temp", "invalido"}, "bottom-left", 141, 20, 0.4, True)
    mangohud.write(text)
    assert "coisa_minha" in p.with_name("MangoHud.conf.antes-do-chinese-control").read_text()
    again = mangohud.read()
    assert again["ours"] and again["items"] == {"fps", "gpu_temp"} and again["position"] == "bottom-left"
    assert again["fps_limit"] == 141 and again["compact"] and "invalido" not in text


def test_sysinfo_parses_nvidia_smi():
    from lolitos.linux import sysinfo
    g = sysinfo.parse_smi("NVIDIA GeForce RTX 5070, 580.10, 12227, 3051, 37, 54, 88.21\n")
    assert g["name"] == "NVIDIA GeForce RTX 5070" and g["vram_total"] == 12227 and g["util"] == 37 and g["temp"] == 54
    assert sysinfo.parse_smi("") == {} and sysinfo.parse_smi("erro") == {}
    assert sysinfo.parse_smi("X, 1, [N/A], 2, 3, 4, [N/A]")["vram_total"] is None
    assert isinstance(sysinfo.summary(), list)


def test_linux_window_builds_every_page(fake):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from lolitos.linux import catalog
    from lolitos.linux.window import LinuxWindow
    catalog.load()
    w = LinuxWindow()
    for key in w.index:
        w.go(key)
        app.processEvents()
    assert set(w.index) == {"painel", "desempenho", "meupc", "ajustes", "jogos", "mangohud", "restauracao", "config"}
    w.close()
