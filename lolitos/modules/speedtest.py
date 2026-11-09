"""Teste de velocidade usando os servidores públicos da Cloudflare (speed.cloudflare.com)."""
from __future__ import annotations

import os
import statistics
import threading
import time
import urllib.request

BASE = "https://speed.cloudflare.com"
UA = {"User-Agent": "ChineseControl/1.0"}


def _get(url: str, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout)


def latency(n: int = 12) -> tuple[float, float, str]:
    """(ping médio ms, jitter ms, colo/cidade)."""
    rtts, colo = [], ""
    for _ in range(n):
        t = time.perf_counter()
        with _get(f"{BASE}/__down?bytes=0") as r:
            r.read()
            ray = r.headers.get("cf-ray", "")
            colo = ray.split("-")[-1] if "-" in ray else colo
        rtts.append((time.perf_counter() - t) * 1000)
    rtts = sorted(rtts)[: max(3, n - 2)]  # descarta os piores (handshake)
    jitter = statistics.mean(abs(a - b) for a, b in zip(rtts, rtts[1:])) if len(rtts) > 1 else 0
    return statistics.median(rtts), jitter, colo


def download(seconds: float = 10, threads: int = 4, on_tick=None) -> float:
    """Mbps."""
    total = [0]
    stop = time.perf_counter() + seconds
    lock = threading.Lock()

    def worker():
        while time.perf_counter() < stop:
            try:
                with _get(f"{BASE}/__down?bytes=25000000", timeout=20) as r:
                    while time.perf_counter() < stop:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        with lock:
                            total[0] += len(chunk)
            except OSError:
                time.sleep(0.2)

    t0 = time.perf_counter()
    ths = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    for t in ths:
        t.start()
    while any(t.is_alive() for t in ths):
        time.sleep(0.5)
        if on_tick:
            on_tick(total[0] * 8 / 1e6 / max(0.1, time.perf_counter() - t0))
    return total[0] * 8 / 1e6 / (time.perf_counter() - t0)


def upload(seconds: float = 8, threads: int = 3, on_tick=None) -> float:
    total = [0]
    stop = time.perf_counter() + seconds
    lock = threading.Lock()
    payload = os.urandom(2_000_000)

    def worker():
        while time.perf_counter() < stop:
            try:
                req = urllib.request.Request(f"{BASE}/__up", data=payload, method="POST",
                                             headers={**UA, "Content-Type": "application/octet-stream"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    r.read()
                with lock:
                    total[0] += len(payload)
            except OSError:
                time.sleep(0.2)

    t0 = time.perf_counter()
    ths = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    for t in ths:
        t.start()
    while any(t.is_alive() for t in ths):
        time.sleep(0.5)
        if on_tick:
            on_tick(total[0] * 8 / 1e6 / max(0.1, time.perf_counter() - t0))
    return total[0] * 8 / 1e6 / (time.perf_counter() - t0)


def loaded_latency(seconds: float = 6) -> float:
    """Ping medido enquanto a linha está cheia (bufferbloat)."""
    stop = threading.Event()
    th = threading.Thread(target=lambda: download(seconds, threads=4), daemon=True)
    th.start()
    time.sleep(1.0)
    rtts = []
    while th.is_alive():
        t = time.perf_counter()
        try:
            with _get(f"{BASE}/__down?bytes=0", timeout=5) as r:
                r.read()
            rtts.append((time.perf_counter() - t) * 1000)
        except OSError:
            pass
        time.sleep(0.3)
    stop.set()
    return statistics.median(rtts) if rtts else 0.0


def full_test(on_stage=None) -> dict:
    say = on_stage or (lambda *a: None)
    say("ping", 0)
    ping, jitter, colo = latency()
    say("download", 0)
    down = download(on_tick=lambda v: say("download", v))
    say("upload", 0)
    up = upload(on_tick=lambda v: say("upload", v))
    say("loaded", 0)
    loaded = loaded_latency()
    res = {"ping": ping, "jitter": jitter, "down": down, "up": up, "loaded": loaded, "colo": colo,
           "time": time.time()}
    res["bufferbloat"] = max(0.0, loaded - ping)
    return res
