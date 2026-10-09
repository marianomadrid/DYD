"""Ficha de personaje con la disposición de la hoja oficial 2024.

Posicionamiento espejo del PDF: cabecera arriba; a la izquierda las tarjetas
FUE/DES/CON, en el centro INT/SAB/CAR (cada una con modificador grande,
puntuación, salvación y habilidades); a la derecha armas y rasgos; abajo
competencias, herramientas, idiomas y equipo. Los modificadores se calculan
en vivo: mod = (puntuación-10)//2, hab. = mod + PB×nivel_competencia.
"""
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QSpinBox, QComboBox, QCheckBox, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QMessageBox,
    QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from ..database import connect, BASE, RETRATOS_DIR, importar_archivo, buscar_retrato, buscar_pdf
from ..pdf_import import (HABILIDADES, CARACTERISTICAS, NOMBRE_CAR,
                          bono_competencia, mod_car)

COMP_OPTS = ["—", "C", "E"]  # 0 nada, 1 competente, 2 pericia


class FichaView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pid = None
        self._updating = False

        # --- barra superior ---
        self.cmb = QComboBox(); self.cmb.setMinimumWidth(220)
        b_save = QPushButton("💾 Guardar ficha")
        b_open = QPushButton("Abrir PDF")
        self.lbl_pb = QLabel()
        self.lbl_pb.setFont(QFont("Segoe UI", 11, QFont.Bold))
        top = QHBoxLayout()
        top.addWidget(QLabel("Personaje:"))
        top.addWidget(self.cmb)
        top.addWidget(b_save)
        top.addWidget(b_open)
        top.addStretch(1)
        top.addWidget(self.lbl_pb)

        # --- cabecera estilo PDF ---
        self.e_nombre = QLineEdit()
        self.e_trasfondo = QLineEdit()
        self.e_clase = QLineEdit()
        self.e_especie = QLineEdit()
        self.e_subclase = QLineEdit()
        self.s_nivel = QSpinBox(); self.s_nivel.setRange(1, 20)
        self.s_px = QSpinBox(); self.s_px.setRange(0, 999999)
        self.s_ca = QSpinBox(); self.s_ca.setRange(1, 30)
        self.s_pg = QSpinBox(); self.s_pg.setRange(0, 9999)
        self.s_temp = QSpinBox(); self.s_temp.setRange(0, 9999)
        self.s_max = QSpinBox(); self.s_max.setRange(1, 9999)
        self.e_dados = QLineEdit(); self.e_dados.setPlaceholderText("9d8")
        self.s_vel = QSpinBox(); self.s_vel.setRange(0, 300)
        self.e_tam = QLineEdit()
        self.s_inib = QSpinBox(); self.s_inib.setRange(-10, 20)
        self.lbl_ini = QLabel(); self.lbl_ini.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_pp = QLabel()
        self.e_alin = QLineEdit()
        self.c_hero = QCheckBox("Inspiración heroica")
        self.s_mue = QSpinBox(); self.s_mue.setRange(0, 3)
        self.s_muf = QSpinBox(); self.s_muf.setRange(0, 3)

        head = QGridLayout()
        for c, (txt, w) in enumerate([("NOMBRE", self.e_nombre), ("TRASFONDO", self.e_trasfondo),
                                      ("CLASE", self.e_clase), ("ESPECIE", self.e_especie),
                                      ("SUBCLASE", self.e_subclase), ("NIVEL", self.s_nivel),
                                      ("PX", self.s_px)]):
            head.addWidget(QLabel(f"<small>{txt}</small>"), 0, c)
            head.addWidget(w, 1, c)
        for c, (txt, w) in enumerate([("CA", self.s_ca), ("PG ACTUAL", self.s_pg),
                                      ("PG TEMP", self.s_temp), ("PG MÁX", self.s_max),
                                      ("DADOS GOLPE", self.e_dados), ("VELOCIDAD", self.s_vel),
                                      ("TAMAÑO", self.e_tam)]):
            head.addWidget(QLabel(f"<small>{txt}</small>"), 2, c)
            head.addWidget(w, 3, c)
        head.addWidget(QLabel("<small>BONO INIC.</small>"), 4, 0); head.addWidget(self.s_inib, 5, 0)
        head.addWidget(QLabel("<small>INICIATIVA</small>"), 4, 1); head.addWidget(self.lbl_ini, 5, 1)
        head.addWidget(QLabel("<small>PERC. PASIVA</small>"), 4, 2); head.addWidget(self.lbl_pp, 5, 2)
        head.addWidget(QLabel("<small>ALINEAMIENTO</small>"), 4, 3); head.addWidget(self.e_alin, 5, 3)
        head.addWidget(self.c_hero, 5, 4)
        head.addWidget(QLabel("<small>MUERTE ÉX.</small>"), 4, 5); head.addWidget(self.s_mue, 5, 5)
        head.addWidget(QLabel("<small>MUERTE FR.</small>"), 4, 6); head.addWidget(self.s_muf, 5, 6)

        # --- tarjetas de características ---
        self.scores, self.saves_chk, self.saves_val = {}, {}, {}
        self.skill_cmb, self.skill_val, self._mods = {}, {}, {}
        abil_grid = QGridLayout()
        abil_grid.addWidget(self._tarjeta("FUE"), 0, 0)
        abil_grid.addWidget(self._tarjeta("DES"), 1, 0)
        abil_grid.addWidget(self._tarjeta("CON"), 2, 0)
        abil_grid.addWidget(self._tarjeta("INT"), 0, 1)
        abil_grid.addWidget(self._tarjeta("SAB"), 1, 1)
        abil_grid.addWidget(self._tarjeta("CAR"), 2, 1)

        # --- columna derecha: armas + rasgos ---
        self.tbl = QTableWidget(6, 4)
        self.tbl.setHorizontalHeaderLabels(["Nombre", "Atk", "Daño", "Notas"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setMinimumHeight(190)
        self.t_rasgos = QTextEdit(); self.t_rasgos.setMaximumHeight(150)
        self.t_resp = QTextEdit(); self.t_resp.setMaximumHeight(110)
        self.t_dotes = QTextEdit(); self.t_dotes.setMaximumHeight(110)
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>ARMAS Y CANTRIPS DE DAÑO</b>"))
        right.addWidget(self.tbl)
        right.addWidget(QLabel("<b>RASGOS DE CLASE</b>")); right.addWidget(self.t_rasgos)
        right.addWidget(QLabel("<b>RASGOS DE ESPECIE</b>")); right.addWidget(self.t_resp)
        right.addWidget(QLabel("<b>DOTES</b>")); right.addWidget(self.t_dotes)
        rightW = QWidget(); rightW.setLayout(right)

        mid = QHBoxLayout()
        abilW = QWidget()
        abilW.setLayout(abil_grid)
        mid.addWidget(abilW, 1)
        mid.addWidget(rightW, 2)

        # --- bloque inferior ---
        self.t_comp = QLineEdit()
        self.t_herr = QLineEdit()
        self.t_idiom = QLineEdit()
        self.t_equipo = QTextEdit(); self.t_equipo.setMaximumHeight(80)
        bot = QGridLayout()
        bot.addWidget(QLabel("<small>COMPETENCIA ARMADURA Y ARMAS</small>"), 0, 0)
        bot.addWidget(self.t_comp, 1, 0)
        bot.addWidget(QLabel("<small>HERRAMIENTAS</small>"), 0, 1)
        bot.addWidget(self.t_herr, 1, 1)
        bot.addWidget(QLabel("<small>IDIOMAS</small>"), 2, 0)
        bot.addWidget(self.t_idiom, 3, 0)
        bot.addWidget(QLabel("<small>EQUIPO</small>"), 2, 1)
        bot.addWidget(self.t_equipo, 3, 1)

        body = QVBoxLayout()
        # retrato a la izquierda de la cabecera, como marco de la ficha
        self.lbl_retrato = QLabel("Sin\nretrato")
        self.lbl_retrato.setAlignment(Qt.AlignCenter)
        self.lbl_retrato.setFixedSize(150, 180)
        self.lbl_retrato.setStyleSheet("border:2px dashed #7d6234; border-radius:4px; color:#8d8172;")
        b_ret = QPushButton("Cambiar…")
        b_retq = QPushButton("Quitar")
        b_ret.clicked.connect(self.elegir_retrato)
        b_retq.clicked.connect(self.quitar_retrato)
        retr_box = QVBoxLayout()
        retr_box.addWidget(QLabel("<small>RETRATO</small>"), alignment=Qt.AlignCenter)
        retr_box.addWidget(self.lbl_retrato)
        retr_box.addWidget(b_ret)
        retr_box.addWidget(b_retq)
        retrW = QWidget(); retrW.setLayout(retr_box)
        self._retrato = ""
        headW = QWidget(); headW.setLayout(head)
        tophead = QHBoxLayout()
        tophead.addWidget(retrW)
        tophead.addWidget(headW, 1)
        body.addLayout(tophead)
        body.addLayout(mid)
        body.addLayout(bot)
        bodyW = QWidget(); bodyW.setLayout(body)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(bodyW)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(scroll, 1)

        self.cmb.currentIndexChanged.connect(self._cambio)
        b_save.clicked.connect(self.guardar)
        b_open.clicked.connect(self.abrir_pdf)
        for w in (self.s_nivel, self.s_inib, *self.scores.values(), *self.saves_chk.values(),
                  *self.skill_cmb.values(), self.e_nombre):
            sig = w.currentIndexChanged if isinstance(w, QComboBox) else (
                w.stateChanged if isinstance(w, QCheckBox) else (
                    w.valueChanged if isinstance(w, QSpinBox) else w.textChanged))
            sig.connect(self._recalc)
        self.refresh()

    def _tarjeta(self, car):
        box = QGroupBox(NOMBRE_CAR[car].upper())
        mod = QLabel("+0"); mod.setFont(QFont("Segoe UI", 26, QFont.Bold))
        mod.setAlignment(Qt.AlignCenter)
        sc = QSpinBox(); sc.setRange(1, 30); sc.setValue(10); sc.setPrefix("Puntuación ")
        chk = QCheckBox("Salvación"); val = QLabel("+0"); val.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lay = QVBoxLayout(box)
        lay.addWidget(mod, alignment=Qt.AlignCenter)
        self._mods[car] = mod
        lay.addWidget(sc)
        r0 = QHBoxLayout(); r0.addWidget(chk); r0.addWidget(val); r0.addStretch(1)
        lay.addLayout(r0)
        self.scores[car] = sc; self.saves_chk[car] = chk; self.saves_val[car] = val
        for hab, c2 in HABILIDADES:
            if c2 != car:
                continue
            cmb = QComboBox(); cmb.addItems(COMP_OPTS); cmb.setMaximumWidth(52)
            v = QLabel("+0"); v.setMinimumWidth(38)
            r = QHBoxLayout(); r.addWidget(cmb); r.addWidget(v); r.addWidget(QLabel(hab)); r.addStretch(1)
            lay.addLayout(r)
            self.skill_cmb[hab] = cmb; self.skill_val[hab] = v
        return box

    # ---- datos ----
    def refresh(self):
        con = connect()
        rows = con.execute("SELECT id,nombre FROM personajes ORDER BY nombre").fetchall()
        con.close()
        actual = self._pid
        self.cmb.blockSignals(True)
        self.cmb.clear()
        sel = 0
        for i, r in enumerate(rows):
            self.cmb.addItem(r["nombre"], r["id"])
            if r["id"] == actual:
                sel = i
        self.cmb.blockSignals(False)
        if rows:
            self.cmb.blockSignals(True)
            self.cmb.setCurrentIndex(sel)
            self.cmb.blockSignals(False)
            self._cargar(self.cmb.itemData(sel))

    def _cambio(self, i):
        if i >= 0:
            self._cargar(self.cmb.itemData(i))

    def _cargar(self, pid):
        con = connect()
        p = con.execute("SELECT * FROM personajes WHERE id=?", (pid,)).fetchone()
        armas = con.execute("SELECT nombre,atk,dano,notas FROM armas WHERE personaje_id=? ORDER BY id", (pid,)).fetchall()
        con.close()
        if not p:
            return
        self._updating = True
        self._pid = pid
        keys = p.keys()
        def g(col, d=""):
            return p[col] if col in keys and p[col] is not None else d
        self.e_nombre.setText(g("nombre"))
        self.e_trasfondo.setText(g("trasfondo")); self.e_clase.setText(g("clase"))
        self.e_especie.setText(g("especie")); self.e_subclase.setText(g("subclase"))
        self.s_nivel.setValue(g("nivel", 1) or 1); self.s_px.setValue(g("px", 0) or 0)
        self.s_ca.setValue(g("ca", 10)); self.s_pg.setValue(g("pg_actual", 10))
        self.s_temp.setValue(g("pg_temp", 0) or 0); self.s_max.setValue(g("pg_max", 10))
        self.e_dados.setText(g("dados_golpe")); self.s_vel.setValue(g("velocidad", 30) or 30)
        self.e_tam.setText(g("tamano")); self.s_inib.setValue(g("iniciativa_bono", 0) or 0)
        self.e_alin.setText(g("alineamiento"))
        self.c_hero.setChecked(bool(g("iniciativa_heroica", g("inspiracion_heroica", 0))))
        self.s_mue.setValue(g("mu_exitos", 0) or 0); self.s_muf.setValue(g("mu_fracasos", 0) or 0)
        for c, col in (("FUE", "fuerza"), ("DES", "destreza"), ("CON", "constitucion"),
                       ("INT", "inteligencia"), ("SAB", "sabiduria"), ("CAR", "carisma")):
            self.scores[c].setValue(g(col, 10) or 10)
        try:
            skills = json.loads(g("skills", "{}") or "{}")
            saves = json.loads(g("saves", "{}") or "{}")
        except (ValueError, TypeError):
            skills, saves = {}, {}
        for hab in self.skill_cmb:
            self.skill_cmb[hab].setCurrentIndex(int(skills.get(hab, 0) or 0))
        for c in self.saves_chk:
            self.saves_chk[c].setChecked(bool(saves.get(c, 0)))
        for i in range(6):
            for j, k in enumerate(("nombre", "atk", "dano", "notas")):
                self.tbl.setItem(i, j, QTableWidgetItem(armas[i][k] if i < len(armas) else ""))
        self.t_rasgos.setPlainText(g("rasgos")); self.t_resp.setPlainText(g("rasgos_especie"))
        self.t_dotes.setPlainText(g("dotes")); self.t_comp.setText(g("competencias"))
        self.t_herr.setText(g("herramientas")); self.t_idiom.setText(g("idiomas"))
        self.t_equipo.setPlainText(g("equipo"))
        self._retrato = g("retrato_path")
        if not self._ruta_retrato():
            auto = buscar_retrato(self.e_nombre.text().strip())
            if auto:
                self._retrato = auto
                con2 = connect()
                con2.execute("UPDATE personajes SET retrato_path=? WHERE id=?", (auto, self._pid))
                con2.commit(); con2.close()
        self._pintar_retrato()
        self._updating = False
        self._recalc()

    # ---- retrato (carpeta Retratos/) ----
    def _ruta_retrato(self):
        if not self._retrato:
            return ""
        from pathlib import Path
        p = Path(self._retrato)
        if not p.is_absolute():
            p = BASE / p
        return str(p) if p.exists() else ""

    def _pintar_retrato(self):
        ruta = self._ruta_retrato()
        if not ruta:
            self.lbl_retrato.setPixmap(QPixmap())
            self.lbl_retrato.setText("Sin\nretrato")
            return
        pm = QPixmap(ruta).scaled(150, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if pm.isNull():
            self.lbl_retrato.setText("No se\nlee")
        else:
            self.lbl_retrato.setPixmap(pm)
            self.lbl_retrato.setToolTip(self._retrato)

    def elegir_retrato(self):
        if self._pid is None:
            return
        inicio = str(RETRATOS_DIR) if RETRATOS_DIR.exists() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Retrato del personaje", inicio,
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        try:
            rel = importar_archivo(path, RETRATOS_DIR, self.e_nombre.text().strip() or "retrato")
        except Exception as e:
            QMessageBox.warning(self, "Retrato", f"No pude copiar la imagen:\n{e}")
            return
        self._retrato = rel
        con = connect()
        con.execute("UPDATE personajes SET retrato_path=? WHERE id=?", (rel, self._pid))
        con.commit(); con.close()
        self._pintar_retrato()

    def quitar_retrato(self):
        if self._pid is None:
            return
        self._retrato = ""
        con = connect()
        con.execute("UPDATE personajes SET retrato_path='' WHERE id=?", (self._pid,))
        con.commit(); con.close()
        self._pintar_retrato()

    # ---- cálculo en vivo ----
    def _fmt(self, v):
        return f"+{v}" if v >= 0 else str(v)

    def _recalc(self, *a):
        if self._updating or self._pid is None:
            return
        pb = bono_competencia(self.s_nivel.value())
        self.lbl_pb.setText(f"Bono competencia +{pb}")
        mods = {c: mod_car(self.scores[c].value()) for c in CARACTERISTICAS}
        for c in CARACTERISTICAS:
            self._mods[c].setText(self._fmt(mods[c]))
            sv = mods[c] + (pb if self.saves_chk[c].isChecked() else 0)
            self.saves_val[c].setText(self._fmt(sv))
        hab_car = dict(HABILIDADES)
        for hab, cmb in self.skill_cmb.items():
            st = cmb.currentIndex()
            self.skill_val[hab].setText(self._fmt(mods[hab_car[hab]] + pb * st))
        self.lbl_ini.setText(self._fmt(mods["DES"] + self.s_inib.value()))
        perc = mods["SAB"] + pb * self.skill_cmb["Percepción"].currentIndex()
        self.lbl_pp.setText(str(10 + perc))

    # ---- guardar ----
    def guardar(self):
        if self._pid is None:
            return
        skills = {h: c.currentIndex() for h, c in self.skill_cmb.items()}
        saves = {c: (1 if ch.isChecked() else 0) for c, ch in self.saves_chk.items()}
        con = connect()
        con.execute("""UPDATE personajes SET nombre=?,trasfondo=?,clase=?,especie=?,subclase=?,
            nivel=?,px=?,ca=?,pg_actual=?,pg_temp=?,pg_max=?,dados_golpe=?,velocidad=?,tamano=?,
            iniciativa_bono=?,alineamiento=?,inspiracion_heroica=?,mu_exitos=?,mu_fracasos=?,
            fuerza=?,destreza=?,constitucion=?,inteligencia=?,sabiduria=?,carisma=?,
            competencias=?,equipo=?,idiomas=?,herramientas=?,rasgos=?,rasgos_especie=?,dotes=?,
            skills=?,saves=?,retrato_path=? WHERE id=?""",
            (self.e_nombre.text().strip() or "Sin nombre", self.e_trasfondo.text(),
             self.e_clase.text(), self.e_especie.text(), self.e_subclase.text(), self.s_nivel.value(), self.s_px.value(),
             self.s_ca.value(), self.s_pg.value(), self.s_temp.value(), self.s_max.value(),
             self.e_dados.text(), self.s_vel.value(), self.e_tam.text(), self.s_inib.value(),
             self.e_alin.text(), int(self.c_hero.isChecked()), self.s_mue.value(), self.s_muf.value(),
             self.scores["FUE"].value(), self.scores["DES"].value(), self.scores["CON"].value(),
             self.scores["INT"].value(), self.scores["SAB"].value(), self.scores["CAR"].value(),
             self.t_comp.text(), self.t_equipo.toPlainText(), self.t_idiom.text(),
             self.t_herr.text(), self.t_rasgos.toPlainText(), self.t_resp.toPlainText(),
             self.t_dotes.toPlainText(), json.dumps(skills, ensure_ascii=False),
             json.dumps(saves), self._retrato, self._pid))
        con.execute("DELETE FROM armas WHERE personaje_id=?", (self._pid,))
        for i in range(6):
            vals = [(self.tbl.item(i, j).text().strip() if self.tbl.item(i, j) else "") for j in range(4)]
            if any(vals):
                con.execute("INSERT INTO armas(personaje_id,nombre,atk,dano,notas) VALUES(?,?,?,?,?)",
                            (self._pid, *vals))
        con.commit(); con.close()
        self.refresh()

    def abrir_pdf(self):
        if self._pid is None:
            return
        con = connect()
        p = con.execute("SELECT ficha_path,nombre FROM personajes WHERE id=?", (self._pid,)).fetchone()
        con.close()
        ficha = (p["ficha_path"] or "") if p else ""
        if not ficha and p:
            auto = buscar_pdf(p["nombre"])
            if auto:
                ficha = auto
                con = connect()
                con.execute("UPDATE personajes SET ficha_path=? WHERE id=?", (auto, self._pid))
                con.commit(); con.close()
        if not ficha:
            QMessageBox.information(self, "Ficha", "Este personaje no tiene PDF vinculado.")
            return
        from pathlib import Path
        ruta = Path(ficha)
        if not ruta.is_absolute():
            ruta = BASE / ruta
        if not ruta.exists():
            QMessageBox.warning(self, "Ficha", f"No se encuentra:\n{ruta}")
            return
        try:
            import os
            os.startfile(str(ruta))
        except Exception:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))
