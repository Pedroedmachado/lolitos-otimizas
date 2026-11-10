"""Cores e folha de estilo. Três temas — Escuro, Claro (vidro líquido) e Azul — com visual de vidro: fundo com
brilho suave e cartões translúcidos. 'Efeitos visuais' desligado volta às cores sólidas (para PCs mais fracos).

C guarda só cores sólidas (#rrggbb), que também são usadas nos desenhos feitos à mão (gráficos, placa-mãe).
As transparências do vidro ficam nas chaves g* e só entram na folha de estilo."""

BLUE = {
    "bg": "#050b16", "panel": "#0a1526", "panel2": "#0f1e36", "border": "#16304f", "border2": "#1d3d6b",
    "text": "#f2f6fc", "muted": "#8597b0", "accent": "#1e9bff", "accent2": "#5cc8ff", "deep": "#0a6cff",
    "on_accent": "#ffffff", "gold": "#f5b82e",
    "ok": "#4ade80", "warn": "#f5b82e", "bad": "#ff4d5e", "info": "#22c3ff",
    "hero1": "#0c2a55", "hero2": "#0a1526", "hero_border": "#1d3d6b", "deepbg": "#0c2a55",
    "gbg1": "#0f3166", "gbg2": "#050b16", "glass": "rgba(13, 30, 56, 0.62)", "glass2": "rgba(20, 44, 82, 0.55)",
    "gborder": "rgba(110, 190, 255, 0.16)", "gside": "rgba(8, 20, 38, 0.72)", "ghero": "rgba(16, 52, 104, 0.55)",
}
DARK = {
    "bg": "#090a0d", "panel": "#121419", "panel2": "#1a1d24", "border": "#24272f", "border2": "#343945",
    "text": "#f2f4f8", "muted": "#8d94a3", "accent": "#1e9bff", "accent2": "#5cc8ff", "deep": "#0a6cff",
    "on_accent": "#ffffff", "gold": "#f5b82e",
    "ok": "#4ade80", "warn": "#f5b82e", "bad": "#ff4d5e", "info": "#22c3ff",
    "hero1": "#16213a", "hero2": "#121419", "hero_border": "#2a3550", "deepbg": "#15253f",
    "gbg1": "#18233a", "gbg2": "#090a0d", "glass": "rgba(255, 255, 255, 0.045)", "glass2": "rgba(255, 255, 255, 0.07)",
    "gborder": "rgba(255, 255, 255, 0.09)", "gside": "rgba(14, 16, 21, 0.78)", "ghero": "rgba(40, 70, 130, 0.30)",
}
LIGHT = {
    "bg": "#edf3fb", "panel": "#ffffff", "panel2": "#e6eef9", "border": "#c9d7ea", "border2": "#9fb6d6",
    "text": "#0b1220", "muted": "#52637a", "accent": "#0a6cff", "accent2": "#075bee", "deep": "#0a4fd0",
    "on_accent": "#ffffff", "gold": "#c98a00",
    "ok": "#059669", "warn": "#b7791f", "bad": "#e11d48", "info": "#0891b2",
    "hero1": "#d6e6ff", "hero2": "#ffffff", "hero_border": "#9fb6d6", "deepbg": "#d6e6ff",
    "gbg1": "#c9dcff", "gbg2": "#eef2f8", "glass": "rgba(255, 255, 255, 0.58)", "glass2": "rgba(255, 255, 255, 0.78)",
    "gborder": "rgba(255, 255, 255, 0.95)", "gside": "rgba(255, 255, 255, 0.55)", "ghero": "rgba(214, 230, 255, 0.70)",
}
THEMES = {"dark": DARK, "light": LIGHT, "blue": BLUE}
THEME_NAMES = [("dark", "Escuro"), ("light", "Claro"), ("blue", "Azul")]
DEFAULT_THEME = "blue"
C = dict(BLUE)
EFFECTS = [True]     # vidro e animações (Configurações › Efeitos visuais)


def use(theme: str, effects: bool | None = None) -> None:
    C.clear()
    C.update(THEMES.get(theme, BLUE))
    if effects is not None:
        EFFECTS[0] = bool(effects)


def effects() -> bool:
    return EFFECTS[0]


def is_light() -> bool:
    return C.get("bg", "#000").lower() == LIGHT["bg"]


def qss() -> str:
    c = C
    return f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 10pt; color: {c['text']}; }}
QMainWindow, QWidget#root, QWidget#page, QDialog {{ background: {c['bg']}; }}

/* área rolável com fundo SÓLIDO (fundo transparente gera rastros ao rolar) */
QScrollArea {{ background: {c['bg']}; border: none; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: {c['bg']}; }}

/* barra de rolagem completa: trilho, alça e áreas acima/abaixo da alça */
QScrollBar:vertical {{ background: {c['bg']}; width: 12px; margin: 0; border: none; }}
QScrollBar::groove:vertical {{ background: {c['bg']}; border: none; }}
QScrollBar::handle:vertical {{ background: {c['border2']}; border-radius: 5px; min-height: 36px; margin: 2px 3px; }}
QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; border: none; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; width: 0; border: none; background: none; }}
QScrollBar:horizontal {{ background: {c['bg']}; height: 12px; margin: 0; border: none; }}
QScrollBar::handle:horizontal {{ background: {c['border2']}; border-radius: 5px; min-width: 36px; margin: 3px 2px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['accent']}; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; border: none; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height: 0; width: 0; border: none; background: none; }}

QLabel#navsec {{ color: {c['muted']}; font-size: 7.5pt; font-weight: 800; letter-spacing: 1px;
    padding: 8px 14px 2px 14px; }}
QWidget#navlist, QScrollArea#navscroll, QScrollArea#navscroll > QWidget#qt_scrollarea_viewport {{
    background: {c['panel']}; }}
QFrame#sidebar {{ background: {c['panel']}; border-right: 1px solid {c['border']}; }}
QPushButton#nav {{ text-align: left; padding: 7px 14px; border: none; border-radius: 10px; background: transparent;
                  color: {c['muted']}; font-size: 10pt; }}
QPushButton#nav:hover {{ background: {c['panel2']}; color: {c['text']}; }}
QPushButton#nav:checked {{ background: {c['deepbg']}; border: 1px solid {c['accent']};
                          border-left: 3px solid {c['accent']}; }}
QPushButton#navgold {{ border: 1px solid {c['gold']}; border-radius: 4px; background: transparent; }}
QPushButton#navgold:hover, QPushButton#navgold:checked {{ background: rgba(245,184,46,0.10); }}
QPushButton#update {{ text-align: left; padding: 8px 12px; border: 1px solid {c['border']}; border-radius: 10px;
    background: {c['panel']}; color: {c['muted']}; }}
QPushButton#update:hover {{ color: {c['text']}; border-color: {c['border2']}; }}
QLabel#brand1 {{ font-size: 15pt; font-weight: 900; color: {c['text']}; letter-spacing: 1px; }}
QLabel#brand2 {{ font-size: 7.5pt; font-weight: 800; color: {c['accent']}; }}
QLabel#verpill {{ color: {c['accent2']}; background: {c['panel2']}; border: 1px solid {c['border2']};
    border-radius: 9px; padding: 1px 8px; font-size: 8pt; font-weight: 700; }}
QLabel#brand {{ font-size: 15pt; font-weight: 800; color: {c['accent2']}; }}
QLabel#brandsub {{ color: {c['muted']}; font-size: 8.5pt; }}
QLabel#h1 {{ font-size: 20pt; font-weight: 800; }}
QLabel#h3 {{ font-size: 11pt; }}
QLabel#hello {{ font-size: 30pt; font-weight: 900; }}
QLabel#pendtitle {{ color: {c['accent2']}; font-size: 12pt; font-weight: 800; }}
QLabel#cardcap {{ font-size: 8.5pt; font-weight: 800; letter-spacing: 0.5px; }}
QLabel#miniv {{ font-size: 21pt; font-weight: 800; }}
QLabel#scorebig {{ font-size: 34pt; font-weight: 900; }}
QLabel#newtag {{ color: {c['accent2']}; font-size: 8pt; font-weight: 800; }}
QPushButton#outline {{ background: transparent; border: 1px solid {c['accent']}; border-radius: 8px; font-weight: 700;
    padding: 8px; }}
QPushButton#outline:hover {{ background: {c['deepbg']}; }}
QPushButton#outline:disabled {{ border-color: {c['border']}; color: {c['muted']}; }}
QFrame#tcard {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#tcardrec {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c['hero1']}, stop:1 {c['panel']});
    border: 1px solid {c['border2']}; border-radius: 12px; }}
QFrame#tcard:hover, QFrame#tcardrec:hover {{ border-color: {c['accent']}; }}
QLabel#tctitle {{ font-size: 11pt; font-weight: 800; }}
QLabel#goaltag {{ border-radius: 4px; padding: 1px 7px; font-size: 7.5pt; font-weight: 700; }}
QPushButton#link {{ background: transparent; border: none; color: {c['accent2']}; padding: 0; font-size: 8.5pt;
    text-align: left; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QLabel#tcwarn {{ color: {c['gold']}; font-size: 8.5pt; }}
QLabel#tagrec {{ color: {c['accent2']}; background: {c['deepbg']}; border-radius: 4px; padding: 2px 7px;
    font-size: 8pt; font-weight: 800; }}
QLabel#tagrestart {{ color: #2dd4bf; background: rgba(45,212,191,0.12); border-radius: 4px; padding: 2px 7px;
    font-size: 8pt; font-weight: 800; }}
QLabel#tagadv {{ color: {c['gold']}; background: rgba(245,184,46,0.12); border-radius: 4px; padding: 2px 7px;
    font-size: 8pt; font-weight: 800; }}
QLabel#barname {{ color: {c['muted']}; font-size: 8.5pt; }}
QPushButton#chip {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 4px; padding: 6px 12px;
    font-weight: 700; color: {c['text']}; }}
QPushButton#chip:hover {{ border-color: {c['border2']}; }}
QPushButton#chip:checked {{ background: {c['deepbg']}; border-color: {c['accent']}; }}
QPushButton#seg {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 0; padding: 6px 16px;
    color: {c['muted']}; font-weight: 700; }}
QPushButton#seg:checked {{ background: {c['deepbg']}; color: {c['text']}; border-color: {c['accent']}; }}
QFrame#icontile {{ background: {c['panel2']}; border: 1px solid {c['border2']}; border-radius: 12px; }}
QLabel#statcap {{ color: {c['muted']}; font-size: 8pt; letter-spacing: 0.5px; }}
QLabel#statval {{ font-size: 20pt; font-weight: 800; }}
QLabel#statunit {{ color: {c['muted']}; font-size: 8pt; }}
QLabel#pill {{ color: {c['accent2']}; border: 1px solid {c['border2']}; border-radius: 6px; padding: 2px 8px;
    font-size: 8.5pt; font-weight: 700; background: {c['panel']}; }}
QLabel#bigtitle {{ color: {c['accent']}; font-size: 22pt; font-weight: 900; letter-spacing: 0.5px; }}
QLabel#h2 {{ font-size: 12.5pt; font-weight: 700; }}
QLabel#muted {{ color: {c['muted']}; }}
QLabel#big {{ font-size: 34pt; font-weight: 800; color: {c['accent2']}; }}
QFrame#card {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#card:hover {{ border-color: {c['border2']}; }}
QFrame#hero {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c['hero1']}, stop:1 {c['hero2']});
               border: 1px solid {c['hero_border']}; border-radius: 14px; }}
QPushButton {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:disabled {{ color: {c['muted']}; border-color: {c['border']}; }}
QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c['accent']}, stop:1 {c['deep']});
                       color: {c['on_accent']}; border: none; font-weight: 700; }}
QPushButton#primary:hover {{ background: {c['accent']}; }}
QPushButton#primary:disabled {{ background: {c['border']}; color: {c['muted']}; }}
QPushButton#danger {{ border-color: {c['bad']}; color: {c['bad']}; }}
QPushButton#link {{ background: transparent; border: none; color: {c['accent2']}; padding: 2px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 6px; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
QComboBox QAbstractItemView {{ background: {c['panel']}; border: 1px solid {c['border']};
                               selection-background-color: {c['panel2']}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {c['border2']};
                        background: {c['panel2']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
QCheckBox::indicator:disabled {{ background: {c['border']}; border-color: {c['border']}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 8px 14px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {c['accent2']}; border-bottom-color: {c['accent']}; }}
QTabBar::tab:hover {{ color: {c['text']}; }}
QTabBar QToolButton {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 4px; }}
QTabBar QToolButton:hover {{ border-color: {c['accent']}; }}
QProgressBar {{ background: {c['panel2']}; border: none; border-radius: 5px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c['deep']}, stop:1 {c['accent2']});
                       border-radius: 5px; }}
QTableWidget, QTreeWidget, QListWidget {{ background: {c['panel']}; border: 1px solid {c['border']};
    border-radius: 8px; gridline-color: {c['border']}; alternate-background-color: {c['panel2']}; }}
QListWidget::item:selected {{ background: {c['panel2']}; color: {c['text']}; }}
QHeaderView::section {{ background: {c['panel2']}; border: none; padding: 7px; color: {c['text']}; font-weight: 700; }}
QTreeWidget::item {{ padding: 3px 0; }}
QTreeWidget::item:hover {{ background: {c['panel2']}; }}
QTreeWidget::item:selected {{ background: {c['deepbg']}; color: {c['text']}; }}
QSlider::groove:horizontal {{ height: 6px; background: {c['panel2']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 16px; margin: -6px 0; border-radius: 8px; background: {c['accent2']}; }}
QToolTip {{ background: {c['panel2']}; border: 1px solid {c['border2']}; padding: 6px; color: {c['text']}; }}
QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; }}
QMenu::item {{ padding: 6px 18px; }}
QMenu::item:selected {{ background: {c['panel2']}; }}
QMessageBox {{ background: {c['bg']}; }}
""" + (_glass(c) if EFFECTS[0] else "")


def _glass(c) -> str:
    """Vidro: o fundo das telas ganha um brilho que fica parado enquanto rola, e os cartões ficam translúcidos.
    O fundo é pintado pela área de rolagem (nunca transparente de verdade, para não deixar rastro ao rolar)."""
    glow = (f"qradialgradient(cx:0.92, cy:0.0, radius:1.15, fx:0.92, fy:0.0, stop:0 {c['gbg1']}, "
            f"stop:0.55 {c['gbg2']}, stop:1 {c['gbg2']})")
    side = (f"qradialgradient(cx:0.0, cy:1.0, radius:1.3, fx:0.0, fy:1.0, stop:0 {c['gbg1']}, "
            f"stop:0.7 {c['bg']}, stop:1 {c['bg']})")
    return f"""
QMainWindow, QWidget#root {{ background: {side}; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: {glow}; }}
QWidget#page {{ background: transparent; }}
QScrollBar:vertical, QScrollBar::groove:vertical, QScrollBar:horizontal {{ background: transparent; }}
QFrame#sidebar {{ background: {c['gside']}; border-right: 1px solid {c['gborder']}; }}
QWidget#navlist, QScrollArea#navscroll, QScrollArea#navscroll > QWidget#qt_scrollarea_viewport {{
    background: transparent; }}
QFrame#card, QFrame#tcard {{ background: {c['glass']}; border: 1px solid {c['gborder']}; }}
QFrame#card:hover, QFrame#tcard:hover {{ background: {c['glass2']}; border-color: {c['accent']}; }}
QFrame#hero, QFrame#tcardrec {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c['ghero']},
    stop:1 {c['glass']}); border: 1px solid {c['gborder']}; }}
QFrame#tcardrec:hover {{ border-color: {c['accent']}; }}
QFrame#icontile {{ background: {c['glass2']}; border: 1px solid {c['gborder']}; }}
QPushButton {{ background: {c['glass2']}; border: 1px solid {c['gborder']}; }}
QPushButton#chip, QPushButton#seg, QLabel#pill, QPushButton#update {{ background: {c['glass']};
    border: 1px solid {c['gborder']}; }}
QPushButton#chip:checked, QPushButton#seg:checked {{ background: {c['deepbg']}; border-color: {c['accent']}; }}
QPushButton#nav:hover {{ background: {c['glass2']}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{ background: {c['glass2']};
    border: 1px solid {c['gborder']}; }}
QTableWidget, QTreeWidget, QListWidget {{ background: {c['glass']}; border: 1px solid {c['gborder']}; }}
"""
