"""Configuração do MangoHud (~/.config/MangoHud/MangoHud.conf). O arquivo antigo é guardado antes da primeira
gravação feita pelo app."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# (chave do MangoHud, texto, ligado por padrão)
ITEMS = [("fps", "FPS", True), ("frametime", "Tempo de quadro (ms)", True), ("frame_timing", "Gráfico de tempo de quadro", True),
         ("cpu_stats", "Uso do processador", True), ("cpu_temp", "Temperatura do processador", True),
         ("gpu_stats", "Uso da placa de vídeo", True), ("gpu_temp", "Temperatura da placa de vídeo", True),
         ("vram", "Memória de vídeo", True), ("ram", "Memória RAM", False),
         ("gamemode", "Mostrar se o GameMode está ativo", False), ("time", "Relógio", False)]
POSITIONS = [("top-left", "Canto superior esquerdo"), ("top-right", "Canto superior direito"),
             ("bottom-left", "Canto inferior esquerdo"), ("bottom-right", "Canto inferior direito")]
MARK = "# Gerado pelo Chinese Control"


def path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "MangoHud" / "MangoHud.conf"


def installed() -> bool:
    return bool(shutil.which("mangohud"))


def render(items, position: str = "top-left", fps_limit: int = 0, font_size: int = 22, alpha: float = 0.4,
           compact: bool = False) -> str:
    valid = {k for k, _t, _d in ITEMS}
    pos = position if position in {p for p, _ in POSITIONS} else "top-left"
    lines = [MARK]
    lines += [k for k, _t, _d in ITEMS if k in items and k in valid]
    lines += [f"position={pos}", f"font_size={max(12, min(48, int(font_size)))}",
              f"background_alpha={max(0.0, min(1.0, float(alpha))):.2f}", "toggle_hud=Shift_R+F12"]
    if compact:
        lines.append("hud_compact")
    if int(fps_limit) > 0:
        lines.append(f"fps_limit={int(fps_limit)}")
    return "\n".join(lines) + "\n"


def read() -> dict:
    """Configuração atual, no formato das opções da tela."""
    out = {"items": {k for k, _t, d in ITEMS if d}, "position": "top-left", "fps_limit": 0, "font_size": 22,
           "alpha": 0.4, "compact": False, "exists": False, "ours": False}
    try:
        text = path().read_text()
    except OSError:
        return out
    out.update(exists=True, ours=text.startswith(MARK), items=set())
    valid = {k for k, _t, _d in ITEMS}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        k, _, v = ln.partition("=")
        k, v = k.strip(), v.strip()
        try:
            if k in valid and v in ("", "1"):
                out["items"].add(k)
            elif k == "position":
                out["position"] = v
            elif k == "fps_limit":
                out["fps_limit"] = int(v.split(",")[0] or 0)
            elif k == "font_size":
                out["font_size"] = int(float(v))
            elif k == "background_alpha":
                out["alpha"] = float(v)
            elif k == "hud_compact":
                out["compact"] = True
        except ValueError:
            pass
    return out


def write(text: str) -> Path:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not p.read_text().startswith(MARK):
        bak = p.with_name("MangoHud.conf.antes-do-chinese-control")
        if not bak.exists():
            shutil.copy2(p, bak)
    p.write_text(text)
    return p
