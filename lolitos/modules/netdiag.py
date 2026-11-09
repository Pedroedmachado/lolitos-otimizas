"""Ping ICMP (IcmpSendEcho), perda de pacotes, jitter e análise de rota salto a salto."""
from __future__ import annotations

import ctypes
import socket
import statistics
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from lolitos.core.system import IS_WIN, run

IP_SUCCESS = 0
IP_TTL_EXPIRED_TRANSIT = 11013


class IP_OPTION_INFORMATION(ctypes.Structure):
    _fields_ = [("Ttl", ctypes.c_ubyte), ("Tos", ctypes.c_ubyte), ("Flags", ctypes.c_ubyte),
                ("OptionsSize", ctypes.c_ubyte), ("OptionsData", ctypes.c_void_p)]


class ICMP_ECHO_REPLY(ctypes.Structure):
    _fields_ = [("Address", ctypes.c_uint32), ("Status", ctypes.c_uint32), ("RoundTripTime", ctypes.c_uint32),
                ("DataSize", ctypes.c_uint16), ("Reserved", ctypes.c_uint16), ("Data", ctypes.c_void_p),
                ("Options", IP_OPTION_INFORMATION)]


_local = threading.local()


def _handle():
    h = getattr(_local, "h", None)
    if h is None:
        icmp = ctypes.windll.iphlpapi
        icmp.IcmpCreateFile.restype = ctypes.c_void_p
        h = icmp.IcmpCreateFile()
        _local.h = h
    return h


def resolve(host: str) -> str:
    return socket.gethostbyname(host)


def ping_once(ip: str, timeout_ms: int = 1000, ttl: int = 128, size: int = 32) -> tuple[int, float | None, str]:
    """Retorna (status, rtt_ms|None, ip_que_respondeu). Usa IcmpSendEcho (sem precisar de admin)."""
    if not IS_WIN:
        return -1, None, ""
    icmp = ctypes.windll.iphlpapi
    icmp.IcmpSendEcho.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint16,
                                  ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    dest = struct.unpack("<I", socket.inet_aton(ip))[0]
    data = ctypes.create_string_buffer(b"lolitos-ping-" + b"x" * max(0, size - 13), size)
    opts = IP_OPTION_INFORMATION(Ttl=ttl)
    buf_size = ctypes.sizeof(ICMP_ECHO_REPLY) + size + 8 + 64
    reply = ctypes.create_string_buffer(buf_size)
    t0 = time.perf_counter()
    n = icmp.IcmpSendEcho(_handle(), dest, data, size, ctypes.byref(opts), reply, buf_size, timeout_ms)
    elapsed = (time.perf_counter() - t0) * 1000
    if n == 0:
        return 11010, None, ""   # IP_REQ_TIMED_OUT
    r = ICMP_ECHO_REPLY.from_buffer_copy(reply)
    who = socket.inet_ntoa(struct.pack("<I", r.Address))
    rtt = float(r.RoundTripTime) if r.RoundTripTime else min(elapsed, 0.9)
    return r.Status, rtt, who


@dataclass
class LossResult:
    target: str
    ip: str
    sent: int = 0
    lost: int = 0
    late: int = 0
    rtts: list[float] = field(default_factory=list)
    timeline: list[str] = field(default_factory=list)  # 'ok' | 'late' | 'lost'

    @property
    def loss_pct(self) -> float:
        return 100 * self.lost / self.sent if self.sent else 0.0

    @property
    def avg(self) -> float:
        return statistics.mean(self.rtts) if self.rtts else 0.0

    @property
    def jitter(self) -> float:
        if len(self.rtts) < 2:
            return 0.0
        return statistics.mean(abs(a - b) for a, b in zip(self.rtts, self.rtts[1:]))

    def verdict(self) -> tuple[str, str]:
        if self.sent == 0:
            return "?", "Nada medido."
        if self.lost == self.sent:
            return "ruim", "Nenhuma resposta: o destino ignora ping ou a conexão caiu. Compare com 1.1.1.1."
        if self.loss_pct == 0 and self.late == 0 and self.jitter < 5:
            return "otimo", "Excelente: nenhum pacote perdido e latência estável. Ideal para Guerra de Nodes."
        if self.loss_pct < 1 and self.jitter < 10:
            return "bom", "Boa: perda e variação mínimas, imperceptíveis na maioria das lutas."
        if self.loss_pct < 3:
            return "atencao", "Atenção: alguma perda. No PvP você pode sentir 'teleporte' e skills atrasadas."
        return "ruim", "Ruim: perda alta. Use 'Analisar rota' para ver onde está o problema."


def packet_loss(target: str, seconds: int = 30, rate: int = 20, late_ms: int = 150,
                on_tick=None, stop: threading.Event | None = None) -> LossResult:
    """Envia `rate` pings/s por `seconds` s (ritmo parecido com o de um jogo)."""
    ip = resolve(target)
    res = LossResult(target, ip)
    interval = 1.0 / rate
    end = time.perf_counter() + seconds
    nxt = time.perf_counter()
    while time.perf_counter() < end:
        if stop and stop.is_set():
            break
        status, rtt, _ = ping_once(ip, timeout_ms=1000)
        res.sent += 1
        if status != IP_SUCCESS or rtt is None:
            res.lost += 1
            res.timeline.append("lost")
        else:
            res.rtts.append(rtt)
            if rtt > late_ms:
                res.late += 1
                res.timeline.append("late")
            else:
                res.timeline.append("ok")
        if on_tick and res.sent % rate == 0:
            on_tick(res)
        nxt += interval
        delay = nxt - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            nxt = time.perf_counter()
    return res


@dataclass
class Hop:
    n: int
    ip: str
    name: str = ""
    sent: int = 0
    lost: int = 0
    rtts: list[float] = field(default_factory=list)

    @property
    def loss_pct(self):
        return 100 * self.lost / self.sent if self.sent else 0.0

    @property
    def avg(self):
        return statistics.mean(self.rtts) if self.rtts else 0.0


def discover_route(ip: str, max_hops: int = 30) -> list[Hop]:
    hops = []
    for ttl in range(1, max_hops + 1):
        who = ""
        for _ in range(3):
            status, _, who = ping_once(ip, timeout_ms=800, ttl=ttl)
            if who and who != "0.0.0.0":
                break
        hops.append(Hop(ttl, who or "*"))
        if who == ip:
            break
    return hops


def analyze_route(target: str, seconds: int = 30, on_progress=None) -> tuple[str, list[Hop], str]:
    ip = resolve(target)
    hops = discover_route(ip)
    live = [h for h in hops if h.ip != "*"]
    end = time.time() + seconds

    def probe(h: Hop):
        while time.time() < end:
            st, rtt, _ = ping_once(h.ip, timeout_ms=1000)
            h.sent += 1
            if st != IP_SUCCESS or rtt is None:
                h.lost += 1
            else:
                h.rtts.append(rtt)
            time.sleep(0.5)

    with ThreadPoolExecutor(max_workers=max(1, len(live))) as ex:
        futs = [ex.submit(probe, h) for h in live]
        while any(not f.done() for f in futs):
            if on_progress:
                on_progress(min(100, 100 - (end - time.time()) / seconds * 100))
            time.sleep(0.5)
    for h in live:
        try:
            h.name = socket.gethostbyaddr(h.ip)[0]
        except OSError:
            h.name = ""
    return ip, hops, _diagnose(hops, ip)


def _diagnose(hops: list[Hop], ip: str) -> str:
    live = [h for h in hops if h.ip != "*" and h.sent]
    if not live:
        return "Nenhum salto respondeu."
    dest = live[-1] if live[-1].ip == ip else None
    if dest and dest.loss_pct < 1:
        if any(h.loss_pct > 5 for h in live[:-1]):
            return ("Sem perda real: o destino recebeu tudo. Saltos do meio com perda só estão ignorando ping "
                    "(roteadores respondem com baixa prioridade) — normal.")
        return "Sem perda em toda a rota. A conexão está limpa."
    # primeiro salto a partir do qual a perda persiste até o fim
    start = None
    for i, h in enumerate(live):
        if h.loss_pct >= 2 and all(x.loss_pct >= 2 for x in live[i:]):
            start = i
            break
    if start is None:
        return "Perda irregular ao longo da rota; repita o teste com cabo e com o PC parado."
    h = live[start]
    where = ("na sua rede local (Wi-Fi, cabo ou roteador)" if start == 0 else
             "logo na saída para a operadora" if start <= 2 else "na rede da operadora ou mais adiante")
    return f"A perda começa no salto {h.n} ({h.ip}) e segue até o destino: o problema está {where}."


def default_gateway() -> str | None:
    r = run(["powershell.exe", "-NoProfile", "-Command",
             "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).NextHop"])
    ip = r.out.strip()
    return ip if ip and ip != "0.0.0.0" else None
