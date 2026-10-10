"""CRUD Ciudades/Localizaciones + ver personajes y battlemaps asociados."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QFormLayout, QLineEdit, QComboBox, QTextEdit, QPushButton, QLabel
from PySide6.QtCore import Qt
from ..database import connect


class CiudadesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lst = QListWidget()
        self.nombre = QLineEdit()
        self.tipo = QComboBox(); self.tipo.addItems(["ciudad", "pueblo", "mazmorra", "punto_interes"])
        self.mapa = QComboBox()
        self.desc = QTextEdit(); self.desc.setMaximumHeight(120)
        self.script = QLineEdit(); self.script.setPlaceholderText("p. ej. nilgotia:llegada")
        self.rel = QLabel("—"); self.rel.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Nombre", self.nombre)
        form.addRow("Tipo", self.tipo)
        form.addRow("Mapa mundo", self.mapa)
        form.addRow("Descripción", self.desc)
        form.addRow("Guion (aventura)", self.script)
        form.addRow("Relacionado", self.rel)

        b_new = QPushButton("＋ Nueva"); b_save = QPushButton("💾 Guardar"); b_del = QPushButton("🗑 Borrar")
        btns = QHBoxLayout(); btns.addWidget(b_new); btns.addWidget(b_save); btns.addWidget(b_del)

        left = QVBoxLayout(); left.addWidget(QLabel("Ciudades / Localizaciones")); left.addWidget(self.lst, 1); left.addLayout(btns)
        right = QVBoxLayout(); right.addLayout(form)
        main = QHBoxLayout(self); main.addLayout(left, 1); main.addLayout(right, 2)

        self.lst.currentItemChanged.connect(self._load)
        b_new.clicked.connect(self.nueva); b_save.clicked.connect(self.guardar); b_del.clicked.connect(self.borrar)
        self.refresh()

    def refresh(self):
        con = connect()
        rows = con.execute("SELECT l.*, m.nombre mname FROM localizaciones l LEFT JOIN mapas_mundo m ON m.id=l.mapa_mundo_id ORDER BY l.nombre").fetchall()
        mapas = con.execute("SELECT id,nombre FROM mapas_mundo").fetchall()
        con.close()
        self.mapa.blockSignals(True)
        self.mapa.clear()
        for m in mapas:
            self.mapa.addItem(m["nombre"], m["id"])
        self.mapa.blockSignals(False)
        self.lst.blockSignals(True); self.lst.clear()
        for r in rows:
            it = QListWidgetItem(f"{r['nombre']} ({r['mname'] or '?'})")
            it.setData(Qt.UserRole, r["id"])
            self.lst.addItem(it)
        self.lst.blockSignals(False)
        if rows and not self.lst.currentItem():
            self.lst.setCurrentRow(0)

    def _load(self, cur, prev):
        if not cur: return
        con = connect()
        l = con.execute("SELECT * FROM localizaciones WHERE id=?", (cur.data(Qt.UserRole),)).fetchone()
        pers = con.execute("SELECT nombre FROM personajes WHERE localizacion_id=?", (l["id"],)).fetchall()
        bms = con.execute("SELECT id,nombre FROM battlemaps WHERE localizacion_id=?", (l["id"],)).fetchall()
        con.close()
        self.nombre.setText(l["nombre"])
        self.tipo.setCurrentText(l["tipo"])
        for i in range(self.mapa.count()):
            if self.mapa.itemData(i) == l["mapa_mundo_id"]:
                self.mapa.setCurrentIndex(i)
        self.desc.setPlainText(l["descripcion"] or "")
        self.script.setText(l["script"] or "")
        self.rel.setText(f"👥 {len(pers)} personajes: " + (", ".join(p['nombre'] for p in pers) or "—") +
                         f"\n⚔ {len(bms)} battlemaps: " + (", ".join(b['nombre'] for b in bms) or "—"))

    def nueva(self):
        con = connect()
        m = con.execute("SELECT id FROM mapas_mundo LIMIT 1").fetchone()
        con.execute("INSERT INTO localizaciones(mapa_mundo_id,nombre,tipo) VALUES(?,?,?)",
                    (m["id"] if m else None, "Nueva ciudad", "ciudad"))
        con.commit(); con.close(); self.refresh()

    def guardar(self):
        cur = self.lst.currentItem()
        if not cur: return
        con = connect()
        con.execute("UPDATE localizaciones SET nombre=?,tipo=?,mapa_mundo_id=?,descripcion=?,script=? WHERE id=?",
                    (self.nombre.text().strip(), self.tipo.currentText(), self.mapa.currentData(),
                     self.desc.toPlainText(), self.script.text().strip(), cur.data(Qt.UserRole)))
        con.commit(); con.close(); self.refresh()

    def borrar(self):
        cur = self.lst.currentItem()
        if not cur: return
        con = connect()
        con.execute("DELETE FROM localizaciones WHERE id=?", (cur.data(Qt.UserRole),))
        con.commit(); con.close(); self.refresh()
