"""Mapas jerárquicos: mundo -> localización (mapa propio) -> punto de interés.

Cada nivel pinta su imagen con pines con nombre; clic selecciona, doble clic
entra, clic en vacío (en modo añadir) crea. Las imágenes se eligen con
«Fondo» (pasan por normalizar_fondo).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QFileDialog, QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QInputDialog,
    QSizePolicy, QStackedWidget, QScrollArea, QTextEdit
)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import Qt, Signal, QRectF
from ..database import connect, MAPAS_DIR
from ..arte import fondo_vacio


class MapCanvas(QWidget):
    """Lienzo con imagen + pines con nombre. Tamaño fijo = imagen mostrada."""
    clic_vacio = Signal(float, float)
    clic_pin = Signal(int)
    doble_pin = Signal(int)
    cambio_zoom = Signal(float)

    def __init__(self, texto_vacio="Sin imagen", parent=None):
        super().__init__(parent)
        self._img = QPixmap()
        self._texto_vacio = texto_vacio
        self._pines = []  # [{nombre, x, y, sel}]
        self._zoom = 1.0
        self._ajustar = True
        self._tam_fit = (900, 520)
        self._hbar = None
        self._vbar = None
        self._drag = None  # (x0, y0, h0, v0)
        self._movido = False
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(120, 120)
        self.setCursor(Qt.OpenHandCursor)

    def set_scroll(self, hbar, vbar):
        self._hbar, self._vbar = hbar, vbar

    # ---- estado ----
    def set_imagen(self, pm):
        self._img = pm if not pm.isNull() else QPixmap()
        self.mostrar()

    def set_pines(self, pines):
        self._pines = list(pines)
        self.update()

    def marcar(self, idx):
        for i, p in enumerate(self._pines):
            p["sel"] = (i == idx)
        self.update()

    def tam_base(self):
        if not self._img.isNull():
            return (self._img.width(), self._img.height())
        return (900, 520)

    # ---- zoom ----
    def encajar(self, w, h):
        self._tam_fit = (max(50, w), max(50, h))
        if self._ajustar:
            self.mostrar()

    def zoom_por(self, factor):
        self._zoom = min(8.0, max(0.2, self._zoom * factor))
        self._ajustar = False
        self.mostrar()
        self.cambio_zoom.emit(self._zoom)

    def zoom_fijo(self, valor):
        self._zoom = valor
        self._ajustar = False
        self.mostrar()
        self.cambio_zoom.emit(self._zoom)

    def zoom_ajustar(self):
        self._ajustar = True
        self._zoom = 1.0
        self.mostrar()
        self.cambio_zoom.emit(self._zoom)

    def mostrar(self):
        bw, bh = self.tam_base()
        if self._ajustar:
            vw, vh = self._tam_fit
            s = min(vw / bw, vh / bh)
            w, h = max(50, round(bw * s)), max(50, round(bh * s))
        else:
            w, h = max(50, round(bw * self._zoom)), max(50, round(bh * self._zoom))
        if (w, h) != (self.width(), self.height()):
            self.setFixedSize(w, h)
        self.update()

    # ---- pintado ----
    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#100d0a"))
        w, h = self.width(), self.height()
        if self._img.isNull():
            ph = fondo_vacio(self._texto_vacio, w, h)
            p.drawPixmap(0, 0, ph)
        else:
            p.drawPixmap(0, 0, w, h, self._img)
        for i, pin in enumerate(self._pines):
            cx, cy = pin["x"] * w, pin["y"] * h
            sel = pin.get("sel", False)
            r = 9 if sel else 7
            p.setPen(QPen(QColor("#c8a44d"), 2 if sel else 1))
            p.setBrush(QBrush(QColor("#8e1414") if sel else QColor("#3d0f0f")))
            p.drawEllipse(int(cx - r), int(cy - r), r * 2, r * 2)
            p.setPen(QPen(QColor("#0c0a08"), 1))
            p.setBrush(QBrush(QColor("#0c0a08")))
            f = QFont("Segoe UI", 10, QFont.Bold)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(pin["nombre"]) + 12
            tx, ty = int(cx - tw / 2), int(cy + r + 3)
            p.setPen(QPen(QColor("#7d6234"), 1))
            p.setBrush(QBrush(QColor(12, 10, 8, 220)))
            p.drawRect(tx, ty, int(tw), 20)
            p.setPen(QPen(QColor("#e8dcc0") if sel else QColor("#d6cbb6")))
            p.drawText(tx, ty, int(tw), 20, Qt.AlignCenter, pin["nombre"])
        p.end()

    # ---- entrada ----
    def _pin_en(self, pos):
        w, h = max(1, self.width()), max(1, self.height())
        mejor, bd = -1, 16.0
        for i, pin in enumerate(self._pines):
            d = ((pin["x"] * w - pos.x()) ** 2 + (pin["y"] * h - pos.y()) ** 2) ** 0.5
            if d < bd:
                mejor, bd = i, d
        return mejor

    def mousePressEvent(self, ev):
        if ev.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._drag = (ev.pos().x(), ev.pos().y(),
                          self._hbar.value() if self._hbar else 0,
                          self._vbar.value() if self._vbar else 0)
            self._movido = False
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag is not None and self._hbar is not None:
            x0, y0, h0, v0 = self._drag
            dx, dy = x0 - ev.pos().x(), y0 - ev.pos().y()
            if abs(dx) + abs(dy) > 4:
                self._movido = True
                self.setCursor(Qt.ClosedHandCursor)
                self._hbar.setValue(h0 + dx)
                self._vbar.setValue(v0 + dy)
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._drag is not None and ev.button() in (Qt.LeftButton, Qt.MiddleButton):
            arrastre, movido = self._drag, self._movido
            self._drag, self._movido = None, False
            self.setCursor(Qt.OpenHandCursor)
            if movido or ev.button() != Qt.LeftButton:
                return
            i = self._pin_en(ev.pos())
            if i >= 0:
                self.clic_pin.emit(i)
            else:
                w, h = max(1, self.width()), max(1, self.height())
                self.clic_vacio.emit(ev.pos().x() / w, ev.pos().y() / h)
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        i = self._pin_en(ev.pos())
        if i >= 0:
            self.doble_pin.emit(i)
        else:
            super().mouseDoubleClickEvent(ev)

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            self.zoom_por(1.25 if ev.angleDelta().y() > 0 else 1 / 1.25)
            ev.accept()
        else:
            ev.ignore()


def _scroll_con(canvas):
    sc = QScrollArea()
    sc.setWidgetResizable(False)
    sc.setWidget(canvas)
    return sc


class WorldMapWidget(QWidget):
    def __init__(self, goto_battlemap=None, parent=None):
        super().__init__(parent)
        self.goto_battlemap = goto_battlemap
        self.stack = QStackedWidget()
        self._mundo_id = None
        self._loc_id = None
        self._poi_id = None
        self._modo_add = None  # None | "loc" | "poi"

        # ---------- página 0: mundo ----------
        pg0 = QWidget()
        self.cmb = QComboBox()
        b_bg = QPushButton("Fondo…")
        b_add_map = QPushButton("+ Mapa mundo")
        b_del_map = QPushButton("Borrar mundo")
        b_add_city = QPushButton("Añadir ciudad (clic)")
        b_del_city = QPushButton("Borrar ciudad")
        b_goto = QPushButton("Ir a su battlemap →")
        top = QHBoxLayout()
        top.addWidget(QLabel("Mundo:"))
        top.addWidget(self.cmb, 1)
        for b in (b_bg, b_add_map, b_del_map, b_add_city, b_del_city, b_goto):
            top.addWidget(b)
        self.canvas = MapCanvas("El mapa aún duerme…\nPulsa «Fondo…» para despertarlo")
        self.lst = QListWidget()
        self.lst.itemClicked.connect(self._ver_detalle)
        self.detalle = QLabel("Selecciona una ciudad.")
        self.detalle.setWordWrap(True)
        b_entrar = QPushButton("Entrar en la ciudad →")
        mid = QHBoxLayout()
        mid.addWidget(self.lst, 1)
        col_d = QVBoxLayout()
        col_d.addWidget(self.detalle, 1)
        col_d.addWidget(b_entrar)
        mid.addLayout(col_d, 2)
        l0 = QVBoxLayout(pg0)
        l0.addLayout(top)
        self.scroll0 = _scroll_con(self.canvas)
        self.canvas.set_scroll(self.scroll0.horizontalScrollBar(),
                               self.scroll0.verticalScrollBar())
        l0.addWidget(self.scroll0, 3)
        l0.addLayout(self._fila_zoom(self.canvas))
        l0.addLayout(mid, 1)

        # ---------- página 1: localización ----------
        pg1 = QWidget()
        self.b_volver0 = QPushButton("‹ Mundo")
        self.lbl_loc = QLabel("")
        self.lbl_loc.setStyleSheet("font-size:16px; color:#c8a44d;")
        b_fondo_loc = QPushButton("Fondo…")
        b_add_poi = QPushButton("+ Punto de interés (clic)")
        b_del_poi = QPushButton("Borrar punto")
        b_add_bm = QPushButton("+ Battlemap aquí")
        b_goto1 = QPushButton("Ir a su battlemap →")
        top1 = QHBoxLayout()
        top1.addWidget(self.b_volver0)
        top1.addWidget(self.lbl_loc, 1)
        for b in (b_fondo_loc, b_add_poi, b_del_poi, b_add_bm, b_goto1):
            top1.addWidget(b)
        self.canvas_loc = MapCanvas("Sin mapa: pulsa «Fondo…»")
        self.lst_poi = QListWidget()
        self.det_poi = QLabel("Selecciona un punto.")
        self.det_poi.setWordWrap(True)
        b_entrar_poi = QPushButton("Ver punto →")
        mid1 = QHBoxLayout()
        mid1.addWidget(self.lst_poi, 1)
        col_d1 = QVBoxLayout()
        col_d1.addWidget(self.det_poi, 1)
        col_d1.addWidget(b_entrar_poi)
        mid1.addLayout(col_d1, 2)
        l1 = QVBoxLayout(pg1)
        l1.addLayout(top1)
        self.scroll1 = _scroll_con(self.canvas_loc)
        self.canvas_loc.set_scroll(self.scroll1.horizontalScrollBar(),
                                   self.scroll1.verticalScrollBar())
        l1.addWidget(self.scroll1, 3)
        l1.addLayout(self._fila_zoom(self.canvas_loc))
        l1.addLayout(mid1, 1)

        # ---------- página 2: punto de interés ----------
        pg2 = QWidget()
        self.b_volver1 = QPushButton("‹ Localización")
        self.lbl_poi = QLabel("")
        self.lbl_poi.setStyleSheet("font-size:16px; color:#c8a44d;")
        b_fondo_poi = QPushButton("Imagen…")
        b_del_poi2 = QPushButton("Borrar punto")
        top2 = QHBoxLayout()
        top2.addWidget(self.b_volver1)
        top2.addWidget(self.lbl_poi, 1)
        top2.addWidget(b_fondo_poi)
        top2.addWidget(b_del_poi2)
        self.e_desc_poi = QTextEdit()
        self.e_desc_poi.setMaximumHeight(110)
        b_guardar_poi = QPushButton("Guardar descripción")
        self.canvas_poi = MapCanvas("Sin imagen")
        l2 = QVBoxLayout(pg2)
        l2.addLayout(top2)
        self.scroll2 = _scroll_con(self.canvas_poi)
        self.canvas_poi.set_scroll(self.scroll2.horizontalScrollBar(),
                                   self.scroll2.verticalScrollBar())
        l2.addWidget(self.scroll2, 3)
        l2.addLayout(self._fila_zoom(self.canvas_poi))
        l2.addWidget(QLabel("Descripción:"))
        l2.addWidget(self.e_desc_poi)
        l2.addWidget(b_guardar_poi)

        self.stack.addWidget(pg0)
        self.stack.addWidget(pg1)
        self.stack.addWidget(pg2)
        lay = QVBoxLayout(self)
        lay.addWidget(self.stack)

        b_bg.clicked.connect(self.poner_fondo)
        b_add_map.clicked.connect(self.crear_mapa)
        b_del_map.clicked.connect(self.borrar_mundo)
        b_add_city.clicked.connect(lambda: self.activar_add("loc"))
        b_del_city.clicked.connect(self.borrar_ciudad)
        b_goto.clicked.connect(self.ir_battlemap)
        b_entrar.clicked.connect(self.entrar_ciudad)
        self.cmb.currentIndexChanged.connect(self.cargar)
        self.canvas.clic_vacio.connect(self._clic_vacio_mundo)
        self.canvas.clic_pin.connect(self._clic_pin_mundo)
        self.canvas.doble_pin.connect(self._entrar_loc_idx)

        self.b_volver0.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        b_fondo_loc.clicked.connect(self.poner_fondo_loc)
        b_add_poi.clicked.connect(lambda: self.activar_add("poi"))
        b_del_poi.clicked.connect(self.borrar_poi)
        b_add_bm.clicked.connect(self.crear_battlemap_aqui)
        b_goto1.clicked.connect(self.ir_battlemap)
        b_entrar_poi.clicked.connect(self.entrar_poi)
        self.lst_poi.itemClicked.connect(self._ver_poi_item)
        self.canvas_loc.clic_vacio.connect(self._clic_vacio_loc)
        self.canvas_loc.clic_pin.connect(self._clic_pin_loc)
        self.canvas_loc.doble_pin.connect(self._entrar_poi_idx)

        self.b_volver1.clicked.connect(self._volver_loc)
        b_fondo_poi.clicked.connect(self.poner_fondo_poi)
        b_del_poi2.clicked.connect(self.borrar_poi_actual)
        b_guardar_poi.clicked.connect(self.guardar_desc_poi)

        self.refrescar()

    # ---------- utilidades ----------
    def _fila_zoom(self, canvas):
        fila = QHBoxLayout()
        b_mas = QPushButton("+")
        b_menos = QPushButton("−")
        b_100 = QPushButton("1:1")
        b_fit = QPushButton("Ajustar")
        for b in (b_mas, b_menos, b_100, b_fit):
            b.setMaximumWidth(70)
            fila.addWidget(b)
        lbl = QLabel("100%")
        fila.addWidget(lbl)
        fila.addWidget(QLabel("Ctrl+rueda o botones para zoom."))
        fila.addStretch(1)
        b_mas.clicked.connect(lambda: canvas.zoom_por(1.25))
        b_menos.clicked.connect(lambda: canvas.zoom_por(1 / 1.25))
        b_100.clicked.connect(lambda: canvas.zoom_fijo(1.0))
        b_fit.clicked.connect(canvas.zoom_ajustar)
        canvas.cambio_zoom.connect(lambda z: lbl.setText(f"{round(z * 100)}%"))
        return fila

    def _fondo_dialogo(self, titulo):
        from ..arte import normalizar_fondo
        inicio = str(MAPAS_DIR) if MAPAS_DIR.exists() else ""
        path, _ = QFileDialog.getOpenFileName(self, titulo, inicio,
                                              "Imágenes (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return ""
        ruta = normalizar_fondo(path)
        if not ruta:
            QMessageBox.warning(self, "Fondo", f"No pude leer esa imagen:\n{path}")
        return ruta

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for cv, sc in ((self.canvas, self.scroll0), (self.canvas_loc, self.scroll1),
                       (self.canvas_poi, self.scroll2)):
            cv.encajar(sc.viewport().width(), sc.viewport().height())

    # ---------- página mundo ----------
    def refrescar(self):
        con = connect()
        maps = con.execute("SELECT * FROM mapas_mundo").fetchall()
        con.close()
        self.cmb.blockSignals(True)
        self.cmb.clear()
        for m in maps:
            self.cmb.addItem(m["nombre"], m["id"])
        self.cmb.blockSignals(False)
        if maps:
            self.cargar(0)

    def mapa_id(self):
        i = self.cmb.currentIndex()
        return self.cmb.itemData(i) if i >= 0 else None

    def cargar(self, idx):
        mid = self.mapa_id()
        if not mid:
            return
        self._mundo_id = mid
        con = connect()
        m = con.execute("SELECT * FROM mapas_mundo WHERE id=?", (mid,)).fetchone()
        locs = con.execute("SELECT l.*, (SELECT COUNT(*) FROM personajes p WHERE p.localizacion_id=l.id) npers, "
                           "(SELECT COUNT(*) FROM battlemaps b WHERE b.localizacion_id=l.id) nmaps "
                           "FROM localizaciones l WHERE l.mapa_mundo_id=?", (mid,)).fetchall()
        con.close()
        img = m["imagen_path"] or ""
        self.canvas.set_imagen(QPixmap(img) if img else QPixmap())
        self._locs = [dict(l) for l in locs]
        self.canvas.set_pines([{"nombre": l["nombre"], "x": l["x"], "y": l["y"], "sel": False}
                               for l in self._locs])
        self.canvas.zoom_ajustar()
        self.lst.clear()
        for l in self._locs:
            it = QListWidgetItem(f"{'🏙' if l['tipo'] == 'ciudad' else '📍'} {l['nombre']} — {l['npers']} pers · {l['nmaps']} mapas")
            it.setData(Qt.UserRole, l["id"])
            self.lst.addItem(it)
        self.stack.setCurrentIndex(0)

    def poner_fondo(self):
        if not self.mapa_id():
            QMessageBox.warning(self, "Fondo", "Crea primero un mapa del mundo con «+ Mapa mundo».")
            return
        ruta = self._fondo_dialogo("Mapa del mundo")
        if not ruta:
            return
        con = connect()
        con.execute("UPDATE mapas_mundo SET imagen_path=? WHERE id=?", (ruta, self.mapa_id()))
        con.commit(); con.close()
        self.cargar(0)

    def borrar_mundo(self):
        mid = self.mapa_id()
        if not mid:
            return
        con = connect()
        nloc = con.execute("SELECT COUNT(*) FROM localizaciones WHERE mapa_mundo_id=?", (mid,)).fetchone()[0]
        nbm = con.execute("SELECT COUNT(*) FROM battlemaps WHERE localizacion_id IN "
                          "(SELECT id FROM localizaciones WHERE mapa_mundo_id=?)", (mid,)).fetchone()[0]
        con.close()
        if QMessageBox.question(
                self, "Borrar mundo",
                f"¿Borrar este mundo con sus {nloc} localizaciones y {nbm} battlemaps?\n"
                f"(Los personajes se quedan sin ubicación, no se borran.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) != QMessageBox.StandardButton.Yes:
            return
        con = connect()
        con.execute("DELETE FROM mapas_mundo WHERE id=?", (mid,))
        con.commit(); con.close()
        self._mundo_id = None
        self.refrescar()

    def crear_mapa(self):
        nombre, ok = QInputDialog.getText(self, "Nuevo mapa", "Nombre del mapa del mundo:")
        if ok and nombre.strip():
            con = connect()
            camp = con.execute("SELECT id FROM campanas LIMIT 1").fetchone()
            con.execute("INSERT INTO mapas_mundo(campana_id,nombre) VALUES(?,?)",
                        (camp["id"] if camp else None, nombre.strip()))
            con.commit(); con.close()
            self.refrescar()

    def activar_add(self, modo):
        self._modo_add = modo
        donde = "el mapa" if modo == "loc" else "el mapa de la localización"
        QMessageBox.information(self, "Añadir", f"Ahora haz CLIC sobre {donde} para colocarlo.")

    def _clic_vacio_mundo(self, rx, ry):
        if self._modo_add != "loc" or not self.mapa_id():
            return
        nombre, ok = QInputDialog.getText(self, "Nueva localización", "Nombre (ej. Puerta de Baldur):")
        if ok and nombre.strip():
            tipo, ok2 = QInputDialog.getItem(self, "Tipo", "Tipo:", ["ciudad", "pueblo", "mazmorra", "punto_interes"], 0, False)
            con = connect()
            con.execute("INSERT INTO localizaciones(mapa_mundo_id,nombre,tipo,x,y) VALUES(?,?,?,?,?)",
                        (self.mapa_id(), nombre.strip(), tipo if ok2 else "ciudad", rx, ry))
            con.commit(); con.close()
            self._modo_add = None
            self.cargar(0)

    def _clic_pin_mundo(self, i):
        self.canvas.marcar(i)
        for r in range(self.lst.count()):
            if self.lst.item(r).data(Qt.UserRole) == self._locs[i]["id"]:
                self.lst.setCurrentRow(r)
        self._ver_loc(self._locs[i]["id"])

    def _ver_detalle(self, item):
        self._ver_loc(item.data(Qt.UserRole))

    def _ver_loc(self, lid):
        con = connect()
        l = con.execute("SELECT * FROM localizaciones WHERE id=?", (lid,)).fetchone()
        pers = con.execute("SELECT nombre,clase,nivel FROM personajes WHERE localizacion_id=?", (lid,)).fetchall()
        bms = con.execute("SELECT nombre FROM battlemaps WHERE localizacion_id=?", (lid,)).fetchall()
        pois = con.execute("SELECT COUNT(*) FROM puntos_interes WHERE localizacion_id=?", (lid,)).fetchone()[0]
        con.close()
        if not l:
            return
        self.detalle.setText(
            f"<h3>{l['nombre']} <small>({l['tipo']})</small></h3>"
            f"<p>{l['descripcion'] or 'Sin descripción. Edítala en Ciudades.'}</p>"
            f"<p><b>Personajes aquí ({len(pers)}):</b> " + (", ".join(f"{p['nombre']} ({p['clase']} {p['nivel']})" for p in pers) or "—") + "</p>"
            f"<p><b>Battlemaps ({len(bms)}):</b> " + (", ".join(b['nombre'] for b in bms) or "—") + "</p>"
            f"<p><b>Puntos de interés:</b> {pois}</p>")
        self._sel = lid
        for i, ll in enumerate(self._locs):
            if ll["id"] == lid:
                self.canvas.marcar(i)

    def entrar_ciudad(self):
        lid = getattr(self, "_sel", None)
        if lid:
            self.entrar_loc(lid)

    def _entrar_loc_idx(self, i):
        self.entrar_loc(self._locs[i]["id"])

    def entrar_loc(self, lid):
        self._loc_id = lid
        self._modo_add = None
        self.cargar_loc()
        self.stack.setCurrentIndex(1)

    def borrar_ciudad(self):
        it = self.lst.currentItem()
        if not it:
            return
        if QMessageBox.question(self, "Borrar", "¿Borrar esta localización y sus puntos?") != QMessageBox.StandardButton.Yes:
            return
        con = connect()
        con.execute("DELETE FROM localizaciones WHERE id=?", (it.data(Qt.UserRole),))
        con.commit(); con.close()
        self.cargar(0)

    def ir_battlemap(self):
        if self.goto_battlemap:
            self.goto_battlemap()

    # ---------- página localización ----------
    def cargar_loc(self):
        con = connect()
        l = con.execute("SELECT * FROM localizaciones WHERE id=?", (self._loc_id,)).fetchone()
        pois = con.execute("SELECT p.*, 0 AS n FROM puntos_interes p WHERE p.localizacion_id=?",
                           (self._loc_id,)).fetchall()
        con.close()
        if not l:
            self.stack.setCurrentIndex(0)
            return
        self.lbl_loc.setText(f"{l['nombre']} ({l['tipo']})")
        img = l["imagen_path"] or ""
        self.canvas_loc.set_imagen(QPixmap(img) if img else QPixmap())
        self._pois = [dict(p) for p in pois]
        self.canvas_loc.set_pines([{"nombre": p["nombre"], "x": p["x"], "y": p["y"], "sel": False}
                                   for p in self._pois])
        self.canvas_loc.zoom_ajustar()
        self.lst_poi.clear()
        for p in self._pois:
            it = QListWidgetItem(f"📍 {p['nombre']}")
            it.setData(Qt.UserRole, p["id"])
            self.lst_poi.addItem(it)

    def poner_fondo_loc(self):
        if not self._loc_id:
            return
        ruta = self._fondo_dialogo("Mapa de la localización")
        if not ruta:
            return
        con = connect()
        con.execute("UPDATE localizaciones SET imagen_path=? WHERE id=?", (ruta, self._loc_id))
        con.commit(); con.close()
        self.cargar_loc()

    @staticmethod
    def _crear_battlemap(loc_id, nombre):
        con = connect()
        cur = con.execute(
            "INSERT INTO battlemaps(localizacion_id,nombre,ancho_celdas,alto_celdas,px_celda) VALUES(?,?,?,?,?)",
            (loc_id, nombre, 20, 14, 50))
        mid = cur.lastrowid
        con.commit(); con.close()
        return mid

    def crear_battlemap_aqui(self):
        if not self._loc_id:
            return
        nombre, ok = QInputDialog.getText(self, "Nuevo battlemap", "Nombre (ej. Taberna - planta baja):")
        if ok and nombre.strip():
            mid = self._crear_battlemap(self._loc_id, nombre.strip())
            self.cargar_loc()
            if self.goto_battlemap:
                self.goto_battlemap(mid)

    def _clic_vacio_loc(self, rx, ry):
        if self._modo_add != "poi" or not self._loc_id:
            return
        nombre, ok = QInputDialog.getText(self, "Nuevo punto de interés", "Nombre (ej. Taberna El Dragón):")
        if ok and nombre.strip():
            con = connect()
            con.execute("INSERT INTO puntos_interes(localizacion_id,nombre,x,y) VALUES(?,?,?,?)",
                        (self._loc_id, nombre.strip(), rx, ry))
            con.commit(); con.close()
            self._modo_add = None
            self.cargar_loc()

    def _clic_pin_loc(self, i):
        self.canvas_loc.marcar(i)
        for r in range(self.lst_poi.count()):
            if self.lst_poi.item(r).data(Qt.UserRole) == self._pois[i]["id"]:
                self.lst_poi.setCurrentRow(r)
        self._ver_poi(self._pois[i]["id"])

    def _ver_poi_item(self, item):
        self._ver_poi(item.data(Qt.UserRole))

    def _ver_poi(self, pid):
        con = connect()
        p = con.execute("SELECT * FROM puntos_interes WHERE id=?", (pid,)).fetchone()
        con.close()
        if not p:
            return
        self.det_poi.setText(
            f"<h3>{p['nombre']}</h3>"
            f"<p>{p['descripcion'] or 'Sin descripción.'}</p>"
            f"<p>{'🖼 Con imagen' if p['imagen_path'] else 'Sin imagen'}</p>")
        self._sel_poi = pid
        for i, pp in enumerate(self._pois):
            if pp["id"] == pid:
                self.canvas_loc.marcar(i)

    def entrar_poi(self):
        pid = getattr(self, "_sel_poi", None)
        if pid:
            self.entrar_poi_id(pid)

    def _entrar_poi_idx(self, i):
        self.entrar_poi_id(self._pois[i]["id"])

    def entrar_poi_id(self, pid):
        self._poi_id = pid
        self.cargar_poi()
        self.stack.setCurrentIndex(2)

    def borrar_poi(self):
        it = self.lst_poi.currentItem()
        if not it:
            return
        if QMessageBox.question(self, "Borrar", "¿Borrar este punto?") != QMessageBox.StandardButton.Yes:
            return
        con = connect()
        con.execute("DELETE FROM puntos_interes WHERE id=?", (it.data(Qt.UserRole),))
        con.commit(); con.close()
        self.cargar_loc()

    # ---------- página punto de interés ----------
    def cargar_poi(self):
        con = connect()
        p = con.execute("SELECT p.*, l.nombre AS loc FROM puntos_interes p "
                        "JOIN localizaciones l ON l.id=p.localizacion_id WHERE p.id=?",
                        (self._poi_id,)).fetchone()
        con.close()
        if not p:
            self._volver_loc()
            return
        self.lbl_poi.setText(f"{p['nombre']}  ·  {p['loc']}")
        img = p["imagen_path"] or ""
        self.canvas_poi.set_imagen(QPixmap(img) if img else QPixmap())
        self.canvas_poi.set_pines([])
        self.canvas_poi.zoom_ajustar()
        self.e_desc_poi.setPlainText(p["descripcion"] or "")

    def poner_fondo_poi(self):
        if not self._poi_id:
            return
        ruta = self._fondo_dialogo("Imagen del punto (mapa o foto)")
        if not ruta:
            return
        con = connect()
        con.execute("UPDATE puntos_interes SET imagen_path=? WHERE id=?", (ruta, self._poi_id))
        con.commit(); con.close()
        self.cargar_poi()

    def guardar_desc_poi(self):
        if not self._poi_id:
            return
        con = connect()
        con.execute("UPDATE puntos_interes SET descripcion=? WHERE id=?",
                    (self.e_desc_poi.toPlainText(), self._poi_id))
        con.commit(); con.close()
        self.cargar_loc()

    def borrar_poi_actual(self):
        if not self._poi_id:
            return
        if QMessageBox.question(self, "Borrar", "¿Borrar este punto?") != QMessageBox.StandardButton.Yes:
            return
        con = connect()
        con.execute("DELETE FROM puntos_interes WHERE id=?", (self._poi_id,))
        con.commit(); con.close()
        self._volver_loc()

    def _volver_loc(self):
        self.cargar_loc()
        self.stack.setCurrentIndex(1)
