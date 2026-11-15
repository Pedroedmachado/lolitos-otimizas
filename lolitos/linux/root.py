"""Fala com o ajudante root (helper.py). A senha é pedida uma vez por sessão, pelo pkexec."""
from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from lolitos.core.actions import ActionError

_proc: subprocess.Popen | None = None
_lock = threading.Lock()
NO_AGENT = ("Não consegui pedir a senha de administrador. O pkexec precisa de um agente polkit rodando na "
            "sessão (no Niri, por exemplo, o polkit-gnome ou o polkit-kde-agent). Se você cancelou o pedido, "
            "é só tentar de novo.")


def fake_root() -> str | None:
    return os.environ.get("CC_FAKE_ROOT")


def P(path: str) -> str:
    """Caminho de leitura (nos testes, dentro da raiz falsa)."""
    return (fake_root() or "") + path


def _start() -> subprocess.Popen:
    if not shutil.which("pkexec"):
        raise ActionError("pkexec não encontrado. Instale o pacote polkit.")
    helper = str(Path(__file__).with_name("helper.py"))
    p = subprocess.Popen(["pkexec", sys.executable, helper], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, bufsize=1)
    p.stdin.write('{"op": "ping"}\n')
    p.stdin.flush()
    if not p.stdout.readline():
        raise ActionError(NO_AGENT)
    return p


def _stop():
    global _proc
    if _proc and _proc.poll() is None:
        try:
            _proc.stdin.write('{"op": "quit"}\n')
            _proc.stdin.flush()
            _proc.wait(3)
        except Exception:  # noqa: BLE001
            _proc.kill()
    _proc = None


atexit.register(_stop)


def call(op: str, **kw) -> str:
    global _proc
    req = {"op": op, **kw}
    if fake_root() is not None or os.geteuid() == 0:
        from lolitos.linux import helper
        helper.PREFIX = fake_root() or ""
        r = helper.handle(req)
    else:
        with _lock:
            try:
                if _proc is None or _proc.poll() is not None:
                    _proc = _start()
                _proc.stdin.write(json.dumps(req) + "\n")
                _proc.stdin.flush()
                line = _proc.stdout.readline()
            except (OSError, ValueError) as e:
                _proc = None
                raise ActionError(f"ajudante root: {e}") from e
            if not line:
                _proc = None
                raise ActionError(NO_AGENT)
            r = json.loads(line)
    if not r.get("ok"):
        raise ActionError(str(r.get("out")))
    return str(r.get("out", ""))
