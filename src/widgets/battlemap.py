"""Battlemap: cuadrícula + fondo + tokens + niebla de guerra + medición + iniciativa."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpinBox,
    QFileDialog, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsLineItem,
    QGraphicsTextItem, QComboBox, QMessageBox, QLineEdit, QListWidget,
    QListWidgetItem, QCheckBox, QInputDialog
)
from PySide6.QtGui import QPen, QBrush, QColor, QPixmap, QPainter, QFont
from PySide6.QtCore import Qt, QRectF
from ..database import connect, MAPAS_DIR

PIES_POR_CASILLA = 5  # regla 2024 simplificada


class TokenItem(QGraphicsEllipseItem):
    def __init__(self, pid, nombre, color, celda):
        r = celda * 0.42
        super().__init__(-r, -r, r * 2, r * 2)
        self.pid = pid  # puede ser None = token temporal no guardado en BD
        self.nombre = nombre
        self.setBrush(QBrush(QColor(color or "#e74c3c")))
        self.setPen(QPen(Qt.black, 2))
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setZValue(10)
        self.setToolTip(nombre)
        self._celda = celda

    def cell_pos(self):
        p = self.scenePos()
        return (round(p.x() / self._celda), round(p.y() / self._celda))


class BattleView(QGraphicsView):
    """QGraphicsView que delega clics al widget padre según el modo activo."""
    def __init__(self, scene, owner):
        super().__init__(scene, owner)
        self.owner = owner
        self.setRenderHint(QPainter.Antialiasing)

    def mousePressEvent(self, ev):
        mode = self.owner._mode
        if mode in ("niebla_add", "niebla_del", "medir"):
            pos = self.mapToScene(ev.pos())
            if mode == "niebla_add":
                self.owner.pintar_niebla_en(pos)
            elif mode == "niebla_del":
                self.owner.borrar_niebla_en(pos)
            elif mode == "medir":
                self.owner.medir_click(pos)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        mode = self.owner._mode
        if mode in ("niebla_add", "niebla_del") and (ev.buttons() & Qt.LeftButton):
            pos = self.mapToScene(ev.pos())
            if mode == "niebla_add":
                self.owner.pintar_niebla_en(pos)
            else:
                self.owner.borrar_niebla_en(pos)
            ev.accept()
            return
        super().mouseMoveEvent(ev)


class BattleMapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = BattleView(self.scene, self)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        # estado
        self._mode = "mover"
        self._battlemap_id = None
        self._bg_path = ""
        self._fog: set[tuple[int, int]] = set()
        self._fog_items: dict[tuple[int, int], QGraphicsRectItem] = {}
        self._measure_pts: list = []
        self._measure_items: list = []
        self._ini: list[dict] = []  # {pid, nombre, mod, init}
        self._ini_idx = 0
        self._ini_round = 1

        # --- controles superiores ---
        self.cmb_maps = QComboBox()
        self.spin_w = QSpinBox(); self.spin_w.setRange(5, 60); self.spin_w.setValue(20)
        self.spin_h = QSpinBox(); self.spin_h.setRange(5, 60); self.spin_h.setValue(14)
        self.spin_px = QSpinBox(); self.spin_px.setRange(20, 120); self.spin_px.setValue(50)
        self.txt_nombre = QLineEdit(); self.txt_nombre.setPlaceholderText("Nombre del battlemap")
        self.cmb_token = QComboBox()
        self.lbl_info = QLabel("Modo Mover: arrastra tokens. Niebla: clic/arrastrar para pintar.")
        self.lbl_info.setWordWrap(True)

        top = QHBoxLayout()
        top.addWidget(QLabel("Mapa:"))
        top.addWidget(self.cmb_maps, 2)
        top.addWidget(QLabel("Nombre:"))
        top.addWidget(self.txt_nombre, 1)
        top.addWidget(QLabel("Ancho:"))
        top.addWidget(self.spin_w)
        top.addWidget(QLabel("Alto:"))
        top.addWidget(self.spin_h)
        top.addWidget(QLabel("px/celda:"))
        top.addWidget(self.spin_px)

        row1 = QHBoxLayout()
        b_new = QPushButton("+ Nuevo")
        b_bg = QPushButton("Fondo...")
        b_grid = QPushButton("Redibujar")
        b_add = QPushButton("Colocar personaje")
        b_add_tmp = QPushButton("Token temporal")
        b_save = QPushButton("Guardar todo")
        b_del = QPushButton("Borrar mapa")
        for b in (b_new, b_bg, b_grid, b_add, b_add_tmp, b_save, b_del):
            row1.addWidget(b)
        row1.addWidget(self.cmb_token, 1)

        # --- barra de herramientas: modos ---
        row2 = QHBoxLayout()
        self.b_move = QPushButton("Mover"); self.b_move.setCheckable(True); self.b_move.setChecked(True)
        self.b_fog = QPushButton("Pintar niebla"); self.b_fog.setCheckable(True)
        self.b_unfog = QPushButton("Borrar niebla"); self.b_unfog.setCheckable(True)
        self.b_meas = QPushButton("Medir"); self.b_meas.setCheckable(True)
        self.chk_fog = QCheckBox("Niebla visible"); self.chk_fog.setChecked(True)
        self.chk_dm = QCheckBox("DM ver a traves"); self.chk_dm.setChecked(True)
        b_clear_fog = QPushButton("Limpiar niebla")
        b_clear_meas = QPushButton("Limpiar medida")
        for b in (self.b_move, self.b_fog, self.b_unfog, self.b_meas):
            row2.addWidget(b)
        row2.addWidget(self.chk_fog)
        row2.addWidget(self.chk_dm)
        row2.addWidget(b_clear_fog)
        row2.addWidget(b_clear_meas)
        row2.addWidget(self.lbl_info, 1)

        # --- panel iniciativa ---
        self.ini_list = QListWidget(); self.ini_list.setMinimumWidth(240); self.ini_list.setMaximumWidth(320)
        self.lbl_round = QLabel("Ronda 1 - sin combate")
        bi1 = QHBoxLayout()
        b_ini_load = QPushButton("Cargar tokens")
        b_ini_roll = QPushButton("Tirar init.")
        bi1.addWidget(b_ini_load); bi1.addWidget(b_ini_roll)
        bi2 = QHBoxLayout()
        b_ini_sort = QPushButton("Ordenar")
        b_ini_next = QPushButton("Siguiente >>")
        bi2.addWidget(b_ini_sort); bi2.addWidget(b_ini_next)
        bi3 = QHBoxLayout()
        b_ini_add = QPushButton("Anadir")
        b_ini_del = QPushButton("Quitar")
        b_ini_rst = QPushButton("Reset")
        bi3.addWidget(b_ini_add); bi3.addWidget(b_ini_del); bi3.addWidget(b_ini_rst)

        side = QVBoxLayout()
        side.addWidget(QLabel("<b>Iniciativa</b> (d20 + mod DES)"))
        side.addWidget(self.lbl_round)
        side.addWidget(self.ini_list, 1)
        side.addLayout(bi1); side.addLayout(bi2); side.addLayout(bi3)
        side.addWidget(QLabel("Doble clic en un token lo quita del mapa."))
        sideW = QWidget(); sideW.setLayout(side); sideW.setMinimumWidth(260); sideW.setMaximumWidth(340)

        mid = QHBoxLayout()
        mid.addWidget(self.view, 3)
        mid.addWidget(sideW, 1)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(row1)
        lay.addLayout(row2)
        lay.addLayout(mid, 1)

        b_new.clicked.connect(self.crear_mapa)
        b_bg.clicked.connect(self.poner_fondo)
        b_grid.clicked.connect(self.redibujar)
        b_add.clicked.connect(self.colocar_token)
        b_add_tmp.clicked.connect(self.colocar_temporal)
        b_save.clicked.connect(self.guardar_todo)
        b_del.clicked.connect(self.borrar_mapa)
        self.cmb_maps.currentIndexChanged.connect(self.cargar_mapa)

        self.b_move.clicked.connect(lambda: self.set_modo("mover"))
        self.b_fog.clicked.connect(lambda: self.set_modo("niebla_add"))
        self.b_unfog.clicked.connect(lambda: self.set_modo("niebla_del"))
        self.b_meas.clicked.connect(lambda: self.set_modo("medir"))
        self.chk_fog.stateChanged.connect(self._aplicar_visibilidad_niebla)
        self.chk_dm.stateChanged.connect(self._aplicar_visibilidad_niebla)
        b_clear_fog.clicked.connect(self.limpiar_niebla)
        b_clear_meas.clicked.connect(self.limpiar_medida)

        b_ini_load.clicked.connect(self.ini_cargar)
        b_ini_roll.clicked.connect(self.ini_tirar)
        b_ini_sort.clicked.connect(self.ini_ordenar)
        b_ini_next.clicked.connect(self.ini_siguiente)
        b_ini_add.clicked.connect(self.ini_anadir)
        b_ini_del.clicked.connect(self.ini_quitar)
        b_ini_rst.clicked.connect(self.ini_reset)

        self.refrescar_listas()

    # ============ modos ============
    def set_modo(self, modo):
        self._mode = modo
        for b, m in ((self.b_move, "mover"), (self.b_fog, "niebla_add"),
                     (self.b_unfog, "niebla_del"), (self.b_meas, "medir")):
            b.blockSignals(True); b.setChecked(m == modo); b.blockSignals(False)
        if modo == "mover":
            self.view.setDragMode(QGraphicsView.ScrollHandDrag)
            self.lbl_info.setText("Modo Mover: arrastra tokens con el raton.")
        elif modo == "niebla_add":
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.lbl_info.setText("Niebla: clic o arrastra para TAPAR celdas. Luego pulsa Guardar todo.")
        elif modo == "niebla_del":
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.lbl_info.setText("Goma: clic o arrastra para DESTAPAR celdas.")
        else:
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.lbl_info.setText("Medir: clic en 2 celdas. Regla 2024: 1 casilla = 5 pies.")

    # ============ datos / escena ============
    def refrescar_listas(self):
        actual = self._battlemap_id
        con = connect()
        maps = con.execute(
            "SELECT b.id, b.nombre, l.nombre loc FROM battlemaps b LEFT JOIN localizaciones l ON l.id=b.localizacion_id"
        ).fetchall()
        pers = con.execute("SELECT id, nombre FROM personajes ORDER BY nombre").fetchall()
        con.close()
        self.cmb_maps.blockSignals(True)
        self.cmb_maps.clear()
        sel = 0
        for i, m in enumerate(maps):
            self.cmb_maps.addItem(f"{m['nombre']} ({m['loc'] or 'sin ciudad'})", m["id"])
            if actual is not None and m["id"] == actual:
                sel = i
        self.cmb_maps.blockSignals(False)
        self.cmb_token.clear()
        for p in pers:
            self.cmb_token.addItem(p["nombre"], p["id"])
        if maps:
            if actual is None:
                self.cargar_mapa(0)
            else:
                self.cmb_maps.blockSignals(True)
                self.cmb_maps.setCurrentIndex(sel)
                self.cmb_maps.blockSignals(False)

    def mapa_actual(self):
        i = self.cmb_maps.currentIndex()
        return self.cmb_maps.itemData(i) if i >= 0 else None

    def seleccionar(self, mid):
        for i in range(self.cmb_maps.count()):
            if self.cmb_maps.itemData(i) == mid:
                self.cmb_maps.setCurrentIndex(i)
                return
        self._battlemap_id = None
        self.refrescar_listas()
        for i in range(self.cmb_maps.count()):
            if self.cmb_maps.itemData(i) == mid:
                self.cmb_maps.setCurrentIndex(i)

    def cargar_mapa(self, idx):
        mid = self.mapa_actual()
        if not mid:
            return
        con = connect()
        b = con.execute("SELECT * FROM battlemaps WHERE id=?", (mid,)).fetchone()
        toks = con.execute("SELECT id,nombre,token_x,token_y,color FROM personajes WHERE battlemap_id=?", (mid,)).fetchall()
        try:
            fog = con.execute("SELECT cx,cy FROM battlemap_fog WHERE battlemap_id=?", (mid,)).fetchall()
        except Exception:
            fog = []
        con.close()
        if b is None:
            return
        self._battlemap_id = mid
        self._bg_path = b["imagen_path"] or ""
        self.txt_nombre.setText(b["nombre"])
        self.spin_w.setValue(b["ancho_celdas"]); self.spin_h.setValue(b["alto_celdas"]); self.spin_px.setValue(b["px_celda"])
        self._fog = {(r["cx"], r["cy"]) for r in fog}
        self._measure_pts = []
        self._ini = []; self._ini_idx = 0; self._ini_round = 1
        self._reconstruir(toks)

    def _reconstruir(self, toks=None):
        self.scene.clear()
        self._fog_items = {}
        self._measure_items = []
        w, h, px = self.spin_w.value(), self.spin_h.value(), self.spin_px.value()
        if self._bg_path:
            pm = QPixmap(self._bg_path)
            if not pm.isNull():
                pm = pm.scaled(w * px, h * px, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                bg = QGraphicsPixmapItem(pm)
                bg.setPos(0, 0); bg.setZValue(-10)
                self.scene.addItem(bg)
        pen = QPen(QColor(0, 0, 0, 90), 1)
        for x in range(w + 1):
            self.scene.addLine(x * px, 0, x * px, h * px, pen)
        for y in range(h + 1):
            self.scene.addLine(0, y * px, w * px, y * px, pen)
        borde = QGraphicsRectItem(QRectF(0, 0, w * px, h * px))
        borde.setPen(QPen(Qt.black, 2))
        self.scene.addItem(borde)
        self.scene.setSceneRect(0, 0, w * px, h * px)
        # tokens
        if toks is None and self._battlemap_id:
            con = connect()
            toks = con.execute("SELECT id,nombre,token_x,token_y,color FROM personajes WHERE battlemap_id=?",
                               (self._battlemap_id,)).fetchall()
            con.close()
        for t in (toks or []):
            tok = TokenItem(t["id"], t["nombre"], t["color"], px)
            tok.setPos(t["token_x"] * px, t["token_y"] * px)
            self.scene.addItem(tok)
        # niebla
        for cx, cy in self._fog:
            self._dibujar_celda_niebla(cx, cy)
        self._aplicar_visibilidad_niebla()
        self._pintar_ini()

    def redibujar(self):
        self._reconstruir()

    # ============ niebla ============
    def _celda_de(self, scene_pos):
        px = self.spin_px.value()
        cx, cy = int(scene_pos.x() // px), int(scene_pos.y() // px)
        if 0 <= cx < self.spin_w.value() and 0 <= cy < self.spin_h.value():
            return (cx, cy)
        return None

    def _dibujar_celda_niebla(self, cx, cy):
        if (cx, cy) in self._fog_items:
            return
        px = self.spin_px.value()
        r = QGraphicsRectItem(cx * px, cy * px, px, px)
        r.setBrush(QBrush(QColor(0, 0, 0, 210)))
        r.setPen(QPen(QColor(0, 0, 0, 0)))
        r.setZValue(20)
        self.scene.addItem(r)
        self._fog_items[(cx, cy)] = r

    def pintar_niebla_en(self, scene_pos):
        c = self._celda_de(scene_pos)
        if c and c not in self._fog:
            self._fog.add(c)
            self._dibujar_celda_niebla(*c)
            self._aplicar_visibilidad_niebla()

    def borrar_niebla_en(self, scene_pos):
        c = self._celda_de(scene_pos)
        if c and c in self._fog:
            self._fog.discard(c)
            it = self._fog_items.pop(c, None)
            if it:
                self.scene.removeItem(it)

    def limpiar_niebla(self):
        self._fog.clear()
        for it in list(self._fog_items.values()):
            self.scene.removeItem(it)
        self._fog_items.clear()

    def _aplicar_visibilidad_niebla(self):
        vis = self.chk_fog.isChecked()
        dm = self.chk_dm.isChecked()
        for it in self._fog_items.values():
            it.setVisible(vis)
            it.setOpacity(0.35 if dm else 0.92)

    # ============ medición ============
    def medir_click(self, scene_pos):
        c = self._celda_de(scene_pos)
        if not c:
            return
        px = self.spin_px.value()
        centro = (c[0] * px + px / 2, c[1] * px + px / 2)
        self._measure_pts.append(centro)
        # punto visual
        dot = QGraphicsEllipseItem(centro[0] - 5, centro[1] - 5, 10, 10)
        dot.setBrush(QBrush(QColor("#d4af37"))); dot.setPen(QPen(Qt.black, 1)); dot.setZValue(30)
        self.scene.addItem(dot); self._measure_items.append(dot)
        if len(self._measure_pts) == 2:
            (x1, y1), (x2, y2) = self._measure_pts
            line = QGraphicsLineItem(x1, y1, x2, y2)
            line.setPen(QPen(QColor("#d4af37"), 3)); line.setZValue(30)
            self.scene.addItem(line); self._measure_items.append(line)
            dx = round((x2 - x1) / px); dy = round((y2 - y1) / px)
            cheb = max(abs(dx), abs(dy))
            pies = cheb * PIES_POR_CASILLA
            import math
            eu = math.hypot(x2 - x1, y2 - y1) / px * PIES_POR_CASILLA
            txt = QGraphicsTextItem(f"{cheb} cas · {pies} pies (2024)\n~{eu:.0f} pies en linea")
            txt.setDefaultTextColor(QColor("#d4af37"))
            txt.setFont(QFont("Segoe UI", 11, QFont.Bold))
            txt.setPos((x1 + x2) / 2 + 8, (y1 + y2) / 2 + 8)
            txt.setZValue(31)
            self.scene.addItem(txt); self._measure_items.append(txt)
            self.lbl_info.setText(f"Medida: dx={dx} dy={dy} -> {cheb} casillas = {pies} pies.")
            self._measure_pts = []

    def limpiar_medida(self):
        for it in self._measure_items:
            try:
                self.scene.removeItem(it)
            except Exception:
                pass
        self._measure_items = []; self._measure_pts = []

    # ============ tokens / guardado ============
    def crear_mapa(self):
        nombre = self.txt_nombre.text().strip() or "Nuevo battlemap"
        con = connect()
        loc = con.execute("SELECT id FROM localizaciones LIMIT 1").fetchone()
        loc_id = loc["id"] if loc else None
        cur = con.execute(
            "INSERT INTO battlemaps(localizacion_id,nombre,ancho_celdas,alto_celdas,px_celda) VALUES(?,?,?,?,?)",
            (loc_id, nombre, self.spin_w.value(), self.spin_h.value(), self.spin_px.value()))
        con.commit(); mid = cur.lastrowid; con.close()
        self._battlemap_id = None
        self.refrescar_listas()
        for i in range(self.cmb_maps.count()):
            if self.cmb_maps.itemData(i) == mid:
                self.cmb_maps.setCurrentIndex(i)
                self.cargar_mapa(i)

    def poner_fondo(self):
        from ..arte import normalizar_fondo
        inicio = str(MAPAS_DIR) if MAPAS_DIR.exists() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Imagen de fondo", inicio, "Imagenes (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        ruta = normalizar_fondo(path)
        if not ruta:
            QMessageBox.warning(self, "Fondo", f"No pude leer esa imagen:\n{path}")
            return
        self._bg_path = ruta
        self._reconstruir()

    def colocar_token(self):
        if not self._battlemap_id:
            QMessageBox.warning(self, "Sin mapa", "Crea o selecciona un battlemap primero.")
            return
        i = self.cmb_token.currentIndex()
        if i < 0:
            return
        pid = self.cmb_token.itemData(i)
        nombre = self.cmb_token.currentText()
        con = connect()
        row = con.execute("SELECT color FROM personajes WHERE id=?", (pid,)).fetchone()
        con.close()
        px = self.spin_px.value()
        tok = TokenItem(pid, nombre, row["color"] if row else "#2ecc71", px)
        tok.setPos(2 * px, 2 * px)
        self.scene.addItem(tok)
        self.lbl_info.setText(f"{nombre} colocado. Pulsa Guardar todo.")

    def colocar_temporal(self):
        """Token gris para monstruos improvisados (no se guarda en BD)."""
        if not self._battlemap_id:
            QMessageBox.warning(self, "Sin mapa", "Crea o selecciona un battlemap primero.")
            return
        nombre, ok = QInputDialog.getText(self, "Token temporal", "Nombre (ej. Goblin 1):")
        if ok and nombre.strip():
            px = self.spin_px.value()
            tok = TokenItem(None, nombre.strip(), "#95a5a6", px)
            tok.setPos(3 * px, 3 * px)
            self.scene.addItem(tok)

    def guardar_todo(self):
        """Guarda dimensiones, fondo, posiciones de tokens y niebla."""
        if not self._battlemap_id:
            return
        px = self.spin_px.value()
        con = connect()
        con.execute("UPDATE battlemaps SET nombre=?, ancho_celdas=?, alto_celdas=?, px_celda=?, imagen_path=? WHERE id=?",
                    (self.txt_nombre.text().strip() or "Battlemap",
                     self.spin_w.value(), self.spin_h.value(), px, self._bg_path, self._battlemap_id))
        for item in self.scene.items():
            if isinstance(item, TokenItem) and item.pid is not None:
                cx, cy = round(item.scenePos().x() / px), round(item.scenePos().y() / px)
                con.execute("UPDATE personajes SET battlemap_id=?, token_x=?, token_y=? WHERE id=?",
                            (self._battlemap_id, cx, cy, item.pid))
        try:
            con.execute("DELETE FROM battlemap_fog WHERE battlemap_id=?", (self._battlemap_id,))
            con.executemany("INSERT OR IGNORE INTO battlemap_fog(battlemap_id,cx,cy) VALUES(?,?,?)",
                            [(self._battlemap_id, cx, cy) for cx, cy in self._fog])
        except Exception as e:
            QMessageBox.warning(self, "Niebla", f"No se pudo guardar la niebla (¿BD antigua?).\n{e}")
        con.commit(); con.close()
        self.lbl_info.setText(f"Guardado: tokens + {len(self._fog)} celdas de niebla.")
        self.refrescar_listas()

    def borrar_mapa(self):
        mid = self.mapa_actual()
        if not mid:
            return
        if QMessageBox.question(self, "Borrar", "Borrar este battlemap?") != QMessageBox.StandardButton.Yes:
            return
        con = connect()
        con.execute("DELETE FROM battlemaps WHERE id=?", (mid,))
        con.commit(); con.close()
        self._battlemap_id = None
        self.refrescar_listas()

    # ============ iniciativa ============
    def _tokens_en_escena(self):
        return [it for it in self.scene.items() if isinstance(it, TokenItem)]

    def ini_cargar(self):
        toks = self._tokens_en_escena()
        if not toks:
            QMessageBox.information(self, "Iniciativa", "No hay tokens en el mapa.")
            return
        pids = [t.pid for t in toks if t.pid is not None]
        mods = {}
        if pids:
            con = connect()
            q = f"SELECT id,destreza FROM personajes WHERE id IN ({','.join('?'*len(pids))})"
            for r in con.execute(q, pids).fetchall():
                mods[r["id"]] = (r["destreza"] - 10) // 2
            con.close()
        self._ini = []
        for t in toks:
            self._ini.append({"pid": t.pid, "nombre": t.nombre,
                              "mod": mods.get(t.pid, 0) if t.pid is not None else 0,
                              "init": None})
        self._ini_idx = 0; self._ini_round = 1
        self._pintar_ini()
        self.lbl_info.setText(f"{len(self._ini)} combatientes cargados. Pulsa Tirar init.")

    def ini_tirar(self):
        if not self._ini:
            self.ini_cargar()
            if not self._ini:
                return
        for e in self._ini:
            e["init"] = random.randint(1, 20) + e["mod"]
        self.ini_ordenar()

    def ini_ordenar(self):
        self._ini.sort(key=lambda e: (e["init"] is None, -(e["init"] or -99), -e["mod"]))
        self._ini_idx = 0
        self._pintar_ini()

    def ini_siguiente(self):
        if not self._ini:
            return
        self._ini_idx += 1
        if self._ini_idx >= len(self._ini):
            self._ini_idx = 0
            self._ini_round += 1
        self._pintar_ini()

    def ini_anadir(self):
        nombre, ok = QInputDialog.getText(self, "Anadir", "Nombre:")
        if ok and nombre.strip():
            self._ini.append({"pid": None, "nombre": nombre.strip(), "mod": 0, "init": 0})
            self._pintar_ini()

    def ini_quitar(self):
        r = self.ini_list.currentRow()
        if 0 <= r < len(self._ini):
            del self._ini[r]
            self._ini_idx = min(self._ini_idx, max(0, len(self._ini) - 1))
            self._pintar_ini()

    def ini_reset(self):
        self._ini = []; self._ini_idx = 0; self._ini_round = 1
        self._pintar_ini()

    def _pintar_ini(self):
        self.ini_list.clear()
        if not self._ini:
            self.lbl_round.setText("Ronda 1 - sin combate")
            return
        for i, e in enumerate(self._ini):
            v = e["init"] if e["init"] is not None else "-"
            it = QListWidgetItem(f"{'>> ' if i == self._ini_idx else '     '}{v:>3}  {e['nombre']} (DES {e['mod']:+d})")
            if i == self._ini_idx:
                it.setBackground(QColor("#4a0d0d"))
            self.ini_list.addItem(it)
        self.ini_list.setCurrentRow(self._ini_idx)
        turno = self._ini[self._ini_idx]["nombre"] if self._ini else "-"
        self.lbl_round.setText(f"Ronda {self._ini_round} - turno: {turno}")
