"""Servidor de qualquer jogo: descobre as conexões do processo (tabela do Windows) e mede a latência
por handshake TCP — funciona mesmo quando o servidor ignora ping. Nada é lido do jogo."""
from __future__ import annotations

import re
import socket
import statistics
import time
from dataclasses import dataclass


@dataclass
class Conn:
    ip: str
    port: int
    proto: str = "tcp"


def find_process(exes: list[str]):
    try:
        import psutil
        wanted = {e.lower() for e in exes}
        for p in psutil.process_iter(["name"]):
            if (p.info["name"] or "").lower() in wanted:
                return p
    except Exception:
        pass
    return None


def _private(ip: str) -> bool:
    return ip.startswith(("10.", "192.168.", "127.", "169.254.", "0.")) or ":" in ip or \
        re.match(r"^172\.(1[6-9]|2\d|3[01])\.", ip) is not None


def connections(exes: list[str]) -> tuple[list[Conn], bool]:
    """(conexões TCP com a internet, tem_udp). UDP não tem endereço remoto na tabela do Windows."""
    p = find_process(exes)
    if not p:
        return [], False
    try:
        conns = p.net_connections(kind="inet") if hasattr(p, "net_connections") else p.connections(kind="inet")
    except Exception:
        return [], False
    out, seen, udp = [], set(), False
    for c in conns:
        if c.type == socket.SOCK_DGRAM:
            udp = True
            continue
        if not c.raddr or c.status != "ESTABLISHED":
            continue
        ip, port = c.raddr.ip, c.raddr.port
        if _private(ip) or (ip, port) in seen:
            continue
        seen.add((ip, port))
        out.append(Conn(ip, port))
    out.sort(key=lambda c: c.port in (80, 443))   # web (loja, launcher) por último
    return out, udp


def tcp_ping(ip: str, port: int, timeout: float = 2.0) -> float | None:
    t = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return (time.perf_counter() - t) * 1000
    except OSError:
        return None


def measure(ip: str, port: int, n: int = 60, interval: float = 0.5, progress=None) -> dict:
    rtts, lost = [], 0
    for i in range(n):
        v = tcp_ping(ip, port)
        if v is None:
            lost += 1
        else:
            rtts.append(v)
        if progress and i % 5 == 4:
            progress(f"{i + 1}/{n}")
        time.sleep(interval)
    if not rtts:
        return {"ok": False, "lost": lost, "n": n}
    jit = statistics.mean(abs(a - b) for a, b in zip(rtts, rtts[1:])) if len(rtts) > 1 else 0.0
    return {"ok": True, "avg": statistics.mean(rtts), "min": min(rtts), "max": max(rtts), "jitter": jit,
            "lost": lost, "n": n}


def verdict(r: dict) -> tuple[str, str]:
    if not r.get("ok"):
        return "ruim", "O servidor não respondeu ao teste."
    if r["avg"] < 40 and r["jitter"] < 5 and r["lost"] == 0:
        return "otimo", "Excelente para jogo competitivo."
    if r["avg"] < 80 and r["jitter"] < 10:
        return "bom", "Bom."
    return "ruim", "Alto — teste com cabo e veja Rede › Analisar rota com este IP."
