"""Aplica e desfaz cada ajuste do catálogo num Windows de verdade e imprime uma linha JSON por ajuste.

Só para a máquina descartável do GitHub Actions (mexe no registro, serviços e energia de verdade)."""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LOCALAPPDATA_REAL"] = os.environ.get("LOCALAPPDATA", "")

import lolitos.catalog  # noqa: E402,F401
from lolitos.core import engine  # noqa: E402
from lolitos.core import registry as reg  # noqa: E402
from lolitos.core.tweaks import CATALOG  # noqa: E402

SKIP_KINDS = {"Appx", "Capability", "Feature"}
SKIP_IDS = {"onedrive_remove", "remove_recall_feature", "hpet_device_off", "reserved_storage_off"}
engine.restart_explorer = lambda *a, **k: None


def with_timeout(fn, secs=240):
    box = {}

    def go():
        try:
            box["v"] = fn()
        except Exception as e:  # noqa: BLE001
            box["e"] = f"{type(e).__name__}: {e}"
    th = threading.Thread(target=go, daemon=True)
    th.start()
    th.join(secs)
    if th.is_alive():
        return None, "timeout"
    return box.get("v"), box.get("e", "")


def raw(t):
    out = []
    for a in t.actions:
        if type(a).__name__ == "Reg":
            try:
                out.append(repr(reg.read(a.hive, a.path, a.name)))
            except Exception as e:  # noqa: BLE001
                out.append(f"err {e}")
        else:
            out.append(None)
    return out


def acts(t):
    rows = []
    for a in t.actions:
        try:
            ap = a.applicable()
        except Exception as e:  # noqa: BLE001
            ap = f"err {e}"
        try:
            st = a.is_applied() if ap is True else None
        except Exception as e:  # noqa: BLE001
            st = f"err {e}"
        rows.append([type(a).__name__, a.describe()[:160], ap, st])
    return rows


def force_off(t):
    from lolitos.core.system import run
    try:
        for a in t.actions:
            k = type(a).__name__
            if not a.applicable():
                continue
            if k == "Reg":
                if a.delete:
                    reg.write(a.hive, a.path, a.name, "sz", "x")
                else:
                    reg.delete_value(a.hive, a.path, a.name)
            elif k == "Service":
                if not run(["sc.exe", "config", a.name, "start=", "auto"]).ok:
                    return False, f"sc config {a.name} recusado"
            elif k == "Power":
                other = 50 if a.value == 100 else (1 if a.value == 0 else 0)
                a._set(other, other)
            elif k == "Task":
                a._set(not a.enabled)
            else:
                return False, f"sem teste forçado para {k}"
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def main():
    print("WINVER", sys.getwindowsversion(), flush=True)
    for t in CATALOG.values():
        kinds = {type(a).__name__ for a in t.actions}
        r = {"id": t.id, "cat": t.cat, "kinds": sorted(kinds)}
        if kinds & SKIP_KINDS or t.id in SKIP_IDS:
            r["result"] = "skipped"
            r["before"], _ = with_timeout(t.status, 120)
            print("TW " + json.dumps(r, ensure_ascii=False), flush=True)
            continue
        t0 = time.time()
        r["before"], err = with_timeout(t.status, 120)
        r["acts_before"] = acts(t)
        raw0 = raw(t)
        if r["before"] in ("na", "unknown", None) or err:
            r["result"] = "na" if r["before"] == "na" else f"status:{r['before']} {err}"
            print("TW " + json.dumps(r, ensure_ascii=False), flush=True)
            continue
        if r["before"] == "on":
            # já vem assim neste Windows: põe no estado contrário à força para poder testar aplicar e desfazer
            forced, why = force_off(t)
            r["forced"] = forced
            st, _ = with_timeout(t.status, 120)
            if not forced or st == "on":
                r["result"] = "already_on"
                r["why"] = why or f"continuou {st}"
                print("TW " + json.dumps(r, ensure_ascii=False), flush=True)
                continue
            r["before"] = st
            raw0 = raw(t)
        res, err = with_timeout(lambda: engine.apply_tweak(t))
        r["apply_ok"] = bool(res and res.ok)
        r["apply_msg"] = (res.msg if res else "") or err
        r["after"], _ = with_timeout(t.status, 120)
        r["acts_after"] = acts(t)
        if t.reversible:
            u, err = with_timeout(lambda: engine.undo_tweak(t))
            r["undo_ok"] = bool(u and u[0])
            r["undo_msg"] = (u[1] if u else "") or err
            r["final"], _ = with_timeout(t.status, 120)
            raw1 = raw(t)
            r["reg_restored"] = raw0 == raw1
            if raw0 != raw1:
                r["reg_diff"] = [[a.describe()[:120], x, y] for a, x, y in zip(t.actions, raw0, raw1) if x != y]
        ok = r["apply_ok"] and r["after"] == "on" and (not t.reversible or (
            r.get("undo_ok") and r.get("final") == r["before"] and r.get("reg_restored")))
        r["result"] = "ok" if ok else "FAIL"
        r["secs"] = round(time.time() - t0, 1)
        print("TW " + json.dumps(r, ensure_ascii=False), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    tempfile.gettempdir()
    main()
