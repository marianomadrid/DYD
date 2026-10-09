"""CRUD Personajes correlacionado con ciudades, battlemaps y fichas PDF."""
import json
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QFormLayout,
    QLineEdit, QSpinBox, QComboBox, QPushButton, QTextEdit, QLabel, QMessageBox,
    QFileDialog
)
from PySide6.QtCore import Qt
from ..database import (connect, BASE, PERSONAJES_DIR, buscar_pdf,
                        buscar_retrato)
from ..pdf_import import parse_ficha_pdf

COLORES = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22"]


class PersonajesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lst = QListWidget()
        self.lst.currentItemChanged.connect(self._cargar_form)

        self.nombre = QLineEdit()
        self.clase = QComboBox(); self.clase.setEditable(True)
        self.clase.addItems(["Guerrero", "Mago", "Clérigo", "Pícaro", "Bardo", "Druida", "Paladín", "Explorador", "Brujo", "Hechicero", "Monje", "Bárbaro"])
        self.especie = QComboBox(); self.especie.setEditable(True)
        self.especie.addItems(["Humano", "Elfo", "Enano", "Halfling", "Tiefling", "Orco", "Gnomo", "Dracónido"])
        self.nivel = QSpinBox(); self.nivel.setRange(1, 20)
        self.ca = QSpinBox(); self.ca.setRange(1, 30); self.ca.setValue(10)
        self.pg_a = QSpinBox(); self.pg_a.setRange(0, 999)
        self.pg_m = QSpinBox(); self.pg_m.setRange(1, 999); self.pg_m.setValue(10)
        self.stats = {}
        for s in ("FUE", "DES", "CON", "INT", "SAB", "CAR"):
            sp = QSpinBox(); sp.setRange(1, 30); sp.setValue(10)
            self.stats[s] = sp
        self.cmb_ciudad = QComboBox()
        self.cmb_mapa = QComboBox()
        self.cmb_color = QComboBox(); self.cmb_color.addItems(COLORES)
        self.notas = QTextEdit(); self.notas.setMaximumHeight(90)
        self.lbl_ficha = QLabel("Ficha PDF: ninguna vinculada.")
        self.lbl_ficha.setWordWrap(True)
        self._ficha = ""
        ficha_row = QHBoxLayout()
        b_link = QPushButton("Vincular PDF…")
        b_open = QPushButton("Abrir PDF")
        b_unlink = QPushButton("Quitar")
        ficha_row.addWidget(b_link); ficha_row.addWidget(b_open); ficha_row.addWidget(b_unlink)
        ficha_w = QWidget(); ficha_w.setLayout(ficha_row)
        b_link.clicked.connect(self.vincular_ficha)
        b_open.clicked.connect(self.abrir_ficha)
        b_unlink.clicked.connect(self.quitar_ficha)
        self.info = QLabel("Selecciona un personaje. Los cambios se guardan con el botón.")

        form = QFormLayout()
        form.addRow("Nombre", self.nombre)
        form.addRow("Clase (2024)", self.clase)
        form.addRow("Especie (2024)", self.especie)
        form.addRow("Nivel", self.nivel)
        form.addRow("CA", self.ca)
        form.addRow("PG actual / máx", self._pg_row())
        for s, sp in self.stats.items():
            form.addRow(s, sp)
        form.addRow("Ciudad actual", self.cmb_ciudad)
        form.addRow("Battlemap", self.cmb_mapa)
        form.addRow("Color token", self.cmb_color)
        form.addRow("Ficha PDF", self.lbl_ficha)
        form.addRow("", ficha_w)
        form.addRow("Notas", self.notas)

        btns = QHBoxLayout()
        b_new = QPushButton("＋ Nuevo")
        b_imp = QPushButton("⬆ Importar PDF…")
        b_imp.setToolTip("Crea un personaje automáticamente desde una ficha PDF")
        b_save = QPushButton("💾 Guardar")
        b_del = QPushButton("🗑 Borrar")
        btns.addWidget(b_new); btns.addWidget(b_imp)
        btns.addWidget(b_save); btns.addWidget(b_del)

        left = QVBoxLayout()
        left.addWidget(QLabel("Personajes"))
        left.addWidget(self.lst, 1)
        left.addLayout(btns)

        right = QVBoxLayout()
        right.addLayout(form)
        right.addWidget(self.info)

        main = QHBoxLayout(self)
        main.addLayout(left, 1)
        main.addLayout(right, 2)

        b_new.clicked.connect(self.nuevo)
        b_imp.clicked.connect(self.importar_pdf)
        b_save.clicked.connect(self.guardar)
        b_del.clicked.connect(self.borrar)
        self.refrescar()

    def _pg_row(self):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.pg_a); h.addWidget(QLabel("/")); h.addWidget(self.pg_m)
        return w

    def refrescar(self):
        con = connect()
        rows = con.execute("SELECT id,nombre,clase,nivel FROM personajes ORDER BY nombre").fetchall()
        ciudades = con.execute("SELECT id,nombre FROM localizaciones ORDER BY nombre").fetchall()
        mapas = con.execute("SELECT id,nombre FROM battlemaps ORDER BY nombre").fetchall()
        con.close()
        self.lst.blockSignals(True)
        self.lst.clear()
        for r in rows:
            it = QListWidgetItem(f"{r['nombre']} · {r['clase'] or '?'} nv{r['nivel']}")
            it.setData(Qt.UserRole, r["id"])
            self.lst.addItem(it)
        self.lst.blockSignals(False)
        self.cmb_ciudad.clear(); self.cmb_ciudad.addItem("— ninguna —", None)
        for c in ciudades:
            self.cmb_ciudad.addItem(c["nombre"], c["id"])
        self.cmb_mapa.clear(); self.cmb_mapa.addItem("— ninguno —", None)
        for m in mapas:
            self.cmb_mapa.addItem(m["nombre"], m["id"])
        if rows and not self.lst.currentItem():
            self.lst.setCurrentRow(0)

    def _cargar_form(self, cur, prev):
        if not cur:
            return
        pid = cur.data(Qt.UserRole)
        con = connect()
        p = con.execute("SELECT * FROM personajes WHERE id=?", (pid,)).fetchone()
        con.close()
        if not p:
            return
        self.nombre.setText(p["nombre"])
        self.clase.setCurrentText(p["clase"] or "")
        self.especie.setCurrentText(p["especie"] or "")
        self.nivel.setValue(p["nivel"]); self.ca.setValue(p["ca"])
        self.pg_a.setValue(p["pg_actual"]); self.pg_m.setValue(p["pg_max"])
        for k, col in (("FUE", "fuerza"), ("DES", "destreza"), ("CON", "constitucion"),
                       ("INT", "inteligencia"), ("SAB", "sabiduria"), ("CAR", "carisma")):
            self.stats[k].setValue(p[col])
        self._sel_combo(self.cmb_ciudad, p["localizacion_id"])
        self._sel_combo(self.cmb_mapa, p["battlemap_id"])
        self._sel_combo(self.cmb_color, p["color"], by_text=True)
        self.notas.setPlainText(p["notas"] or "")
        self._ficha = p["ficha_path"] if "ficha_path" in p.keys() else ""
        self._pintar_ficha()
        self.info.setText(f"id={p['id']} · token en ({p['token_x']},{p['token_y']}) · edítalo y pulsa Guardar.")

    # ---- ficha PDF (carpeta Personajes/) ----
    def _ruta_ficha(self):
        """Devuelve la ruta absoluta de la ficha vinculada, o '' si no existe."""
        if not self._ficha:
            return ""
        p = Path(self._ficha)
        if not p.is_absolute():
            p = BASE / p
        return str(p) if p.exists() else ""

    def _pintar_ficha(self):
        ruta = self._ruta_ficha()
        if ruta:
            self.lbl_ficha.setText(f"Ficha PDF: {Path(ruta).name}")
            return
        # autodetectar Personajes/<nombre>/ o Personajes/<nombre>.pdf sin vincular
        cand = buscar_pdf(self.nombre.text().strip())
        if cand:
            self.lbl_ficha.setText(f"Ficha PDF: detectado {Path(cand).name} (sin vincular). Pulsa Vincular PDF…")
        elif self._ficha:
            self.lbl_ficha.setText(f"Ficha PDF: no encontrada ({self._ficha}). Revincúlala.")
        else:
            self.lbl_ficha.setText("Ficha PDF: ninguna vinculada.")

    def vincular_ficha(self):
        cur = self.lst.currentItem()
        if not cur:
            return
        inicio = str(PERSONAJES_DIR) if PERSONAJES_DIR.exists() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Ficha de personaje", inicio, "PDF (*.pdf)")
        if not path:
            return
        try:
            rel = str(Path(path).relative_to(BASE))
        except ValueError:
            rel = path  # fuera del repo: guardar absoluta
        self._ficha = rel
        con = connect()
        con.execute("UPDATE personajes SET ficha_path=? WHERE id=?", (rel, cur.data(Qt.UserRole)))
        con.commit(); con.close()
        self._pintar_ficha()
        self.ofrecer_crear_desde_pdf(path, rel)

    @staticmethod
    def _resumen(d):
        return (f"{d['nombre']} · {d['clase'] or '?'} ({d['especie'] or '?'}) nv {d['nivel']}\n"
                f"CA {d['ca']} · PG {d['pg_max']} · "
                f"FUE {d['fuerza']} DES {d['destreza']} CON {d['constitucion']} "
                f"INT {d['inteligencia']} SAB {d['sabiduria']} CAR {d['carisma']}")

    def ofrecer_crear_desde_pdf(self, path, rel):
        """Tras vincular: parsea el PDF y ofrece crear el personaje automáticamente."""
        try:
            datos = parse_ficha_pdf(path)
        except Exception as e:
            QMessageBox.information(self, "PDF vinculado",
                                    f"Ficha vinculada, pero no pude leer sus datos:\n{e}")
            return
        r = QMessageBox.question(
            self, "Crear personaje",
            f"Datos detectados en el PDF:\n\n{self._resumen(datos)}\n\n"
            "¿Crear un personaje con estos datos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._crear_desde_datos(datos, rel)

    def importar_pdf(self):
        """Crear personaje desde PDF sin necesidad de tener uno seleccionado."""
        inicio = str(PERSONAJES_DIR) if PERSONAJES_DIR.exists() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Importar ficha", inicio, "PDF (*.pdf)")
        if not path:
            return
        try:
            datos = parse_ficha_pdf(path)
        except Exception as e:
            QMessageBox.warning(self, "Importar", f"No pude leer ese PDF:\n{e}")
            return
        try:
            rel = str(Path(path).relative_to(BASE))
        except ValueError:
            rel = path
        self._crear_desde_datos(datos, rel)

    def _crear_desde_datos(self, d, ficha_rel):
        con = connect()
        existente = con.execute("SELECT id FROM personajes WHERE nombre=?", (d["nombre"],)).fetchone()
        if existente:
            r = QMessageBox.question(
                self, "Duplicado",
                f"Ya existe '{d['nombre']}'.\n¿Actualizarlo con los datos del PDF?\n"
                "(Sí = actualizar, No = crear otro, Cancelar = nada)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel:
                con.close()
                return None
            if r == QMessageBox.StandardButton.Yes:
                self._volcar_datos(con, existente["id"], d, ficha_rel)
                con.commit(); con.close()
                self.refrescar()
                self._seleccionar(existente["id"])
                self.info.setText(f"'{d['nombre']}' actualizado desde el PDF.")
                return existente["id"]
        camp = con.execute("SELECT id FROM campanas LIMIT 1").fetchone()
        n = con.execute("SELECT COUNT(*) c FROM personajes").fetchone()["c"]
        cur = con.execute(
            """INSERT INTO personajes(campana_id,nombre,clase,especie,trasfondo,subclase,nivel,px,
               alineamiento,fuerza,destreza,constitucion,inteligencia,sabiduria,carisma,
               pg_actual,pg_temp,pg_max,dados_golpe,velocidad,tamano,inspiracion_heroica,
               mu_exitos,mu_fracasos,iniciativa_bono,ca,competencias,equipo,idiomas,
               herramientas,rasgos,rasgos_especie,dotes,skills,saves,notas,ficha_path,retrato_path,color)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (camp["id"] if camp else None, d["nombre"], d["clase"], d["especie"],
             d.get("trasfondo", ""), d.get("subclase", ""), d["nivel"], d.get("px", 0),
             d["alineamiento"], d["fuerza"], d["destreza"], d["constitucion"],
             d["inteligencia"], d["sabiduria"], d["carisma"], d["pg_actual"],
             d.get("pg_temp", 0), d["pg_max"], d.get("dados_golpe", ""),
             d.get("velocidad", 30), d.get("tamano", ""),
             d.get("inspiracion_heroica", 0), d.get("mu_exitos", 0),
             d.get("mu_fracasos", 0), d.get("iniciativa_bono", 0), d["ca"],
             d.get("competencias", ""), d.get("equipo", ""), d.get("idiomas", ""),
             d.get("herramientas", ""), d.get("rasgos", ""),
             d.get("rasgos_especie", ""), d.get("dotes", ""),
             json.dumps(d.get("skills", {}), ensure_ascii=False),
             json.dumps(d.get("saves", {})), d.get("notas", ""),
             ficha_rel, d.get("retrato_path", ""), COLORES[n % len(COLORES)]))
        pid = cur.lastrowid
        self._volcar_armas(con, pid, d.get("armas", []))
        con.commit(); con.close()
        self.refrescar()
        self._seleccionar(pid)
        self.info.setText(f"'{d['nombre']}' creado desde el PDF.")
        return pid

    @staticmethod
    def _volcar_datos(con, pid, d, ficha_rel):
        con.execute("""UPDATE personajes SET clase=?,especie=?,trasfondo=?,subclase=?,nivel=?,px=?,
            alineamiento=?,fuerza=?,destreza=?,constitucion=?,inteligencia=?,sabiduria=?,carisma=?,
            pg_actual=?,pg_temp=?,pg_max=?,dados_golpe=?,velocidad=?,tamano=?,inspiracion_heroica=?,
            mu_exitos=?,mu_fracasos=?,iniciativa_bono=?,ca=?,competencias=?,equipo=?,idiomas=?,
            herramientas=?,rasgos=?,rasgos_especie=?,dotes=?,skills=?,saves=?,notas=?,ficha_path=?
            WHERE id=?""",
            (d["clase"], d["especie"], d.get("trasfondo", ""), d.get("subclase", ""),
             d["nivel"], d.get("px", 0), d["alineamiento"], d["fuerza"], d["destreza"],
             d["constitucion"], d["inteligencia"], d["sabiduria"], d["carisma"],
             d["pg_actual"], d.get("pg_temp", 0), d["pg_max"], d.get("dados_golpe", ""),
             d.get("velocidad", 30), d.get("tamano", ""),
             d.get("inspiracion_heroica", 0), d.get("mu_exitos", 0),
             d.get("mu_fracasos", 0), d.get("iniciativa_bono", 0), d["ca"],
             d.get("competencias", ""), d.get("equipo", ""), d.get("idiomas", ""),
             d.get("herramientas", ""), d.get("rasgos", ""), d.get("rasgos_especie", ""),
             d.get("dotes", ""), json.dumps(d.get("skills", {}), ensure_ascii=False),
             json.dumps(d.get("saves", {})), d.get("notas", ""), ficha_rel, pid))
        con.execute("DELETE FROM armas WHERE personaje_id=?", (pid,))
        PersonajesView._volcar_armas(con, pid, d.get("armas", []))

    @staticmethod
    def _volcar_armas(con, pid, armas):
        for a in armas:
            if a.get("nombre", "").strip():
                con.execute("INSERT INTO armas(personaje_id,nombre,atk,dano,notas) VALUES(?,?,?,?,?)",
                            (pid, a["nombre"].strip(), a.get("atk", "").strip(),
                             a.get("dano", "").strip(), a.get("notas", "").strip()))

    def _seleccionar(self, pid):
        for i in range(self.lst.count()):
            if self.lst.item(i).data(Qt.UserRole) == pid:
                self.lst.setCurrentRow(i)
                return

    def abrir_ficha(self):
        # si hay autodetección sin vincular, vincularla al abrir
        if not self._ruta_ficha():
            cand = buscar_pdf(self.nombre.text().strip())
            if cand:
                self._ficha = cand
                cur = self.lst.currentItem()
                if cur:
                    con = connect()
                    con.execute("UPDATE personajes SET ficha_path=? WHERE id=?",
                                (self._ficha, cur.data(Qt.UserRole)))
                    con.commit(); con.close()
        ruta = self._ruta_ficha()
        if not ruta:
            QMessageBox.information(self, "Ficha", "No hay ficha vinculada. Copia el PDF a la carpeta Personajes/ y vincúlalo.")
            return
        try:
            os.startfile(ruta)  # Windows: abre con el lector predeterminado
        except Exception:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    def quitar_ficha(self):
        cur = self.lst.currentItem()
        if not cur:
            return
        self._ficha = ""
        con = connect()
        con.execute("UPDATE personajes SET ficha_path='' WHERE id=?", (cur.data(Qt.UserRole),))
        con.commit(); con.close()
        self._pintar_ficha()

    def _sel_combo(self, cmb, val, by_text=False):
        for i in range(cmb.count()):
            d = cmb.itemText(i) if by_text else cmb.itemData(i)
            if d == val:
                cmb.setCurrentIndex(i); return
        cmb.setCurrentIndex(0)

    def nuevo(self):
        con = connect()
        camp = con.execute("SELECT id FROM campanas LIMIT 1").fetchone()
        cur = con.execute("INSERT INTO personajes(campana_id,nombre,clase,especie) VALUES(?,?,?,?)",
                          (camp["id"] if camp else None, "Nuevo héroe", "Guerrero", "Humano"))
        con.commit(); con.close()
        self.refrescar()

    def guardar(self):
        cur = self.lst.currentItem()
        if not cur:
            return
        pid = cur.data(Qt.UserRole)
        con = connect()
        con.execute("""UPDATE personajes SET nombre=?,clase=?,especie=?,nivel=?,ca=?,pg_actual=?,pg_max=?,
            fuerza=?,destreza=?,constitucion=?,inteligencia=?,sabiduria=?,carisma=?,
            localizacion_id=?,battlemap_id=?,color=?,notas=?,ficha_path=? WHERE id=?""",
            (self.nombre.text().strip() or "Sin nombre", self.clase.currentText(), self.especie.currentText(),
             self.nivel.value(), self.ca.value(), self.pg_a.value(), self.pg_m.value(),
             self.stats["FUE"].value(), self.stats["DES"].value(), self.stats["CON"].value(),
             self.stats["INT"].value(), self.stats["SAB"].value(), self.stats["CAR"].value(),
             self.cmb_ciudad.currentData(), self.cmb_mapa.currentData(),
             self.cmb_color.currentText(), self.notas.toPlainText(), self._ficha, pid))
        con.commit(); con.close()
        self.refrescar()

    def borrar(self):
        cur = self.lst.currentItem()
        if not cur:
            return
        if QMessageBox.question(self, "Borrar", "¿Borrar personaje?") != QMessageBox.Yes:
            return
        con = connect()
        con.execute("DELETE FROM personajes WHERE id=?", (cur.data(Qt.UserRole),))
        con.commit(); con.close()
        self.refrescar()
