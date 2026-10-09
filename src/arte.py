"""Arte Bloodborne: fuentes, tema QSS, portada y fondos.

Fuentes OFL en assets/fonts (ver assets/CREDITOS.md). Si un TTF falta o no
carga, todo tiene familia de reserva del sistema: la app nunca se rompe.
"""
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplashScreen

BASE = Path(__file__).resolve().parents[1]
FONTS = BASE / "assets" / "fonts"
IMGS = BASE / "assets" / "images"

TITULO = "Cinzel Decorative"
AMBIENTE = "IM Fell English"
CUERPO = "Libre Baskerville"

HUESO = "#d6cbb6"
ORO = "#c8a44d"
LATON = "#7d6234"


def cargar_fuentes():
    """Registra los TTF en Qt. Devuelve {clave: familia efectiva}."""
    res = {"titulo": "serif", "ambiente": "serif", "cuerpo": "serif"}
    if not FONTS.exists():
        return res
    pedidos = {"titulo": ["CinzelDecorative-Bold.ttf", "CinzelDecorative-Regular.ttf"],
               "ambiente": ["IMFeENrm28P.ttf"],
               "cuerpo": ["Cardo-Regular.ttf"]}
    extras = ["Cardo-Bold.ttf", "Cardo-Italic.ttf", "IMFeENit28P.ttf"]
    for f in extras:
        p = FONTS / f
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
    for clave, ficheros in pedidos.items():
        for f in ficheros:
            p = FONTS / f
            if not p.exists():
                continue
            fid = QFontDatabase.addApplicationFont(str(p))
            if fid >= 0:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    res[clave] = fams[0]
                    break
    return res


def qss() -> str:
    tex = (IMGS / "textura.png").as_posix()
    return f"""
QMainWindow {{ background-color:#0c0a08; }}
QTabWidget::pane {{ border:1px solid {LATON}; background-color:#100d0a;
    background-image:url("{tex}"); background-repeat:repeat; }}
QWidget {{ background-color:transparent; color:{HUESO}; font-family:'{CUERPO}',serif; font-size:13px; }}
QTabBar::tab {{ font-family:'{TITULO}',serif; font-size:14px; color:#9a8c74;
    background:#161110; padding:9px 18px; margin-right:3px;
    border:1px solid #2c2318; border-bottom:2px solid #000;
    border-top-left-radius:4px; border-top-right-radius:4px; }}
QTabBar::tab:selected {{ color:{ORO}; background:#221812;
    border:1px solid {LATON}; border-bottom:2px solid #8e1414; }}
QTabBar::tab:hover:!selected {{ color:{HUESO}; }}
QPushButton {{ font-family:'{TITULO}',serif; font-size:12px; color:{HUESO};
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #241b13, stop:1 #17110c);
    border:1px solid {LATON}; border-radius:3px; padding:7px 12px; }}
QPushButton:hover {{ color:#f0e6d2; border-color:{ORO}; background:#2e1f14; }}
QPushButton:pressed {{ background:#3d0f0f; }}
QPushButton:checked {{ background:#3d0f0f; color:{ORO}; border-color:{ORO}; }}
QLineEdit, QTextEdit, QComboBox, QSpinBox, QListWidget, QTableWidget {{
    background-color:#131009; border:1px solid #4a3a26; border-radius:3px;
    padding:5px; color:{HUESO}; selection-background-color:#4a0d0d; }}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border:1px solid {ORO}; }}
QListWidget::item {{ padding:4px; }}
QListWidget::item:selected {{ background:#3d0f0f; color:#f0e2c8; border:1px solid {LATON}; }}
QComboBox QAbstractItemView {{ background-color:#131009; color:{HUESO};
    selection-background-color:#3d0f0f; border:1px solid {LATON}; }}
QGroupBox {{ font-family:'{TITULO}',serif; font-size:13px; color:{ORO};
    border:1px solid {LATON}; border-radius:4px; margin-top:18px; padding-top:8px;
    background-color:rgba(20,14,10,160); }}
QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 6px; }}
QTableWidget {{ gridline-color:#3a2c1e; }}
QHeaderView::section {{ font-family:'{TITULO}',serif; color:{ORO};
    background:#1d150e; border:1px solid #2c2318; padding:5px; }}
QCheckBox {{ color:{HUESO}; spacing:6px; }}
QCheckBox::indicator {{ width:15px; height:15px; border:1px solid {LATON};
    background:#131009; border-radius:2px; }}
QCheckBox::indicator:checked {{ background:#8e1414; border:1px solid {ORO}; }}
QScrollBar:vertical {{ background:#0c0a08; width:12px; border-left:1px solid #2c2318; }}
QScrollBar::handle:vertical {{ background:#3a2c1e; min-height:24px; border:1px solid {LATON}; }}
QScrollBar::handle:vertical:hover {{ background:#5a452c; }}
QScrollBar:horizontal {{ background:#0c0a08; height:12px; border-top:1px solid #2c2318; }}
QScrollBar::handle:horizontal {{ background:#3a2c1e; min-width:24px; border:1px solid {LATON}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height:0; width:0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background:none; }}
QToolTip {{ background-color:#0c0a08; color:{ORO}; border:1px solid {LATON}; padding:4px; }}
QStatusBar {{ color:#8d8172; font-family:'{AMBIENTE}',serif; font-style:italic; }}
QStatusBar::item {{ border:none; }}
QLabel[big="true"] {{ font-family:'{TITULO}',serif; }}
"""


def _caronte_recortado():
    """Grabado sin la banda de texto inferior, oscurecido para fondos."""
    pm = QPixmap(str(IMGS / "caronte.jpg"))
    if pm.isNull():
        return pm
    rec = pm.copy(0, 0, pm.width(), int(pm.height() * 0.86))
    osc = QPixmap(rec.size())
    osc.fill(Qt.transparent)
    p = QPainter(osc)
    p.drawPixmap(0, 0, rec)
    p.fillRect(osc.rect(), QColor(5, 3, 2, 150))
    p.end()
    return osc


def splash():
    """Portada de arranque: Caronte + título. None si falta la imagen."""
    base = _caronte_recortado()
    if base.isNull():
        return None
    w, h = 760, 520
    pm = base.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (pm.width() - w) // 2
    pm = pm.copy(x, 0, w, h)
    p = QPainter(pm)
    p.fillRect(pm.rect(), QColor(5, 3, 2, 60))
    p.setPen(QColor(HUESO))
    p.setFont(QFont(TITULO, 44, QFont.Bold))
    p.drawText(pm.rect().adjusted(0, 150, 0, -60), Qt.AlignCenter, "D & D  ·  2024")
    p.setPen(QColor(ORO))
    p.setFont(QFont(AMBIENTE, 20, -1, True))
    p.drawText(pm.rect().adjusted(0, 240, 0, 0), Qt.AlignCenter,
               "— cuaderno de campaña del cazador —")
    p.setPen(QColor(LATON))
    p.drawRect(6, 6, w - 13, h - 13)
    p.end()
    sp = QSplashScreen(pm)
    sp.setStyleSheet("QSplashScreen { border:1px solid #7d6234; }")
    return sp


def fondo_vacio(texto, w=900, h=520):
    """Fondo para el mapa del mundo cuando aún no hay imagen: Caronte + texto."""
    base = _caronte_recortado()
    pm = QPixmap(w, h)
    if base.isNull():
        pm.fill(QColor("#14100c"))
    else:
        pm = base.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (pm.width() - w) // 2
        pm = pm.copy(x, 0, w, h)
        p0 = QPainter(pm)
        p0.fillRect(pm.rect(), QColor(5, 3, 2, 110))
        p0.end()
    p = QPainter(pm)
    p.setPen(QColor(HUESO))
    p.setFont(QFont(AMBIENTE, 22, -1, True))
    p.drawText(pm.rect(), Qt.AlignCenter, texto)
    p.setPen(QColor(LATON))
    p.drawRect(8, 8, w - 17, h - 17)
    p.end()
    return pm


def normalizar_fondo(origen, max_lado=2048):
    """Devuelve la ruta de una imagen que Qt sí puede mostrar (o "").

    - Si QPixmap la abre y no es gigante: la original tal cual.
    - Si es gigante pero Qt la abre: copia reducida junto al original.
    - Si Qt no la abre (JPEG raros, CMYK…): convierte con Pillow a PNG.
    La copia se llama "<nombre> (Qt).png" en la misma carpeta.
    """
    from pathlib import Path as _P
    src = _P(origen)
    if not src.exists():
        return ""
    pm = QPixmap(str(src))
    if not pm.isNull() and max(pm.width(), pm.height()) <= max_lado:
        return str(src)
    dest = src.parent / f"{src.stem} (Qt).png"
    try:
        if not pm.isNull():
            pm.scaled(max_lado, max_lado, Qt.KeepAspectRatio,
                      Qt.SmoothTransformation).save(str(dest))
            return str(dest)
    except Exception:
        pass
    try:
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(src) as im:
            peq = im.convert("RGB")
            peq.thumbnail((max_lado, max_lado))
            peq.save(dest)
        return str(dest) if not QPixmap(str(dest)).isNull() else ""
    except Exception:
        return ""
