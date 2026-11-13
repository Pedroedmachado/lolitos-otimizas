"""Medição de antes e depois: grava os quadros do jogo por alguns minutos (PresentMon, o mesmo do overlay),
resume em números (FPS médio, 1% low, 0,1% low, frametime, travadas) e compara duas medições.

Nada é lido de dentro do jogo: são os eventos de apresentação de quadros que o próprio Windows publica."""
from __future__ import annotations

import json
import statistics
import threading
import time
import uuid
from collections import defaultdict

from lolitos.core.system import data_dir, write_atomic

MIN_SECONDS = 20          # menos que isso não dá para confiar
MIN_FRAMES = 300
NOISE_PCT = 3.0           # diferença menor que isso é variação normal entre duas partidas
MAX_KEPT = 60
DURATIONS = [(60, "1 minuto"), (120, "2 minutos"), (180, "3 minutos"), (300, "5 minutos")]


def summarize(ms: list[float]) -> dict | None:
    """Tempos de quadro (ms) → números da medição. None se for pouco para confiar."""
    n = len(ms)
    secs = sum(ms) / 1000.0
    if n < MIN_FRAMES or secs < MIN_SECONDS:
        return None
    worst = sorted(ms, reverse=True)
    med = statistics.median(ms)

    def low(frac: float) -> float:
        k = max(1, int(n * frac))
        return 1000.0 / (sum(worst[:k]) / k)
    limit = max(med * 2.5, 20.0)             # travada: quadro bem mais longo que o normal E perceptível
    stut = sum(1 for m in worst if m > limit)
    return {"frames": n, "secs": round(secs, 1), "fps": round(n / secs, 1), "low1": round(low(0.01), 1),
            "low01": round(low(0.001), 1), "frame_ms": round(med, 2),
            "p99_ms": round(worst[max(0, int(n * 0.01) - 1)], 2),
            "stutters": stut, "stutters_min": round(stut / (secs / 60.0), 1)}


class Recorder:
    """Recebe os quadros do leitor de FPS (FpsReader.taps) e amostras de uso do PC (sample(), 1 vez por segundo)."""

    def __init__(self):
        self.frames: dict[int, list[float]] = defaultdict(list)
        self.names: dict[int, str] = {}
        self.samples: list[dict] = []
        self.t0 = time.time()
        self._lock = threading.Lock()

    def tap(self, pid: int, name: str, _t: float, ms: float) -> None:
        with self._lock:
            self.frames[pid].append(ms)
            self.names[pid] = name

    def sample(self) -> None:
        import psutil

        from lolitos.modules import gpu
        s = {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent}
        try:
            g = gpu.read() if gpu.available() else {}
        except Exception:  # noqa: BLE001
            g = {}
        s["gpu"], s["gpu_c"] = g.get("util"), g.get("temp")
        self.samples.append(s)

    def game(self) -> tuple[int | None, str]:
        """O processo que mais desenhou (em tempo de quadro somado), fora o que não é jogo."""
        from lolitos.modules.fps import IGNORE
        with self._lock:
            tot = {pid: sum(v) for pid, v in self.frames.items()
                   if self.names.get(pid, "").lower() not in IGNORE and len(v) >= 3}
            if not tot:
                return None, ""
            pid = max(tot, key=tot.get)
            return pid, self.names.get(pid, "")

    def live(self) -> tuple[float | None, str, int]:
        """(FPS dos últimos ~2 s, nome do jogo, quadros gravados) para mostrar durante a gravação."""
        pid, name = self.game()
        if pid is None:
            return None, "", 0
        with self._lock:
            v = self.frames[pid]
            tail, acc = [], 0.0
            for m in reversed(v):
                tail.append(m)
                acc += m
                if acc >= 2000:
                    break
            n = len(v)
        return (1000.0 / statistics.mean(tail) if len(tail) >= 3 else None), name, n

    def result(self, label: str) -> dict | None:
        pid, name = self.game()
        if pid is None:
            return None
        with self._lock:
            ms = list(self.frames[pid])
        r = summarize(ms)
        if r is None:
            return None

        def avg(key):
            v = [s[key] for s in self.samples if s.get(key) is not None]
            return round(sum(v) / len(v), 1) if v else None

        def top(key):
            v = [s[key] for s in self.samples if s.get(key) is not None]
            return round(max(v), 1) if v else None
        r.update(id=uuid.uuid4().hex[:12], time=time.time(), label=label.strip()[:40] or "Medição", game=name,
                 cpu=avg("cpu"), gpu=avg("gpu"), ram=avg("ram"), gpu_c_max=top("gpu_c"), tweaks=active_tweaks())
        return r


def active_tweaks() -> list[str]:
    """Ajustes que o app aplicou e ainda estão valendo (para dizer o que mudou entre duas medições)."""
    try:
        from lolitos.core import history
        return sorted({e["tweak_id"] for e in history.active_entries() if e.get("tweak_id")})
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------- arquivo
def _file():
    return data_dir() / "medicoes.json"


def load() -> list[dict]:
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [x for x in d if isinstance(x, dict) and x.get("id") and "fps" in x] if isinstance(d, list) else []


def save(r: dict) -> None:
    items = load()
    items.append(r)
    write_atomic(_file(), json.dumps(items[-MAX_KEPT:], ensure_ascii=False, indent=1))


def delete(rid: str) -> None:
    write_atomic(_file(), json.dumps([x for x in load() if x["id"] != rid], ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- comparação
# (campo, título, maior é melhor?, unidade)
METRICS = [("fps", "FPS médio", True, ""), ("low1", "1% low", True, ""), ("low01", "0,1% low", True, ""),
           ("frame_ms", "Tempo de quadro típico", False, " ms"), ("p99_ms", "Tempo de quadro (99%)", False, " ms"),
           ("stutters_min", "Travadas por minuto", False, "")]


def compare(a: dict, b: dict) -> dict:
    """a = antes, b = depois. Devolve as linhas da tabela, o veredito e os avisos."""
    rows = []
    for key, title, higher, unit in METRICS:
        va, vb = a.get(key), b.get(key)
        if va is None or vb is None:
            continue
        if key == "stutters_min":           # contagem pequena: porcentagem engana (0,2 → 0,4 = "+100%")
            diff = vb - va
            verdict = 0 if abs(diff) < 1.0 else (1 if diff < 0 else -1)
            pct = None
        else:
            pct = (vb - va) / va * 100.0 if va else 0.0
            verdict = 0 if abs(pct) < NOISE_PCT else (1 if (pct > 0) == higher else -1)
        rows.append({"key": key, "title": title, "a": va, "b": vb, "pct": pct, "unit": unit, "verdict": verdict})
    by = {r["key"]: r["verdict"] for r in rows}
    main = [by.get("fps", 0), by.get("low1", 0)]
    if all(v == 0 for v in main):
        overall = "igual"
    elif all(v >= 0 for v in main):
        overall = "melhor"
    elif all(v <= 0 for v in main):
        overall = "pior"
    else:
        overall = "misto"
    warns = []
    if (a.get("game") or "").lower() != (b.get("game") or "").lower():
        warns.append("jogo")
    sa, sb = a.get("secs") or 0, b.get("secs") or 0
    if min(sa, sb) and max(sa, sb) / min(sa, sb) > 1.5:
        warns.append("duracao")
    ta, tb = set(a.get("tweaks") or []), set(b.get("tweaks") or [])
    return {"rows": rows, "overall": overall, "warns": warns, "added": sorted(tb - ta), "removed": sorted(ta - tb)}
