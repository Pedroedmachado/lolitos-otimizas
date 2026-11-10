"""Desenho da placa-mãe do Meu PC: processador, memórias, placa de vídeo, discos e chipset nos lugares de uma
placa ATX. Passe o mouse em cada peça para ver os detalhes."""
from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from lolitos.core.system import human_size
from lolitos.i18n import tr
from lolitos.ui.theme import C

W, H = 760, 520          # sistema de coordenadas do desenho (escala para o tamanho do widget)


@dataclass
class Part:
    key: str
    rect: QRectF
    title: str
    lines: list[str]
    filled: bool = True


def _short_cpu(name: str) -> str:
    n = " ".join((name or "").replace("(R)", "").replace("(TM)", "").replace("CPU", "").split())
    for cut in (" with ", " w/ ", " @ "):
        if cut in n:
            n = n.split(cut)[0]
    n = re.sub(r"\s*\d+-Core Processor", "", n)
    return n.replace(" Processor", "").strip()


def _short_gpu(name: str) -> str:
    n = (name or "").replace("NVIDIA ", "").replace("AMD ", "").replace("(TM)", "").replace("(R)", "")
    return " ".join(n.split())


def build_parts(d: dict, rs: dict | None) -> list[Part]:
    """Monta as peças a partir do que o Windows informa (hwinfo.read_all + ram_summary)."""
    parts: list[Part] = []
    cpu = (d.get("cpu") or [{}])[0]
    cname = _short_cpu(cpu.get("Name", "")) or tr("Processador")
    parts.append(Part("cpu", QRectF(250, 95, 150, 150), cname, [
        f"{cpu.get('NumberOfCores', '?')} {tr('núcleos')} / {cpu.get('NumberOfLogicalProcessors', '?')} threads",
        f"{tr('Clock base')}: {cpu.get('MaxClockSpeed', '?')} MHz",
        f"{tr('Cache L3')}: {(cpu.get('L3CacheSize') or 0) // 1024} MB",
        f"{tr('Soquete')}: {cpu.get('SocketDesignation') or '—'}"]))

    # memórias: 4 encaixes (ou o que a placa informar, até 8)
    sticks = (rs or {}).get("sticks") or d.get("ram") or []
    slots = int((rs or {}).get("slots") or d.get("slots") or 0) or max(4 if len(sticks) > 2 else 4, len(sticks))
    slots = max(2, min(8, slots))
    by_loc = sorted(sticks, key=lambda s: str(s.get("DeviceLocator") or s.get("BankLabel") or ""))
    filled_idx = _fill_order(slots, len(by_loc))
    x0, sw, gap = 440, 18, 12
    for i in range(slots):
        r = QRectF(x0 + i * (sw + gap), 60, sw, 230)
        if i in filled_idx:
            s = by_loc[filled_idx.index(i)]
            size = human_size(int(s.get("Capacity") or 0))
            sp = s.get("ConfiguredClockSpeed") or s.get("Speed") or "?"
            parts.append(Part(f"ram{i}", r, f"{tr('Memória')} {size}", [
                f"{(s.get('Manufacturer') or '').strip()} {(s.get('PartNumber') or '').strip()}".strip() or "—",
                f"{sp} MT/s · {(rs or {}).get('kind') or ''}".strip(" ·"),
                f"{tr('Encaixe')}: {s.get('DeviceLocator') or s.get('BankLabel') or i + 1}"]))
        else:
            parts.append(Part(f"ram{i}", r, tr("Encaixe vazio"), [tr("Sem pente de memória neste encaixe.")],
                              filled=False))

    # placa de vídeo dedicada (a primeira que não é integrada/virtual)
    gpus = [g for g in d.get("gpu", []) if g.get("Name")]
    ded = [g for g in gpus if not any(k in g["Name"] for k in ("Intel(R) UHD", "Intel(R) HD", "Iris", "Basic Display",
                                                                 "Microsoft", "Radeon(TM) Graphics", "Virtual"))]
    g = (ded or gpus or [{}])[0]
    if g:
        vram = int(g.get("AdapterRAM") or 0)
        res = (f"{g.get('CurrentHorizontalResolution')}×{g.get('CurrentVerticalResolution')} @ "
               f"{g.get('CurrentRefreshRate')} Hz" if g.get("CurrentHorizontalResolution") else "")
        lines = [f"{tr('Driver')}: {g.get('DriverVersion') or '—'}"]
        if vram > 0:
            lines.append(f"VRAM: {human_size(vram)}{'+' if vram >= 4 * 1024 ** 3 - 1 else ''}")
        if res:
            lines.append(f"{tr('Monitor')}: {res}")
        parts.append(Part("gpu", QRectF(95, 315, 470, 70), _short_gpu(g.get("Name", "")) or tr("Placa de vídeo"),
                          lines, filled=bool(ded)))

    # discos: M.2 (NVMe) na placa; SATA perto do chipset
    disks = d.get("disks", [])
    nv = [x for x in disks if str(x.get("BusType", "")).upper() in ("NVME", "17")]
    other = [x for x in disks if x not in nv]
    for i, x in enumerate(nv[:2]):
        parts.append(Part(f"m2{i}", QRectF(130 + i * 230, 410, 190, 26), _disk_name(x), _disk_lines(x)))
    for i, x in enumerate(other[:3]):
        parts.append(Part(f"sata{i}", QRectF(684, 300 + i * 52, 44, 40), _disk_name(x), _disk_lines(x)))

    board = d.get("board") or {}
    if isinstance(board, list):
        board = board[0] if board else {}
    bios = d.get("bios") or {}
    if isinstance(bios, list):
        bios = bios[0] if bios else {}
    parts.append(Part("chipset", QRectF(600, 420, 70, 60), tr("Chipset / placa-mãe"), [
        f"{(board.get('Manufacturer') or '').strip()} {(board.get('Product') or '').strip()}".strip() or "—",
        f"BIOS {bios.get('SMBIOSBIOSVersion') or '—'} ({bios.get('Date') or '—'})",
        f"Secure Boot: {_yn(d.get('secureboot'))} · TPM: {_yn((d.get('tpm') or {}).get('ready'))}"]))
    return parts


def _fill_order(slots: int, n: int) -> list[int]:
    """Em que encaixes ficam os pentes (2 pentes em 4 encaixes: o 2º e o 4º, como os manuais mandam)."""
    if slots == 4:
        order = {0: [], 1: [1], 2: [1, 3], 3: [0, 1, 3], 4: [0, 1, 2, 3]}
        return order.get(n, list(range(min(n, 4))))
    return list(range(min(n, slots)))


def _disk_name(x: dict) -> str:
    return (x.get("FriendlyName") or tr("Disco")).strip()


def _disk_lines(x: dict) -> list[str]:
    media = {"SSD": "SSD", "HDD": "HD", "4": "SSD", "3": "HD"}.get(str(x.get("MediaType")), str(x.get("MediaType") or ""))
    bus = str(x.get("BusType") or "")
    bus = {"17": "NVMe", "11": "SATA", "7": "USB"}.get(bus, bus)
    return [f"{human_size(int(x.get('Size') or 0))} · {media} · {bus}".strip(" ·"),
            f"{tr('Saúde')}: {x.get('HealthStatus') or '—'}"]


def _yn(v) -> str:
    return tr("sim") if v else (tr("não") if v is not None else "—")


class BoardView(QWidget):
    hovered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parts: list[Part] = []
        self.hot: str = ""
        self.setMouseTracking(True)
        self.setMinimumHeight(300)

    def set_data(self, d: dict, rs: dict | None):
        self.parts = build_parts(d, rs)
        self.update()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return int(w * H / W)

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(W, H)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        h = max(300, min(560, int(self.width() * H / W)))
        if self.minimumHeight() != h:
            self.setMinimumHeight(h)

    # ---------------------------------------------------------------- coordenadas
    def _scale(self):
        s = min(self.width() / W, self.height() / H)
        ox = (self.width() - W * s) / 2
        oy = (self.height() - H * s) / 2
        return s, ox, oy

    def _hit(self, pos) -> Part | None:
        s, ox, oy = self._scale()
        p = QPointF((pos.x() - ox) / s, (pos.y() - oy) / s)
        for part in reversed(self.parts):
            if part.rect.adjusted(-4, -4, 4, 4).contains(p):
                return part
        return None

    def mouseMoveEvent(self, e):
        part = self._hit(e.position())
        key = part.key if part else ""
        if key != self.hot:
            self.hot = key
            self.update()
        if part:
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"<b>{part.title}</b><br>" + "<br>".join(x for x in part.lines if x), self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, e):
        self.hot = ""
        self.update()

    # ---------------------------------------------------------------- desenho
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s, ox, oy = self._scale()
        p.translate(ox, oy)
        p.scale(s, s)
        acc, acc2 = QColor(C["accent"]), QColor(C["accent2"])
        dark = QColor(C["bg"]).lightness() < 128
        pcb = QColor("#0d1b2e" if dark else "#dfe8f3")
        # placa
        g = QLinearGradient(0, 0, W, H)
        g.setColorAt(0, pcb.lighter(115))
        g.setColorAt(1, pcb)
        p.setPen(QPen(QColor(C["border2"]), 2))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(20, 20, W - 40, H - 40), 18, 18)
        # trilhas
        trace = QColor(acc)
        trace.setAlpha(38)
        p.setPen(QPen(trace, 2))
        for i in range(9):
            y = 70 + i * 44
            p.drawLine(QPointF(40, y), QPointF(230, y))
            p.drawLine(QPointF(230, y), QPointF(250, y - 12))
        for i in range(6):
            x = 600 + i * 22
            p.drawLine(QPointF(x, 40), QPointF(x, 280))
        # painel traseiro (I/O) e VRM
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["panel2"]))
        p.drawRoundedRect(QRectF(34, 50, 70, 230), 6, 6)
        for i in range(6):
            p.setBrush(QColor(C["border2"]))
            p.drawRoundedRect(QRectF(46, 64 + i * 34, 46, 20), 3, 3)
        for i in range(5):
            p.setBrush(QColor(C["panel2"]).lighter(120))
            p.drawRoundedRect(QRectF(250 + i * 31, 52, 24, 28), 3, 3)
            p.drawRoundedRect(QRectF(205, 100 + i * 31, 28, 24), 3, 3)
        # bateria da BIOS
        p.setBrush(QColor("#9aa7b8"))
        p.drawEllipse(QPointF(520, 455), 16, 16)
        # slot PCIe (atrás da placa de vídeo) e slot secundário
        p.setBrush(QColor(C["border2"]))
        p.drawRoundedRect(QRectF(150, 340, 330, 12), 3, 3)
        p.drawRoundedRect(QRectF(150, 395, 200, 8), 3, 3)
        f = QFont("Segoe UI", 9)
        for part in self.parts:
            self._draw_part(p, part, acc, acc2, f)
        p.end()

    def _draw_part(self, p, part: Part, acc, acc2, f):
        hot = part.key == self.hot
        r = part.rect
        if hot:
            glow = QColor(acc2)
            glow.setAlpha(70)
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawRoundedRect(r.adjusted(-6, -6, 6, 6), 10, 10)
        pen = QPen(acc2 if hot else QColor(C["border2"]), 2 if hot else 1.2)
        if part.key == "cpu":
            p.setPen(pen)
            p.setBrush(QColor(C["panel2"]))
            p.drawRoundedRect(r, 8, 8)
            inner = r.adjusted(18, 18, -18, -18)
            gg = QLinearGradient(inner.topLeft(), inner.bottomRight())
            gg.setColorAt(0, QColor("#c9d3df"))
            gg.setColorAt(1, QColor("#8e9aab"))
            p.setBrush(gg)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(inner, 6, 6)
            self._text(p, inner.adjusted(6, 6, -6, -6), part.title, QColor("#0b1220"), 9, bold=True)
        elif part.key.startswith("ram"):
            p.setPen(pen)
            p.setBrush(QColor(C["panel2"]) if not part.filled else QColor(acc).darker(150))
            p.drawRoundedRect(r, 3, 3)
            if part.filled:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(acc2))
                for k in range(8):
                    p.drawRect(QRectF(r.x() + 4, r.y() + 12 + k * 26, r.width() - 8, 14))
        elif part.key == "gpu":
            p.setPen(pen)
            body = QColor("#1a2232") if part.filled else QColor(C["panel2"])
            p.setBrush(body)
            p.drawRoundedRect(r, 10, 10)
            p.setBrush(QColor("#2a3446"))
            p.setPen(Qt.NoPen)
            for k in range(2):
                c = QPointF(r.x() + 60 + k * 90, r.center().y())
                p.drawEllipse(c, 26, 26)
                p.setBrush(QColor("#3a465c"))
                p.drawEllipse(c, 8, 8)
                p.setBrush(QColor("#2a3446"))
            strip = QColor(acc2)
            p.setBrush(strip)
            p.drawRoundedRect(QRectF(r.x() + 12, r.y() + 6, r.width() - 24, 4), 2, 2)
            self._text(p, QRectF(r.right() - 230, r.y() + 14, 220, r.height() - 20), part.title,
                       QColor("#e8eef8"), 9, bold=True, align=Qt.AlignRight | Qt.AlignVCenter)
        elif part.key.startswith("m2"):
            p.setPen(pen)
            p.setBrush(QColor("#1d2a3c"))
            p.drawRoundedRect(r, 4, 4)
            p.setBrush(QColor(acc2))
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(r.x() + 6, r.y() + 8, 26, r.height() - 16))
            self._text(p, r.adjusted(38, 0, -4, 0), part.title, QColor("#dce6f3"), 7.5,
                       align=Qt.AlignLeft | Qt.AlignVCenter)
        elif part.key.startswith("sata"):
            p.setPen(pen)
            p.setBrush(QColor(C["panel2"]))
            p.drawRoundedRect(r, 4, 4)
            p.setBrush(QColor(acc2))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(r.x() + 8, r.y() + 8, r.width() - 16, 6), 2, 2)
        elif part.key == "chipset":
            p.setPen(pen)
            p.setBrush(QColor("#2a3446"))
            p.drawRoundedRect(r, 8, 8)
            path = QPainterPath()
            path.addRoundedRect(r.adjusted(14, 14, -14, -14), 4, 4)
            p.fillPath(path, QColor(acc).darker(130))

    @staticmethod
    def _text(p, rect, txt, col, size, bold=False, align=Qt.AlignCenter):
        f = QFont("Segoe UI", 1)
        f.setPointSizeF(size)
        f.setBold(bold)
        p.setFont(f)
        p.setPen(col)
        p.drawText(rect, align | Qt.TextWordWrap, txt)
