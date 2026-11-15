#!/usr/bin/env python3
"""Ajudante com privilégio de root. É aberto UMA vez por sessão com pkexec e fica lendo pedidos (uma linha JSON
por pedido) pela entrada padrão. Só aceita as operações e os caminhos listados aqui: nada de comando livre.

Só usa a biblioteca padrão, para rodar com o python do sistema."""
import glob
import json
import os
import re
import subprocess
import sys

PREFIX = ""          # só nos testes: raiz falsa (o cliente preenche; o processo root real nunca usa)

CONF_RX = re.compile(r"^/etc/(sysctl\.d|tmpfiles\.d|modules-load\.d)/(99-)?chinese-control-[a-z0-9_]+\.conf$")
SYSCTL_RX = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
VALUE_RX = re.compile(r"^[A-Za-z0-9_\- ]{1,64}$")
SYSFS_RX = [re.compile(x) for x in (
    r"^/sys/devices/system/cpu/cpu(\*|\d+)/cpufreq/(scaling_governor|energy_performance_preference)$",
    r"^/sys/kernel/mm/transparent_hugepage/(enabled|shmem_enabled|defrag)$",
    r"^/sys/block/nvme(\*|[a-z0-9]+)/queue/scheduler$",
)]
MODULES = {"tcp_bbr"}
PACKAGES = {"gamemode", "lib32-gamemode", "mangohud", "lib32-mangohud"}


def _conf(path):
    if not isinstance(path, str) or not CONF_RX.match(path) or ".." in path:
        raise ValueError("caminho não permitido: %r" % (path,))
    return PREFIX + path


def handle(req):
    try:
        return {"ok": True, "out": _do(req) or ""}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "out": "%s: %s" % (type(e).__name__, e)}


def _do(req):
    op = req.get("op")
    if op == "ping":
        return "pong"
    if op == "write_file":
        content = req.get("content", "")
        if not isinstance(content, str) or len(content) > 4096:
            raise ValueError("conteúdo inválido")
        p = _conf(req.get("path"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp, 0o644)
        os.replace(tmp, p)
        return ""
    if op == "remove_file":
        p = _conf(req.get("path"))
        if os.path.exists(p):
            os.remove(p)
        return ""
    if op == "sysctl":
        key, value = str(req.get("key", "")), str(req.get("value", ""))
        if not SYSCTL_RX.match(key) or not VALUE_RX.match(value):
            raise ValueError("sysctl inválido")
        with open(PREFIX + "/proc/sys/" + key.replace(".", "/"), "w") as f:
            f.write(value + "\n")
        return ""
    if op == "sysfs":
        pat, value = str(req.get("path", "")), str(req.get("value", ""))
        if not any(rx.match(pat) for rx in SYSFS_RX) or not VALUE_RX.match(value):
            raise ValueError("sysfs não permitido: %r" % (pat,))
        errs, n = [], 0
        for p in sorted(glob.glob(PREFIX + pat)):
            try:
                with open(p, "w") as f:
                    f.write(value)
                n += 1
            except OSError as e:
                errs.append("%s: %s" % (p, e.strerror))
        if errs and not n:
            raise OSError("; ".join(errs[:3]))
        return "%d arquivo(s)" % n
    if op == "modprobe":
        name = req.get("name")
        if name not in MODULES:
            raise ValueError("módulo não permitido")
        if not PREFIX:
            subprocess.run(["/usr/bin/modprobe", name], check=True, capture_output=True, timeout=30)
        return ""
    if op == "pacman":
        pkgs = req.get("pkgs") or []
        if not pkgs or any(p not in PACKAGES for p in pkgs):
            raise ValueError("pacote não permitido")
        if PREFIX:
            with open(PREFIX + "/pacman.log", "a") as f:
                f.write(" ".join(pkgs) + "\n")
            return ""
        r = subprocess.run(["/usr/bin/pacman", "-S", "--needed", "--noconfirm", *pkgs],
                           capture_output=True, text=True, timeout=900)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip()[-600:])
        return r.stdout[-600:]
    raise ValueError("operação desconhecida: %r" % (op,))


def main():
    if os.geteuid() != 0:
        print(json.dumps({"ok": False, "out": "o ajudante precisa de root"}), flush=True)
        return 1
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if not isinstance(req, dict):
                raise ValueError("pedido inválido")
        except ValueError as e:
            print(json.dumps({"ok": False, "out": str(e)}), flush=True)
            continue
        if req.get("op") == "quit":
            break
        print(json.dumps(handle(req)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
