"""Baixa o PresentMon (Intel, licença MIT) para vendor/PresentMon.exe, conferindo o SHA-256.

Usado pelo GitHub Actions e pelo gerar-instalador.bat; o instalador copia o arquivo para {app}\\tools."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lolitos.modules.fps import PM_SHA256, PM_URL, download_presentmon  # noqa: E402

if __name__ == "__main__":
    dst = Path(__file__).resolve().parents[1] / "vendor" / "PresentMon.exe"
    download_presentmon(dst)
    print(f"PresentMon ok: {dst} ({PM_URL}, sha256 {PM_SHA256})")
