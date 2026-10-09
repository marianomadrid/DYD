"""Compendio estilo 5e.tools: navegador con filtro por libros.

Las filas 5eTools se muestran con HTML de lectura (statblocks, objetos,
hechizos o texto con formato) y son de solo lectura; las del usuario se
editan en plano. El filtro por fuentes se guarda en ajustes (fuentes_off).
"""
import html
import json
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
                               QListView, QTableView, QLineEdit, QComboBox,
                               QTextEdit, QPushButton, QLabel, QInputDialog,
                               QCheckBox, QDialog, QHeaderView)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QTimer, QModelIndex, QItemSelectionModel, QSortFilterProxyModel
from ..database import connect, get_ajuste, set_ajuste

CATS = ["todas", "clase", "especie", "hechizo", "objeto", "monstruo", "regla",
        "trasfondo", "dote", "otro"]

HUESO = "#d6cbb6"
ORO = "#c8a44d"
LATON = "#7d6234"
TENUE = "#8d8172"

CUERPO_FONT = "font-family:'Cardo',serif; font-size:14px;"
TIT_FONT = "font-family:'Cinzel Decorative',serif;"


def _esc(t):
    return html.escape(str(t or "")).replace("\n", "<br>")


def html_texto(texto):
    """Texto plano del importador -> HTML legible estilo 5e.tools.

    Convenciones que genera `plano()`: `### ` títulos, `--- X ---` secciones,
    `• ` listas, ` | ` tablas, `[...]` entradillas. El resto, párrafos.
    """
    out, lista, tabla, parrafo = [], [], [], []

    def vuelca_lista():
        if lista:
            out.append("<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in lista) + "</ul>")
            lista.clear()

    def vuelca_tabla():
        if tabla:
            filas = "".join(
                f"<tr>{''.join(f'<th>{_esc(c)}</th>' if i == 0 else f'<td>{_esc(c)}</td>' for i, c in enumerate(r))}</tr>"
                for r in [[c.strip() for c in fila.split("|")] for fila in tabla])
            out.append(f"<table width='100%' border='1' cellspacing='0' cellpadding='5'>{filas}</table>")
            tabla.clear()

    def vuelca_parrafo():
        if parrafo:
            out.append(f"<p>{' '.join(_esc(x) for x in parrafo)}</p>")
            parrafo.clear()

    for cruda in (texto or "").splitlines():
        ln = cruda.strip()
        if not ln:
            vuelca_parrafo()
            continue
        if ln.startswith("### "):
            vuelca_parrafo(); vuelca_lista(); vuelca_tabla()
            out.append(f"<h4 style='color:{ORO}; {TIT_FONT} margin-bottom:2px;'>{_esc(ln[4:])}</h4>")
        elif ln.startswith("---") and ln.endswith("---"):
            vuelca_parrafo(); vuelca_lista(); vuelca_tabla()
            out.append(f"<p style='color:{ORO}; font-size:15px; {TIT_FONT} margin-bottom:0;'>{_esc(ln.strip('- '))}</p><hr>")
        elif ln.startswith(("• ", "- ")):
            vuelca_parrafo(); vuelca_tabla()
            lista.append(ln[2:])
        elif "|" in ln:
            vuelca_parrafo(); vuelca_lista()
            tabla.append(ln)
        elif ln.startswith("[") and ln.endswith("]"):
            vuelca_parrafo(); vuelca_lista(); vuelca_tabla()
            out.append(f"<p><i style='color:{TENUE};'>{_esc(ln)}</i></p>")
        else:
            vuelca_lista(); vuelca_tabla()
            parrafo.append(ln)
    vuelca_parrafo(); vuelca_lista(); vuelca_tabla()
    return f"<div style='{CUERPO_FONT}'>" + "".join(out) + "</div>"


def _celda(txto, clave=None, num=False):
    it = QStandardItem(str(txto))
    it.setEditable(False)
    it.setData(clave if clave is not None else str(txto).lower(), R_SORT)
    return it


def _fila_tabla(cat, pid, nombre, fuente_cod, d):
    """(QStandardItems por columna) para hechizo/objeto/dote."""
    if cat == "hechizo":
        n = d.get("nivel", 0)
        niv = "Truco" if n == 0 else str(n)
        if d.get("ritual"):
            niv += " (rit.)"
        return [_celda(nombre, nombre.lower()),
                _celda(niv, n),
                _celda(d.get("tiempo", "")),
                _celda(d.get("escuela", "")),
                _celda("×" if d.get("conc") else "", int(bool(d.get("conc")))),
                _celda(d.get("alcance", "")),
                _celda(d.get("corta", d.get("fuente", "")))]
    if cat == "objeto":
        return [_celda(nombre, nombre.lower()),
                _celda(d.get("tipo", "")),
                _celda(d.get("rareza", "") or "—"),
                _celda(d.get("valor", "") or "—", d.get("valor_cp", -1)),
                _celda(d.get("peso", "") or "—", d.get("peso_lb", -1.0)),
                _celda(d.get("corta", d.get("fuente", "")))]
    # dote
    if cat == "dote":
        return [_celda(nombre, nombre.lower()),
                _celda(d.get("tipo", "") or "—"),
                _celda(d.get("requisito", "") or "—"),
                _celda(d.get("corta", d.get("fuente", "")))]
    # trasfondo
    return [_celda(nombre, nombre.lower()),
            _celda(d.get("origen", "") or "—"),
            _celda(d.get("habilidades", "") or "—"),
            _celda(d.get("corta", d.get("fuente", "")))]


def _fuente_badge(d):
    pagina = f" · pág. {d['pagina']}" if d.get("pagina") else ""
    return f"{_esc(d.get('corta', d.get('fuente', '')))}{pagina}"


def _pie(d):
    ref = f" Referenciado en {', '.join(d['ref'])}." if d.get("ref") else ""
    return f"<p style='color:{TENUE};'><small>Fuente: {_esc(d.get('fuente', ''))}.{ref}</small></p>"


def html_statblock(d):
    """Statblock estilo 5eTools con paleta Bloodborne. d = dict de `datos`."""
    car = d.get("car", {})
    filas = "".join(
        f"<tr><td><b>{c}</b></td><td align='center'>{car[c]['score']}</td>"
        f"<td align='center'>{car[c]['mod']}</td>"
        f"<td align='center'>{car[c]['save']}</td></tr>"
        for c in ("FUE", "DES", "CON", "INT", "SAB", "CAR") if c in car)
    tabla = (f"<table width='100%' border='1' cellspacing='0' cellpadding='5'>"
             f"<tr><td><b>CAR</b></td><td align='center'><b>PTOS</b></td>"
             f"<td align='center'><b>MOD</b></td><td align='center'><b>SALV</b></td></tr>"
             f"{filas}</table>") if filas else ""
    hab = ", ".join(f"{n} {v}" for n, v in d.get("hab", []))
    subt = ", ".join(t for t in [d.get("tam", ""), d.get("tipo", ""), d.get("alin", "")] if t)
    xp = f" (XP {d['xp']}; PB +{d['pb']})" if d.get("xp") and d.get("pb") else ""
    pp = f"Percepción pasiva {d['pp']}" if d.get("pp") else ""
    sen = "; ".join(t for t in [d.get("sentidos", ""), pp] if t)

    def sec(titulo, bloques):
        if not bloques:
            return ""
        items = "".join(
            f"<p><b><i>{_esc(b.get('n', ''))}.</i></b> {_esc(b.get('t', ''))}</p>"
            for b in bloques)
        return (f"<p style='color:{ORO}; font-size:15px; {TIT_FONT} margin-bottom:0;'>{titulo}</p>"
                f"<hr>{items}")

    footer = "".join(
        f"<p><b>{et}:</b> {_esc(v)}</p>" for et, v in
        (("Hábitat", d.get("habitat", "")), ("Tesoro", d.get("tesoro", ""))) if v)
    return f"""<h2 style='color:{ORO}; margin-bottom:0;'>{_esc(d.get('nombre', '?'))}</h2>
<p align='right' style='color:{ORO};'><small>{_fuente_badge(d)}</small></p>
<p><i style='color:{TENUE};'>{_esc(subt)}</i></p>
<table width='100%' cellspacing='0' cellpadding='4'>
<tr><td><b>CA</b> {_esc(d.get('ca', ''))}</td>
<td align='right'><b>Iniciativa</b> {_esc(d.get('ini', ''))}</td></tr>
<tr><td><b>PG</b> {_esc(d.get('pg', ''))}</td>
<td><b>Vel</b> {_esc(d.get('vel', ''))}</td></tr>
</table><br>{tabla}<br>
<p><b>Habilidades</b> {_esc(hab) if hab else '—'}</p>
<p><b>Sentidos</b> {_esc(sen) if sen else '—'}</p>
<p><b>Idiomas</b> {_esc(d.get('idiomas', '')) if d.get('idiomas') else '—'}</p>
<p><b>CR</b> {_esc(d.get('cr', ''))}{_esc(xp)}</p>
{sec('ACCIONES', d.get('acciones', []))}
{sec('REACCIONES', d.get('reacciones', []))}
{sec('ACCIONES LEGENDARIAS', d.get('legendarias', []))}
{sec('RASGOS', d.get('rasgos', []))}
{footer}
{_pie(d)}"""


def html_objeto(d):
    """Ficha de objeto estilo página 5eTools. d = dict de `datos`."""
    subt = " · ".join(t for t in [d.get("tipo", ""), d.get("cat_arma", ""),
                                  ", ".join(d.get("props", []))] if t)
    det = []
    for et, k in (("Valor", "valor"), ("Peso", "peso"),
                  ("Daño", "dano"), ("Daño versátil", "dano2"),
                  ("Alcance", "alcance")):
        if d.get(k):
            v = d[k] + (f" ({d['dano_tipo']})" if k == "dano" and d.get("dano_tipo") else "")
            det.append((et, v))
    if d.get("maestrias"):
        det.append(("Maestría", ", ".join(d["maestrias"])))
    for et, v in (d.get("armadura") or {}).items():
        det.append((et, v))
    if d.get("base"):
        det.append(("Basado en", d["base"]))
    filas = "".join(f"<tr><td><b>{_esc(a)}</b></td><td>{_esc(b)}</td></tr>" for a, b in det)
    tabla = (f"<table width='100%' border='1' cellspacing='0' cellpadding='5'>{filas}</table><br>"
             if filas else "")
    rareza = d.get("rareza", "")
    if d.get("sintonia"):
        rareza = (rareza + " " if rareza else "") + f"({_esc(d['sintonia'])})"
    return f"""<h2 style='color:{ORO}; margin-bottom:0;'>{_esc(d.get('nombre', '?'))}</h2>
<p align='right' style='color:{ORO};'><small>{_fuente_badge(d)}</small></p>
<p><i style='color:{TENUE};'>{_esc(subt)}</i></p>
{f"<p style='color:{ORO}; font-size:15px; {TIT_FONT}>{_esc(rareza)}</p><hr>" if rareza else ""}
{tabla}{html_texto(d.get('texto', ''))}
{_pie(d)}"""


def html_clase(d, subs_on=None):
    """Página de clase estilo 5e.tools: cabecera, tabla, rasgos, subclases."""
    subs_on = set(subs_on) if subs_on is not None else None
    cols, filas = d.get("columnas", []), d.get("filas", [])
    # Epígrafe centrado en vez de fila de grupo con colspan (frágil en Qt).
    epigrafe = ""
    if d.get("con_conjuros") and len(cols) >= 12 and all(
            isinstance(c, str) and len(c) > 2 and c[:-2].isdigit() and c[-2:] in ("st", "nd", "rd", "th")
            for c in cols[-9:]):
        epigrafe = (f"<p align='center' style='color:{ORO}; {TIT_FONT} margin-bottom:2px;'>"
                    f"Spell Slots per Spell Level</p>")
    cab = "".join(f"<tr>{''.join(f'<th>{_esc(c)}</th>' if i == 0 else f'<td>{_esc(c)}</td>' for j, c in enumerate([f[0]] + f[1:]))}</tr>" for i, f in enumerate([cols] + filas))
    tabla = (f"{epigrafe}<table width='100%' border='1' cellspacing='0' cellpadding='4'>{cab}</table><br>"
             if cols else "")
    detalle = "".join(f"<p>{_esc(x)}</p>" for x in d.get("cabecera", []))

    AZUL = "#8fb8d8"  # títulos de subclase: luz de luna, distinto del oro de clase

    def rasgo_html(f, color=ORO):
        src = f"{_esc(f.get('fuente', ''))}" + (f" p{f['pagina']}" if f.get("pagina") else "")
        cuerpo = "<br>".join(
            f"<b>{_esc(s[4:])}</b>" if s.startswith("### ") else _esc(s)
            for s in str(f.get("t", "")).splitlines() if s.strip())
        return (f"<p style='color:{color}; font-size:15px; {TIT_FONT} margin-bottom:0;'>"
                f"Level {f.get('nivel', '?')}: {_esc(f.get('n', ''))}"
                f"<span style='color:{TENUE}; font-size:12px;'> · {src}</span></p>"
                f"<p>{cuerpo}</p>")

    def nivel_de(f):
        return f.get("nivel") if isinstance(f.get("nivel"), int) else 999

    # Flujo único por niveles como la página: en cada nivel, primero rasgos de
    # clase y después los de cada subclase elegida (intro + rasgos).
    sel = []
    for s in d.get("subclases", []):
        clave = f"{s.get('corto') or s.get('nombre')}§{s.get('fuente', '')}"
        if subs_on is not None and clave not in subs_on:
            continue
        fr = list(s.get("rasgos", []))
        intro = None
        resto = []
        for f in fr:
            if intro is None and f.get("n") == s.get("nombre"):
                intro = f
            else:
                resto.append(f)
        sel.append((s, intro, resto))

    def intro_html(s, intro):
        src = f"{_esc(s.get('fuente', ''))}" + (f" p{s['pagina']}" if s.get("pagina") else "")
        if intro:
            lineas = [x.strip() for x in str(intro.get("t", "")).splitlines() if x.strip()]
            lema = f"<p><i style='color:{TENUE};'>{_esc(lineas[0])}</i></p>" if lineas else ""
            desc = "<br>".join(_esc(x) for x in lineas[1:])
        else:
            lema, desc = "", f"<p><i style='color:{TENUE};'>{_esc(s.get('desc', ''))}</i></p>"
        return (f"<p style='color:{AZUL}; font-size:16px; {TIT_FONT} margin-bottom:0;'>"
                f"{_esc(s.get('nombre', '').upper())}"
                f"<span style='color:{TENUE}; font-size:12px;'> · {src}</span></p><hr>"
                f"{lema}<p>{desc}</p>" if desc else
                f"<p style='color:{AZUL}; font-size:16px; {TIT_FONT} margin-bottom:0;'>"
                f"{_esc(s.get('nombre', '').upper())}"
                f"<span style='color:{TENUE}; font-size:12px;'> · {src}</span></p><hr>{lema}")

    flujo = ""
    niveles = sorted({nivel_de(f) for f in d.get("rasgos", [])} |
                     {nivel_de(f) for _, _, resto in sel for f in resto} |
                     {nivel_de(i) for _, i, _ in sel if i is not None})
    mostradas = set()
    for nv in niveles:
        etiqueta = str(nv) if nv != 999 else "?"
        for f in d.get("rasgos", []):
            if nivel_de(f) == nv:
                flujo += rasgo_html({**f, "nivel": etiqueta})
        for s, intro, resto in sel:
            if intro is not None and nivel_de(intro) == nv and id(s) not in mostradas:
                mostradas.add(id(s))
                flujo += intro_html(s, intro)
            for f in resto:
                if nivel_de(f) == nv:
                    flujo += rasgo_html({**f, "nivel": etiqueta}, AZUL)
    for s, intro, resto in sel:  # subclases sin rasgos: solo la intro al final
        if id(s) not in mostradas:
            flujo += intro_html(s, intro)
    return f"""<h2 style='color:{ORO}; margin-bottom:0;'>{_esc(d.get('nombre', '?'))}</h2>
<p align='right' style='color:{ORO};'><small>{_fuente_badge(d)}</small></p>
{detalle}{tabla}
<p style='color:{ORO}; font-size:16px; {TIT_FONT} margin-bottom:0;'>RASGOS</p><hr>{flujo}
{_pie(d)}"""


def html_hechizo(d):
    """Ficha de conjuro estilo página 5eTools. d = dict de `datos`."""
    subt = d.get("nivel", 0)
    subt = ("Truco" if subt == 0 else f"Nivel {subt}") + \
        (f" de {d['escuela']}" if d.get("escuela") else "")
    det = [(et, d[k]) for et, k in (("Tiempo", "tiempo"), ("Alcance", "alcance"),
                                    ("Componentes", "comp"), ("Duración", "duracion")) if d.get(k)]
    filas = "".join(f"<tr><td><b>{_esc(a)}</b></td><td>{_esc(b)}</td></tr>" for a, b in det)
    tabla = (f"<table width='100%' border='1' cellspacing='0' cellpadding='5'>{filas}</table><br>"
             if filas else "")
    cls = f"<p><b>Clases</b> {_esc(', '.join(d['clases']))}</p>" if d.get("clases") else ""
    return f"""<h2 style='color:{ORO}; margin-bottom:0;'>{_esc(d.get('nombre', '?'))}</h2>
<p align='right' style='color:{ORO};'><small>{_fuente_badge(d)}</small></p>
<p><i style='color:{TENUE};'>{_esc(subt)}</i></p>
{tabla}{cls}{html_texto(d.get('texto', ''))}
{_pie(d)}"""


LIMITE_FILAS = 1500  # tope visible; el resto se alcanza buscando/filtrando

R_ID = Qt.UserRole
R_CAT = Qt.UserRole + 1
R_FUENTE = Qt.UserRole + 2  # código 5eTools o "" (filas de usuario, nunca filtradas)
R_SORT = Qt.UserRole + 10  # clave de ordenación por celda en tablas

TABLAS = {
    "hechizo": ["Nombre", "Nivel", "Tiempo", "Escuela", "C.", "Alcance", "Libro"],
    "objeto": ["Nombre", "Tipo", "Rareza", "Valor", "Peso", "Libro"],
    "dote": ["Nombre", "Tipo", "Requisito", "Libro"],
    "trasfondo": ["Nombre", "Origen", "Habilidades", "Libro"],
}


class FiltroCompendio(QSortFilterProxyModel):
    """Proxy sin destrucción: filtra por categoría, ids de búsqueda y libros
    apagados, con tope visible. Nada se crea ni se destruye al refiltrar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cat = "todas"
        self.ids = None
        self.off = set()
        self._acept = 0
        self._total = 0

    def refiltrar(self, cat, ids, off):
        self.cat = cat
        self.ids = ids
        self.off = set(off)
        self._acept = 0
        self._total = 0
        self.invalidateFilter()

    def filterAcceptsRow(self, r, parent):
        m = self.sourceModel()
        i0 = m.index(r, 0, parent)
        if self.cat != "todas" and i0.data(R_CAT) != self.cat:
            return False
        if self.ids is not None and i0.data(R_ID) not in self.ids:
            return False
        if (i0.data(R_FUENTE) or "") in self.off:
            return False
        self._total += 1
        if self._acept >= LIMITE_FILAS:
            return False
        self._acept += 1
        return True

    def lessThan(self, izq, der):
        a, b = izq.data(R_SORT), der.data(R_SORT)
        if a is None:
            a = izq.data(Qt.DisplayRole) or ""
        if b is None:
            b = der.data(Qt.DisplayRole) or ""
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a < b
        return str(a).lower() < str(b).lower()


class CompendioView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar…")
        self.cat = QComboBox(); self.cat.addItems(CATS)
        self.lst = QListView()
        self.lst.setUniformItemSizes(True)  # filas iguales: layout O(1), sin picos
        self.table = QTableView()
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setVisible(False)
        self._tablas = {}  # cat -> (model, proxy, selmodel, mapa); se construyen una vez
        self._vista = self.lst
        self._pactiva = None
        self.title = QLineEdit(); self.title.setPlaceholderText("Nombre de la entrada")
        self.subs_frame = QWidget()
        subslay = QHBoxLayout(self.subs_frame)
        subslay.setContentsMargins(0, 0, 0, 0)
        subslay.addWidget(QLabel("Subclases:"))
        self.subs_grid = QGridLayout()
        subslay.addLayout(self.subs_grid, 1)
        self.subs_frame.setVisible(False)
        self.subs_btns = {}
        self.txt = QTextEdit()
        self.txt.document().setDocumentMargin(14)
        self.txt.setUndoRedoEnabled(False)  # los docs gigantes no se acumulan en undo
        self.lbl = QLabel("Añade tus resúmenes del manual 2024 para uso privado.")
        self._off = set()
        try:
            self._off = set(json.loads(get_ajuste("fuentes_off", "[]") or "[]"))
        except (ValueError, TypeError):
            self._off = set()

        top = QHBoxLayout(); top.addWidget(QLabel("Categoría:")); top.addWidget(self.cat)
        top.addWidget(self.search, 1)
        b_add = QPushButton("+ Nueva"); b_save = QPushButton("Guardar"); b_del = QPushButton("Borrar")
        top.addWidget(b_add); top.addWidget(b_save); top.addWidget(b_del)

        self.b_f = QPushButton("Fuentes")
        self.b_f.setToolTip("Filtrar por libros (como en 5e.tools)")
        fra = QHBoxLayout(); fra.addWidget(self.b_f); fra.addStretch(1)
        fra.addWidget(QLabel("Desactiva los libros que no te interesen."))
        self.lbl_count = QLabel("")
        fra.addWidget(self.lbl_count)
        self.dlg = None
        self.dgrid = None
        self.dchecks = {}

        left = QVBoxLayout(); left.addLayout(top); left.addLayout(fra)
        left.addWidget(self.lst, 1)
        left.addWidget(self.table, 1)
        right = QVBoxLayout(); right.addWidget(self.title); right.addWidget(self.subs_frame); right.addWidget(self.txt, 1); right.addWidget(self.lbl)
        main = QHBoxLayout(self); main.addLayout(left, 1); main.addLayout(right, 2)

        self.search.textChanged.connect(self._buscar_luego)
        self._tbuscar = QTimer(self)
        self._tbuscar.setSingleShot(True)
        self._tbuscar.setInterval(250)
        self._tbuscar.timeout.connect(self.refiltrar)
        self.cat.currentIndexChanged.connect(lambda _i=0: self.refiltrar())
        b_add.clicked.connect(self.nueva); b_save.clicked.connect(self.guardar); b_del.clicked.connect(self.borrar)
        self.b_f.clicked.connect(self.abrir_filtro)
        self.checks = {}
        self._total = set()
        self._texto_boton()
        self._proxy = FiltroCompendio(self)
        # Un solo selection-model para toda la sesión, atado al proxy (que
        # también vive siempre): aquí ya no se destruye nada nunca.
        self._selmodel = QItemSelectionModel(self._proxy)
        self._selmodel.currentChanged.connect(self._load)
        self._source = None
        self._por_id = {}
        self.refresh()

    # ---- filtro por fuentes (diálogo grande, todo visible) ----
    def _buscar_luego(self):
        if self._tbuscar.isActive():
            self._tbuscar.stop()
        self._tbuscar.start()
    def abrir_filtro(self):
        if self.dlg is None:
            self.dlg = QDialog(self)
            self.dlg.setWindowTitle("Fuentes")
            self.dlg.setMinimumWidth(1150)
            lay = QVBoxLayout(self.dlg)
            fila = QHBoxLayout()
            self.dsearch = QLineEdit(); self.dsearch.setPlaceholderText("Buscar libro…")
            b_todas = QPushButton("Todas"); b_ninguna = QPushButton("Ninguna")
            b_cerrar = QPushButton("Cerrar")
            fila.addWidget(self.dsearch, 1)
            fila.addWidget(b_todas); fila.addWidget(b_ninguna); fila.addWidget(b_cerrar)
            lay.addLayout(fila)
            self.dgrid = QGridLayout()
            lay.addLayout(self.dgrid)
            self.dsearch.textChanged.connect(self._filtrar_checks)
            b_todas.clicked.connect(lambda: self._todas(True))
            b_ninguna.clicked.connect(lambda: self._todas(False))
            b_cerrar.clicked.connect(self.dlg.close)
        else:
            self.dsearch.clear()
        self._construir_checks()
        self.dlg.adjustSize()
        self.dlg.show()

    def _filtrar_checks(self):
        # Sin reconstruir: solo oculta. Reconstruir 122 casillas por tecla
        # dejaba un reguero de deleteLater que tumbaba el binding (shiboken).
        q = self.dsearch.text().strip().lower()
        for cod, w in self.dchecks.items():
            if not q:
                w.setVisible(True)
                continue
            nom = w.toolTip().lower()
            w.setVisible(q in nom or q in cod.lower())

    def _construir_checks(self):
        if self.dgrid is None:
            return
        if self.dchecks:
            # Ya construido: solo refiltra (ver _filtrar_checks).
            self._filtrar_checks()
            self._texto_boton()
            return
        con = connect()
        try:
            fl = con.execute("SELECT codigo,nombre FROM fuentes ORDER BY nombre").fetchall()
        except Exception:
            fl = []
        conteo = {}
        try:
            for f, n in con.execute("SELECT fuente,COUNT(*) FROM compendio WHERE fuente LIKE '5eTools · %' GROUP BY fuente"):
                conteo[f.rsplit("·", 1)[-1].strip()] = n
        except Exception:
            pass
        con.close()
        i = 0
        for r in fl:
            cod, nom = r["codigo"], r["nombre"]
            n = conteo.get(cod, 0)
            if n == 0:
                continue
            corto = nom if len(nom) <= 27 else nom[:25] + "…"
            chk = QCheckBox(f"{corto} ({n})")
            chk.setToolTip(f"{nom} [{cod}]")
            chk.setChecked(cod not in self._off)
            chk.toggled.connect(self._cambio_fuente)
            chk.setProperty("codigo", cod)
            self.dgrid.addWidget(chk, i // 5, i % 5)
            self.dchecks[cod] = chk
            i += 1
        self.checks = self.dchecks
        self._total = {w.property("codigo") for w in self.dchecks.values()}
        self._filtrar_checks()
        self._texto_boton()

    def _texto_boton(self):
        if not getattr(self, "_total", set()):
            con = connect()
            try:
                self._total = {r[0].rsplit("·", 1)[-1].strip() for r in
                               con.execute("SELECT DISTINCT fuente FROM compendio "
                                           "WHERE fuente LIKE '5eTools · %'").fetchall()}
            except Exception:
                pass
            con.close()
        tot = len(self._total)
        on = len([c for c in self._total if c not in self._off])
        self.b_f.setText(f"Fuentes ({on}/{tot})")

    def _cambio_fuente(self):
        self._off = {c for c, w in self.checks.items() if not w.isChecked()}
        set_ajuste("fuentes_off", json.dumps(sorted(self._off)))
        self._texto_boton()
        self.refiltrar()

    def _todas(self, on):
        con = connect()
        try:
            todos = [r["codigo"] for r in
                     con.execute("SELECT DISTINCT substr(fuente,11) AS codigo FROM compendio "
                                 "WHERE fuente LIKE '5eTools · %'").fetchall()]
        except Exception:
            todos = list(self.checks)
        con.close()
        self._off = set() if on else set(todos)
        set_ajuste("fuentes_off", json.dumps(sorted(self._off)))
        for w in self.dchecks.values():
            w.blockSignals(True)
            w.setChecked(on)
            w.blockSignals(False)
        self._texto_boton()
        self.refiltrar()

    def _fila_fuente(self, r):
        f = r["fuente"] or ""
        if f.startswith("5eTools · "):
            return f.rsplit("·", 1)[-1].strip()
        return ""

    def _construir_fuente(self):
        # El modelo fuente se construye UNA vez (con TODAS las filas) y no se
        # vuelve a tocar en masa jamás: ni clear, ni swap, ni deleteLater.
        src = QStandardItemModel(self)
        con = connect()
        rows = con.execute("SELECT id,categoria,nombre,fuente FROM compendio "
                           "ORDER BY categoria,nombre").fetchall()
        con.close()
        for r in rows:
            it = QStandardItem(f"[{r['categoria']}] {r['nombre']}")
            it.setData(r["id"], R_ID)
            it.setData(r["categoria"], R_CAT)
            it.setData(self._fila_fuente(r), R_FUENTE)
            it.setEditable(False)
            src.appendRow(it)
            self._por_id[r["id"]] = it
        self._source = src
        self._proxy.setSourceModel(src)
        self.lst.setModel(self._proxy)
        self.lst.setSelectionModel(self._selmodel)

    def refresh(self):
        # Compatibilidad (Main llama a refresh al cambiar de pestaña):
        # con el proxy no hay nada que reconstruir, solo refiltrar.
        self.refiltrar()

    def _tabla_asegurada(self, cat):
        # Un modelo+proxy por categoría tabla, construidos una vez y vivos
        # siempre: aquí tampoco se destruye nada nunca.
        if cat in self._tablas:
            return self._tablas[cat]
        con = connect()
        rows = con.execute("SELECT id,nombre,fuente,datos FROM compendio WHERE categoria=?", (cat,)).fetchall()
        con.close()
        model = QStandardItemModel(self)
        model.setHorizontalHeaderLabels(TABLAS[cat])
        mapa = {}
        for r in rows:
            try:
                d = json.loads(r["datos"]) if r["datos"] else {}
            except (ValueError, TypeError):
                d = {}
            cod = (r["fuente"] or "")
            cod = cod.rsplit("·", 1)[-1].strip() if cod.startswith("5eTools · ") else ""
            items = _fila_tabla(cat, r["id"], r["nombre"], cod, d if isinstance(d, dict) else {})
            items[0].setData(r["id"], R_ID)
            items[0].setData(cat, R_CAT)
            items[0].setData(cod, R_FUENTE)
            model.appendRow(items)
            mapa[r["id"]] = items[0]
        proxy = FiltroCompendio(self)
        proxy.setSourceModel(model)
        proxy.sort(0, Qt.AscendingOrder)
        selmodel = QItemSelectionModel(proxy)
        selmodel.currentChanged.connect(self._load)
        self._tablas[cat] = (model, proxy, selmodel, mapa)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for j in range(1, model.columnCount()):
            hh.setSectionResizeMode(j, QHeaderView.ResizeToContents)
        return self._tablas[cat]

    def refiltrar(self):
        if self._source is None:
            self._construir_fuente()
        q = self.search.text().strip()
        ids = None
        if q:
            con = connect()
            ids = {r[0] for r in con.execute(
                "SELECT id FROM compendio WHERE nombre LIKE ? OR contenido LIKE ?",
                (f"%{q}%", f"%{q}%")).fetchall()}
            con.close()
        cat = self.cat.currentText()
        if cat in TABLAS:
            _, proxy, selmodel, _ = self._tabla_asegurada(cat)
            proxy.refiltrar(cat, ids, self._off)
            if self.table.model() is not proxy:
                self.table.setModel(proxy)
            if self.table.selectionModel() is not selmodel:
                self.table.setSelectionModel(selmodel)
            self.lst.setVisible(False)
            self.table.setVisible(True)
            self._vista = self.table
            self._pactiva = proxy
            self.subs_frame.setVisible(False)
        else:
            self._proxy.refiltrar(cat, ids, self._off)
            self.table.setVisible(False)
            self.lst.setVisible(True)
            self._vista = self.lst
            self._pactiva = self._proxy
        total, shown = self._pactiva._total, self._pactiva.rowCount()
        self.lbl_count.setText(f"Mostrando {shown} de {total}")
        if shown and not self._vista.currentIndex().isValid():
            self._vista.setCurrentIndex(self._pactiva.index(0, 0))

    def _load(self, cur: QModelIndex, prev: QModelIndex):
        if cur is None or not cur.isValid():
            return
        pid = cur.data(Qt.UserRole)
        if pid is None:
            return
        self.subs_frame.setVisible(False)
        con = connect()
        e = con.execute("SELECT * FROM compendio WHERE id=?", (pid,)).fetchone()
        con.close()
        self.title.setText(f"[{e['categoria']}] {e['nombre']}")
        self._id = e["id"]
        self._solo_lectura = False
        try:
            datos = json.loads(e["datos"]) if "datos" in e.keys() and e["datos"] else {}
        except (ValueError, TypeError):
            datos = {}
        v = datos.get("v")
        if e["categoria"] == "monstruo" and v in (1, "monstruo"):
            self.subs_frame.setVisible(False)
            self.txt.setHtml(html_statblock(datos))
        elif e["categoria"] == "objeto" and v in (1, "objeto") and datos.get("tipo") is not None:
            self.subs_frame.setVisible(False)
            self.txt.setHtml(html_objeto(datos))
        elif e["categoria"] == "hechizo" and v == "hechizo":
            self.subs_frame.setVisible(False)
            self.txt.setHtml(html_hechizo(datos))
        elif e["categoria"] == "clase" and v == "clase":
            self._pintar_clase(e["nombre"], datos)
            return
        elif str(e["fuente"]).startswith("5eTools"):
            self.txt.setHtml(html_texto(e["contenido"]))
        else:
            self.txt.setReadOnly(False)
            self.txt.setPlainText(f"Fuente: {e['fuente']}\n\n{e['contenido']}")
            self.lbl.setText("Añade tus resúmenes del manual 2024 para uso privado.")
            return
        self.txt.setReadOnly(True)
        self._solo_lectura = True
        self.lbl.setText("Entrada de referencia 5eTools (solo lectura).")

    # ---- página de clase con subclases seleccionables ----
    def _pintar_clase(self, nombre, datos):
        from ..database import get_ajuste as _ga, set_ajuste as _sa
        self._clase_datos = datos
        self._clase_nombre = nombre
        try:
            guardado = json.loads(_ga("clase_subs", "{}") or "{}")
        except (ValueError, TypeError):
            guardado = {}
        # Por defecto ninguna subclase marcada (se eligen a mano); si ya hay
        # preferencia guardada (aunque sea vacía) se respeta tal cual.
        sel = set(guardado[nombre]) if nombre in guardado else set()
        for i in reversed(range(self.subs_grid.count())):
            w = self.subs_grid.itemAt(i).widget()
            if w:
                w.deleteLater()
        self.subs_btns = {}
        subs = datos.get("subclases", [])
        for i, s in enumerate(subs):
            clave = f"{s.get('corto') or s.get('nombre')}§{s.get('fuente', '')}"
            b = QPushButton(f"{s.get('nombre')} ({s.get('corta', s.get('fuente', ''))})")
            b.setCheckable(True)
            b.setChecked(clave in sel)
            b.setProperty("clave", clave)
            b.toggled.connect(self._cambio_subs)
            self.subs_grid.addWidget(b, i // 4, i % 4)
            self.subs_btns[clave] = b
        self.subs_frame.setVisible(True)
        self._sel_subs = sel
        self._render_clase()
        self.txt.setReadOnly(True)
        self._solo_lectura = True
        self.lbl.setText("Entrada de referencia 5eTools (solo lectura).")

    def _cambio_subs(self):
        self._sel_subs = {c for c, b in self.subs_btns.items() if b.isChecked()}
        try:
            from ..database import get_ajuste as _ga, set_ajuste as _sa
            todo = json.loads(_ga("clase_subs", "{}") or "{}")
            todo[self._clase_nombre] = sorted(self._sel_subs)
            _sa("clase_subs", json.dumps(todo))
        except (ValueError, TypeError):
            pass
        self._render_clase()

    def _render_clase(self):
        sb = self.txt.verticalScrollBar().value()
        self.txt.setHtml(html_clase(self._clase_datos, self._sel_subs))
        self.txt.verticalScrollBar().setValue(sb)

    def _anadir_fila(self, pid, categoria, nombre, fuente=""):
        it = QStandardItem(f"[{categoria}] {nombre}")
        it.setData(pid, R_ID)
        it.setData(categoria, R_CAT)
        it.setData(self._fila_fuente({"fuente": fuente}), R_FUENTE)
        it.setEditable(False)
        self._source.appendRow(it)
        self._por_id[pid] = it

    def nueva(self):
        nombre, ok = QInputDialog.getText(self, "Nueva entrada", "Nombre:")
        if ok and nombre.strip():
            c, ok2 = QInputDialog.getItem(self, "Categoría", "Categoría:", CATS[1:], 0, True)
            con = connect()
            cur = con.execute("INSERT INTO compendio(categoria,nombre,contenido) VALUES(?,?,?)",
                              (c if ok2 else "otro", nombre.strip(), ""))
            pid = cur.lastrowid
            con.commit(); con.close()
            self._anadir_fila(pid, c if ok2 else "otro", nombre.strip())
            if (c if ok2 else "otro") in self._tablas:
                model, _, _, mapa = self._tablas[c if ok2 else "otro"]
                items = _fila_tabla(c if ok2 else "otro", nombre.strip(), "", {})
                items[0].setData(pid, R_ID)
                items[0].setData(c if ok2 else "otro", R_CAT)
                items[0].setData("", R_FUENTE)
                model.appendRow(items)
                mapa[pid] = items[0]
            self.refiltrar()

    def _pid_actual(self):
        idx = self._vista.currentIndex()
        if not idx.isValid():
            return None
        return idx.data(Qt.UserRole)

    def guardar(self):
        pid = self._pid_actual()
        if pid is None: return
        if getattr(self, "_solo_lectura", False):
            return  # filas de referencia 5eTools no se editan aquí
        # el título puede llevar [cat]; extraemos contenido tras la primera línea de fuente
        body = self.txt.toPlainText()
        if body.startswith("Fuente:"):
            body = "\n".join(body.splitlines()[2:])
        con = connect()
        con.execute("UPDATE compendio SET contenido=? WHERE id=?", (body, pid))
        con.commit(); con.close(); self.refiltrar()

    def borrar(self):
        pid = self._pid_actual()
        if pid is None: return
        con = connect()
        con.execute("DELETE FROM compendio WHERE id=?", (pid,))
        con.commit(); con.close()
        it = self._por_id.pop(pid, None)
        if it is not None and self._source is not None:
            self._source.removeRow(it.row())
        for model, _, _, mapa in self._tablas.values():
            jt = mapa.pop(pid, None)
            if jt is not None:
                model.removeRow(jt.row())
        self.refiltrar()
