"""Revisão semanal: uma vez por semana confere o disco, os arquivos do sistema e a imagem do Windows e repara o que
estiver danificado. Não mexe nos ajustes aplicados. Roda por uma tarefa agendada do Windows que abre o app com
--weekly-review (sem janela) e grava o resultado no histórico."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from lolitos import APP_ID
from lolitos.core import history, settings
from lolitos.core.system import IS_WIN, data_dir, powershell, run

TASK = f"{APP_ID} - Revisão semanal"
ARG = "--weekly-review"
STEPS = (("chkdsk", "Verificando o disco"), ("dism", "Reparando a imagem do Windows"),
         ("sfc", "Verificando os arquivos do sistema"))


def _command() -> tuple[str, str]:
    """Executável e argumentos para a tarefa agendada."""
    if getattr(sys, "frozen", False):
        return sys.executable, ARG
    pyw = Path(sys.executable).with_name("pythonw.exe")
    main = Path(__file__).resolve().parents[2] / "run_lolitos.pyw"
    return str(pyw if pyw.exists() else sys.executable), f'"{main}" {ARG}'


def _ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def enable(on: bool = True) -> tuple[bool, str]:
    """Cria (domingo, 12h; se o PC estiver desligado, roda assim que possível) ou remove a tarefa."""
    if not IS_WIN:
        return False, "só no Windows"
    if not on:
        r = run(["schtasks", "/Delete", "/F", "/TN", TASK])
        settings.set("weekly_review", False)
        return r.ok or "não" in (r.err + r.out).lower(), ""
    exe, args = _command()
    script = (
        f"$a=New-ScheduledTaskAction -Execute {_ps(exe)} -Argument {_ps(args)};"
        "$t=New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 12:00;"
        "$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries"
        " -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew;"
        "$p=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name)"
        " -LogonType Interactive -RunLevel Highest;"
        f"Register-ScheduledTask -TaskName {_ps(TASK)} -Action $a -Trigger $t -Settings $s -Principal $p -Force"
        " | Out-Null")
    r = powershell(script, timeout=60)
    if r.ok:
        settings.set("weekly_review", True)
    return r.ok, (r.err or r.out).strip()[:300]


def enabled() -> bool:
    if not IS_WIN:
        return bool(settings.get("weekly_review"))
    return run(["schtasks", "/Query", "/TN", TASK]).ok


def last_run() -> float:
    return float(settings.get("weekly_review_last") or 0)


def run_review(progress=None) -> tuple[bool, str]:
    """Disco (só leitura), DISM /RestoreHealth e SFC. Leva de 10 a 30 minutos."""
    from lolitos.modules import repair
    say = progress or (lambda s: None)
    lines, ok_all = [], True
    for tid, text in STEPS:
        t = repair.TOOLS_BY_ID[tid]
        say(f"{text}…  ({t.cmd})")
        ok, out = repair.run_tool(t)
        ok_all &= ok
        tail = " ".join((out or "").split())[-240:]
        lines.append(f"{'OK' if ok else 'AVISO'} · {t.name}" + (f" — {tail}" if not ok and tail else ""))
        say(lines[-1])
    settings.set("weekly_review_last", time.time())
    summary = "; ".join(lines)
    history.add("task", "Revisão semanal: " + ("tudo certo" if ok_all else "terminou com avisos"), "Manutenção",
                success=ok_all, detail=summary, reversible=False)
    try:
        log = data_dir() / "revisao-semanal.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M") + "\n" + "\n".join(lines) + "\n\n")
    except OSError:
        pass
    return ok_all, "\n".join(lines)


def main_headless() -> int:
    """Chamado pela tarefa agendada: roda sem janela e sai."""
    ok, _ = run_review()
    return 0 if ok else 1
