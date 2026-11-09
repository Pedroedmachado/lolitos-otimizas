"""Extrai os textos visíveis da interface (português) para lolitos/data/i18n/pt_keys.json.

Uso: python tools/extract_strings.py   — f-strings viram modelos com {} no lugar dos valores."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_CALLS = {"run", "powershell", "powershell_json", "Reg", "Service", "Task", "Cmd", "Power", "PowerPlan", "Appx",
              "Capability", "JsonKey", "Interfaces", "LayerFlag", "DefenderFolder", "getLogger", "info_log",
              "debug", "warning", "exception", "error", "compile", "match", "search", "sub", "fullmatch", "split",
              "startswith", "endswith", "replace", "strftime", "strptime", "joinpath", "Path", "get", "set",
              "setdefault", "setObjectName", "open", "environ", "getenv", "expandvars", "CreateMutexW",
              "_get", "urlopen", "Request", "loads", "dumps", "encode", "decode", "format_exc", "setStyleSheet",
              "QColor", "QFont", "lower", "upper", "strip", "lstrip", "rstrip", "index", "count", "find",
              "data_dir", "resource_path", "writerow", "ShellExecuteW", "Popen", "check_output", "OpenKey",
              "QueryValueEx", "SetValueEx", "CreateKey", "DeleteKey", "_hkey", "_read", "_write", "pop"}
PT = re.compile(r"[ãõáéíóúâêôçàÃÕÁÉÍÓÚÂÊÔÇ]|\b(de|do|da|para|com|não|você|seu|sua|os|as|um|uma|ou|em|no|na|que|"
                r"o|a|e)\b", re.I)


def literal(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(v.value.replace("{", "{{").replace("}", "}}"))
            else:
                out.append("{}")
        return "".join(out)
    return None


def visible(s: str) -> bool:
    t = re.sub(r"<[^>]+>|\{\}", " ", s).strip()
    if len(t) < 2 or not re.search(r"[A-Za-zÀ-ú]{2}", t):
        return False
    if re.search(r"(^|[\s\"'])(HK(LM|CU|EY)|[A-Z]:\\|\\\\|%[A-Z]+%|\$_|Get-|Set-|New-|Remove-|-Command)|\.exe\b|::|\\n\$",
                 s):
        return False
    if "\\" in s and " " not in s:
        return False
    if " " not in t:   # uma palavra só: precisa começar com maiúscula e não parecer id
        return bool(re.fullmatch(r"[A-ZÀ-Ú][A-Za-zÀ-ú\-]+[.:!?…]?|[A-ZÀ-Ú]{2,}[A-ZÀ-Ú ]*", t))
    if re.fullmatch(r"[\w.\-/:]+", t):
        return False
    return bool(PT.search(t)) or t[:1].isupper()


def collect(path: Path, out: dict):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents = {}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p):
            parents[c] = p
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body and \
                isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            docs.add(n.body[0].value)
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Constant, ast.JoinedStr)) or n in docs:
            continue
        if isinstance(parents.get(n), ast.JoinedStr) or isinstance(parents.get(n), ast.FormattedValue):
            continue
        s = literal(n)
        if not s or not visible(s):
            continue
        p, skip = parents.get(n), False
        while p is not None and not isinstance(p, (ast.stmt,)):
            if isinstance(p, ast.Call):
                f = p.func
                name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                if name in SKIP_CALLS:
                    skip = True
                break
            if isinstance(p, ast.Subscript):
                skip = True
                break
            if isinstance(p, ast.Compare):
                skip = True
                break
            p = parents.get(p)
        if not skip:
            out.setdefault(s, str(path.relative_to(ROOT)))


def main():
    out: dict[str, str] = {}
    for f in sorted((ROOT / "lolitos").rglob("*.py")):
        collect(f, out)
    dst = ROOT / "lolitos" / "data" / "i18n" / "pt_keys.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(len(out), "textos", sum(len(k) for k in out), "caracteres", file=sys.stderr)


if __name__ == "__main__":
    main()
