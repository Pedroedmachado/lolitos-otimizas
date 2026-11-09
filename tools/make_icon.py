"""Gera o ícone (.ico) e as imagens do instalador (.bmp) a partir do desenho em código."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter  # noqa: E402

app = QGuiApplication(sys.argv)
from lolitos.ui.icon import pixmap  # noqa: E402

out = Path(__file__).resolve().parents[1] / "build"
out.mkdir(exist_ok=True)
pixmap(256).save(str(out / "app.png"), "PNG")
# .ico com todos os tamanhos desenhados de verdade (16 a 256) — o Windows não precisa reduzir/borrar
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
try:
    from PIL import Image
    tmp = []
    for s in SIZES:
        f = out / f"_ico_{s}.png"
        pixmap(s).save(str(f), "PNG")
        tmp.append(f)
    imgs = [Image.open(f).convert("RGBA") for f in tmp]
    imgs[-1].save(out / "app.ico", format="ICO", sizes=[(s, s) for s in SIZES], append_images=imgs[:-1])
    for f in tmp:
        f.unlink()
except ImportError:   # sem Pillow: ícone de um tamanho só (o Windows reduz)
    pixmap(256).save(str(out / "app.ico"), "ICO")


def banner(w, h, path, scale=1):
    """Imagem lateral do assistente (164x314 em 100%)."""
    img = QImage(w * scale, h * scale, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, img.height())
    g.setColorAt(0, QColor("#0c2a55"))
    g.setColorAt(1, QColor("#050b16"))
    p.fillRect(img.rect(), g)
    ic = pixmap(110 * scale)
    p.drawPixmap((img.width() - ic.width()) // 2, int(img.height() * 0.18), ic)
    f = QFont("Segoe UI", 15)
    f.setBold(True)
    f.setPixelSize(22 * scale)
    p.setFont(f)
    p.setPen(QColor("#5cc8ff"))
    p.drawText(QRect(0, int(img.height() * 0.58), img.width(), 30 * scale), Qt.AlignCenter, "Chinese")
    f2 = QFont("Segoe UI")
    f2.setPixelSize(12 * scale)
    p.setFont(f2)
    p.setPen(QColor("#f2f6fc"))
    p.drawText(QRect(0, int(img.height() * 0.58) + 30 * scale, img.width(), 20 * scale), Qt.AlignCenter,
               "Control")
    p.setPen(QColor("#8597b0"))
    p.drawText(QRect(0, int(img.height() * 0.88), img.width(), 20 * scale), Qt.AlignCenter, "para jogos")
    p.end()
    img.save(str(path), "BMP")


def small(size, path):
    img = QImage(size, size, QImage.Format_RGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.drawPixmap(0, 0, pixmap(size))
    p.end()
    img.save(str(path), "BMP")


banner(164, 314, out / "wizard.bmp")
banner(164, 314, out / "wizard@2x.bmp", scale=2)
small(55, out / "wizard-small.bmp")
small(110, out / "wizard-small@2x.bmp")
print("ícone e imagens do instalador gerados em", out)
