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
pixmap(256).save(str(out / "lolitos.ico"), "ICO")
pixmap(256).save(str(out / "lolitos.png"), "PNG")


def banner(w, h, path, scale=1):
    """Imagem lateral do assistente (164x314 em 100%)."""
    img = QImage(w * scale, h * scale, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, img.height())
    g.setColorAt(0, QColor("#2a2012"))
    g.setColorAt(1, QColor("#0e1014"))
    p.fillRect(img.rect(), g)
    ic = pixmap(110 * scale)
    p.drawPixmap((img.width() - ic.width()) // 2, int(img.height() * 0.18), ic)
    f = QFont("Segoe UI", 15)
    f.setBold(True)
    f.setPixelSize(22 * scale)
    p.setFont(f)
    p.setPen(QColor("#f2c46b"))
    p.drawText(QRect(0, int(img.height() * 0.58), img.width(), 30 * scale), Qt.AlignCenter, "Lolitos")
    f2 = QFont("Segoe UI")
    f2.setPixelSize(12 * scale)
    p.setFont(f2)
    p.setPen(QColor("#c9cdd6"))
    p.drawText(QRect(0, int(img.height() * 0.58) + 30 * scale, img.width(), 20 * scale), Qt.AlignCenter,
               "Otimizações")
    p.setPen(QColor("#8b93a4"))
    p.drawText(QRect(0, int(img.height() * 0.88), img.width(), 20 * scale), Qt.AlignCenter, "Black Desert")
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
