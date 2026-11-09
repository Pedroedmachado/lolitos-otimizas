"""Cores e folha de estilo (escuro com dourado, inspirado no BDO)."""

DARK = {
    "bg": "#0e1014", "panel": "#161920", "panel2": "#1d212a", "border": "#2a2f3a",
    "text": "#e7e9ee", "muted": "#8b93a4", "accent": "#e2a740", "accent2": "#f2c46b",
    "ok": "#4cb782", "warn": "#e3b23c", "bad": "#e0584c", "info": "#5a9cf0",
}
LIGHT = {
    "bg": "#f3f4f7", "panel": "#ffffff", "panel2": "#eef0f4", "border": "#d6dae2",
    "text": "#1b1e25", "muted": "#5f6878", "accent": "#b77a12", "accent2": "#d4952a",
    "ok": "#2f9466", "warn": "#b88715", "bad": "#c43d32", "info": "#2f74d0",
}
C = dict(DARK)


def use(theme: str) -> None:
    C.clear()
    C.update(LIGHT if theme == "light" else DARK)


def qss() -> str:
    c = C
    return f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 10pt; color: {c['text']}; }}
QMainWindow, QWidget#root {{ background: {c['bg']}; }}
QWidget#page {{ background: {c['bg']}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QFrame#sidebar {{ background: {c['panel']}; border-right: 1px solid {c['border']}; }}
QPushButton#nav {{ text-align: left; padding: 9px 14px; border: none; border-radius: 8px; background: transparent;
                  color: {c['muted']}; font-size: 10.5pt; }}
QPushButton#nav:hover {{ background: {c['panel2']}; color: {c['text']}; }}
QPushButton#nav:checked {{ background: {c['panel2']}; color: {c['accent2']}; font-weight: 600; }}
QLabel#brand {{ font-size: 15pt; font-weight: 700; color: {c['accent2']}; }}
QLabel#brandsub {{ color: {c['muted']}; font-size: 8.5pt; }}
QLabel#h1 {{ font-size: 18pt; font-weight: 700; }}
QLabel#h2 {{ font-size: 12.5pt; font-weight: 650; }}
QLabel#muted {{ color: {c['muted']}; }}
QLabel#big {{ font-size: 34pt; font-weight: 800; color: {c['accent2']}; }}
QFrame#card {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#card:hover {{ border-color: #3a4150; }}
QFrame#hero {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2a2012, stop:1 {c['panel']});
               border: 1px solid #4a3a1c; border-radius: 14px; }}
QPushButton {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:disabled {{ color: {c['muted']}; border-color: {c['border']}; }}
QPushButton#primary {{ background: {c['accent']}; color: #1a1306; border: none; font-weight: 700; }}
QPushButton#primary:hover {{ background: {c['accent2']}; }}
QPushButton#primary:disabled {{ background: #5a4a2a; color: #2a2210; }}
QPushButton#danger {{ border-color: {c['bad']}; color: {c['bad']}; }}
QPushButton#link {{ background: transparent; border: none; color: {c['accent2']}; padding: 2px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 6px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
QComboBox QAbstractItemView {{ background: {c['panel']}; selection-background-color: {c['panel2']}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {c['border']};
                        background: {c['panel2']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
QCheckBox::indicator:disabled {{ background: #3b404b; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 8px 14px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {c['accent2']}; border-bottom-color: {c['accent']}; }}
QTabBar::tab:hover {{ color: {c['text']}; }}
QProgressBar {{ background: {c['panel2']}; border: none; border-radius: 5px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 5px; }}
QTableWidget, QTreeWidget, QListWidget {{ background: {c['panel']}; border: 1px solid {c['border']};
    border-radius: 8px; gridline-color: {c['border']}; alternate-background-color: {c['panel2']}; }}
QHeaderView::section {{ background: {c['panel2']}; border: none; padding: 6px; color: {c['muted']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QSlider::groove:horizontal {{ height: 6px; background: {c['panel2']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 16px; margin: -6px 0; border-radius: 8px; background: {c['accent2']}; }}
QToolTip {{ background: {c['panel2']}; border: 1px solid {c['border']}; padding: 6px; color: {c['text']}; }}
QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; }}
QMenu::item:selected {{ background: {c['panel2']}; }}
"""
