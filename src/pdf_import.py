"""Importar fichas de personaje desde PDF (hoja oficial D&D 2024).

Los nombres internos de los campos (/T como 'text_1imkp') llevan sufijos
aleatorios que cambian en cada exportación, así que el mapeo es POR POSICIÓN
(página + esquina inferior-izquierda del widget, tolerancia 25pt en Manhattan),
no por nombre. Si WotC cambia la plantilla, recalibrar las tablas con un volcado.
"""
from pathlib import Path
import re

TOL = 25.0

# (clave, página, x, y)
_ANCHORS = [
    ("nombre", 0, 25, 744),
    ("clase_trasfondo", 0, 25, 723),
    ("especie_subclase", 0, 24, 700),
    ("nivel", 0, 262, 728),
    ("px", 0, 255, 706),
    ("ca", 0, 325, 726),
    ("pg", 0, 380, 703),
    ("pg_temp", 0, 439, 703),
    ("pg_max", 0, 325, 710),
    ("dados_golpe", 0, 491, 702),
    ("bono_comp", 0, 45, 607),
    ("iniciativa", 0, 244, 629),
    ("velocidad", 0, 339, 629),
    ("tamano", 0, 433, 630),
    ("percepcion_pasiva", 0, 528, 630),
    ("fue", 0, 64, 538),
    ("des", 0, 64, 420),
    ("con", 0, 64, 274),
    ("int", 0, 170, 615),
    ("sab", 0, 170, 442),
    ("car", 0, 171, 268),
    ("heroica", 0, 52, 177),
    ("alineamiento", 1, 413, 471),
    ("idiomas", 1, 409, 397),
    ("equipo", 1, 407, 186),
    ("herramientas", 0, 13, 11),
    ("comp_armas", 0, 12, 56),
    ("rasgos_especie", 0, 223, 12),
    ("dotes", 0, 408, 12),
    ("rasgos_clase", 0, 223, 216),
    ("pericia", 0, 407, 216),
]

# (habilidad ES, caracter, x_mod, y_mod, x_box, y_box) — página 0
_SKILLS = [
    ("Atletismo", "FUE", 28, 485, 16, 484),
    ("Acrobacias", "DES", 29, 367, 16, 366),
    ("Juego de manos", "DES", 28, 353, 16, 353),
    ("Sigilo", "DES", 28, 339, 16, 338),
    ("Arcana", "INT", 135, 562, 121, 562),
    ("Historia", "INT", 134, 548, 122, 548),
    ("Investigación", "INT", 134, 534, 122, 533),
    ("Naturaleza", "INT", 135, 520, 122, 519),
    ("Religión", "INT", 134, 506, 123, 505),
    ("Trato con animales", "SAB", 134, 388, 121, 388),
    ("Perspicacia", "SAB", 134, 374, 122, 373),
    ("Medicina", "SAB", 134, 359, 122, 360),
    ("Percepción", "SAB", 134, 346, 122, 346),
    ("Supervivencia", "SAB", 134, 332, 122, 331),
    ("Engaño", "CAR", 135, 214, 122, 214),
    ("Intimidación", "CAR", 135, 200, 122, 199),
    ("Interpretación", "CAR", 134, 185, 122, 184),
    ("Persuasión", "CAR", 134, 172, 122, 171),
]

# (caracter, x_mod, y_mod, x_box, y_box) — salvaciones, página 0
_SAVES = [
    ("FUE", 28, 504, 15, 504),
    ("DES", 28, 386, 16, 386),
    ("CON", 29, 241, 15, 240),
    ("INT", 135, 582, 122, 581),
    ("SAB", 134, 408, 122, 407),
    ("CAR", 134, 234, 122, 234),
]

# Listas públicas para la vista Ficha (misma información sin coordenadas)
HABILIDADES = [(h, c) for h, c, *_ in _SKILLS]
CARACTERISTICAS = ["FUE", "DES", "CON", "INT", "SAB", "CAR"]
NOMBRE_CAR = {"FUE": "Fuerza", "DES": "Destreza", "CON": "Constitución",
              "INT": "Inteligencia", "SAB": "Sabiduría", "CAR": "Carisma"}


def bono_competencia(nivel):
    return 2 + (max(1, nivel) - 1) // 4


def mod_car(score):
    return (score - 10) // 2

# Muerte: 3 éxitos + 3 fracasos (página 0); armadura lig/media/pesada/escudos
_MU_EX = [(540, 725), (552, 725), (564, 725)]
_MU_FR = [(540, 703), (552, 703), (563, 703)]
_ARMOR = [("ligera", 58, 120), ("media", 92, 121), ("pesada", 136, 122), ("escudos", 174, 121)]

# Filas de armas: (nombre, atk, daño, notas) — página 0
_ARMAS = [
    ((223, 562), (337, 562), (384, 562), (462, 561)),
    ((223, 542), (337, 542), (384, 542), (462, 542)),
    ((223, 523), (337, 523), (384, 523), (462, 522)),
    ((223, 504), (337, 504), (384, 504), (462, 503)),
    ((223, 484), (337, 484), (384, 484), (462, 484)),
    ((223, 464), (336, 464), (384, 465), (462, 464)),
]

_CLASES_EN_ES = {
    "barbarian": "Bárbaro", "bard": "Bardo", "cleric": "Clérigo", "druid": "Druida",
    "fighter": "Guerrero", "monk": "Monje", "paladin": "Paladín", "ranger": "Explorador",
    "rogue": "Pícaro", "sorcerer": "Hechicero", "warlock": "Brujo", "wizard": "Mago",
    "artificer": "Artífice",
}
_CLASES_ES = {"bárbaro", "bardo", "clérigo", "druida", "guerrero", "monje", "paladín",
              "explorador", "pícaro", "hechicero", "brujo", "mago", "artífice"}
_ESPECIES = {"humano", "elfo", "enano", "halfling", "tiefling", "orco", "gnomo",
             "dracónido", "tabaxi", "aasimar", "goliath", "genasi", "semielfo",
             "semiorco", "kenku", "tortle", "kobold", "trasgo", "goblin",
             "human", "elf", "dwarf", "orc", "dragonborn", "half-elf", "half-orc"}


def _widgets_por_pagina(reader):
    paginas = []
    for page in reader.pages:
        ws = []
        for a in list(page.annotations or []):
            o = a.get_object()
            rect = o.get("/Rect")
            if rect is None:
                continue
            cur, nombre = o, ""
            for _ in range(5):
                t = cur.get("/T")
                if t:
                    nombre = str(t)
                    break
                cur = cur.get("/Parent")
                if cur is None:
                    break
                try:
                    cur = cur.get_object()
                except Exception:
                    break
            if not nombre:
                continue
            x0, y0, x1, y1 = (float(v) for v in rect)
            ws.append({"nombre": nombre, "x": float(x0), "y": float(y0),
                       "rect": (x0, y0, x1, y1), "ann": o})
        paginas.append(ws)
    return paginas


def _widget_cerca(paginas, pag, x, y):
    mejor, bd = None, float("inf")
    if 0 <= pag < len(paginas):
        for w in paginas[pag]:
            dd = abs(w["x"] - x) + abs(w["y"] - y)
            if dd < bd:
                mejor, bd = w, dd
    return mejor, bd


def _cerca(paginas, pag, x, y):
    """Nombre del widget más cercano a (x, y) y su distancia Manhattan."""
    w, d = _widget_cerca(paginas, pag, x, y)
    return (w["nombre"], d) if w else ("", float("inf"))


def _checked(val) -> bool:
    return str(val).startswith("/Yes")


def _box_checked(w, f_val):
    """Estado real de una casilla: manda /AS (lo que se ve), si no /V."""
    try:
        a = str(((w or {}).get("ann") or {}).get("/AS", "") or "")
    except Exception:
        a = ""
    if a and a != "/Off":
        return True
    if a == "/Off":
        return False
    return _checked(f_val)


def _caja_marcada(paginas, val, pag, x, y, tol=TOL):
    w, d = _widget_cerca(paginas, pag, x, y)
    return bool(w) and d <= tol and _box_checked(w, val(w["nombre"]))


def parse_ficha_pdf(path) -> dict:
    """Extrae los datos de la ficha (plantilla export u oficial rellenable)."""
    from pypdf import PdfReader
    reader = PdfReader(str(Path(path)))
    fields = reader.get_fields() or {}

    def val(nombre):
        try:
            v = (fields.get(nombre) or {}).get("/V", "")
            return "" if v is None else str(v).strip()
        except Exception:
            return ""

    paginas = _widgets_por_pagina(reader)
    nombres = [w["nombre"] for pags in paginas for w in pags]
    if any(re.match(r"^Text\d+$", n or "") for n in nombres):
        datos = _leer_oficial(paginas, val, str(path))
    else:
        datos = _leer_export(paginas, val)
    if not datos.get("nombre") and not datos.get("clase_trasfondo"):
        raise ValueError("No reconozco esta plantilla de ficha (¿hoja oficial 2024?).")
    return _normalizar(datos)


def _leer_export(paginas, val):
    datos = {}
    for clave, pag, x, y in _ANCHORS:
        nombre, d = _cerca(paginas, pag, x, y)
        datos[clave] = val(nombre) if d <= TOL else ""

    nivel = max(1, min(20, _num(datos.get("nivel"), 1)))
    pb = _num(datos.get("bono_comp"), 0) or (2 + (nivel - 1) // 4)
    mods = {c: _mod(_num(datos.get(k.lower()))) for c, k in
            (("FUE", "fue"), ("DES", "des"), ("CON", "con"),
             ("INT", "int"), ("SAB", "sab"), ("CAR", "car"))}

    skills, saves = {}, {}
    for hab, car, xm, ym, xb, yb in _SKILLS:
        nm, dm = _cerca(paginas, 0, xm, ym)
        wb, db = _widget_cerca(paginas, 0, xb, yb)
        m = _num(val(nm)) if dm <= TOL else mods[car]
        prof = _box_checked(wb, val(wb["nombre"])) if wb and db <= TOL else (m == mods[car] + pb)
        if prof and m == mods[car] + 2 * pb:
            skills[hab] = 2
        elif prof or m == mods[car] + pb:
            skills[hab] = 1
        else:
            skills[hab] = 0
    for car, xm, ym, xb, yb in _SAVES:
        wb, db = _widget_cerca(paginas, 0, xb, yb)
        saves[car] = 1 if (wb and db <= TOL and _box_checked(wb, val(wb["nombre"]))) else 0

    ex = sum(1 for x, y in _MU_EX if _caja_marcada(paginas, val, 0, x, y))
    fr = sum(1 for x, y in _MU_FR if _caja_marcada(paginas, val, 0, x, y))
    armor = [n for n, x, y in _ARMOR if _caja_marcada(paginas, val, 0, x, y)]

    armas = []
    for (xn, yn), (xa, ya), (xd, yd), (xno, yno) in _ARMAS:
        n = val(_cerca(paginas, 0, xn, yn)[0])
        if not n.strip():
            continue
        armas.append({"nombre": n.strip(),
                      "atk": val(_cerca(paginas, 0, xa, ya)[0]).strip(),
                      "dano": val(_cerca(paginas, 0, xd, yd)[0]).strip(),
                      "notas": val(_cerca(paginas, 0, xno, yno)[0]).strip()})
    datos.update({"skills": skills, "saves": saves, "mu_exitos": ex,
                  "mu_fracasos": fr, "armadura": armor, "armas": armas,
                  "pb": pb})
    return datos


# ---- plantilla 2: hoja oficial rellenable (campos 'Text11', 'Check Box3'...) ----
_ANCHORS_OFICIAL = [
    ("nombre", 0, 27, 758),
    ("trasfondo", 0, 25, 737),
    ("clase_sola", 0, 151, 737),
    ("especie_sola", 0, 25, 715),
    ("subclase", 0, 151, 715),
    ("nivel", 0, 266, 741),
    ("ca", 0, 326, 729),
    ("pg_actual", 0, 384, 716),
    ("pg_max", 0, 445, 716),
    ("pg_temp", 0, 445, 738),
    ("dados_golpe", 0, 500, 716),
    ("iniciativa", 0, 245, 635),
    ("velocidad_raw", 0, 338, 635),
    ("tamano", 0, 437, 634),
    ("percepcion_pasiva", 0, 529, 634),
    ("fue", 0, 64, 547),
    ("des", 0, 64, 428),
    ("con", 0, 63, 280),
    ("int", 0, 172, 626),
    ("sab", 0, 172, 450),
    ("car", 0, 170, 273),
    ("alineamiento", 1, 419, 482),
    ("idiomas", 1, 419, 408),
    ("rasgos_a", 0, 232, 228),
    ("rasgos_b", 0, 418, 229),
    ("rasgos_especie", 0, 232, 22),
    ("dotes", 0, 419, 21),
    ("comp_armas", 0, 18, 60),
    ("herramientas", 0, 17, 30),
]
_MU_EX_OF = [(550, 739), (561, 739), (572, 739)]
_MU_FR_OF = [(549, 717), (561, 717), (572, 717)]
_ARMOR_OFICIAL = [("ligera", 60, 126), ("media", 94, 126),
                  ("pesada", 139, 126), ("escudos", 177, 126)]
# (car, xmod_min, xmod_max, y_lo, y_hi, y_puntuación, slots en orden visual)
_BANDAS_OFICIAL = [
    ("FUE", 25, 46, 490, 556, 547, ["save", "Atletismo"]),
    ("DES", 25, 46, 340, 436, 428, ["save", "Acrobacias", "Juego de manos", "Sigilo"]),
    ("CON", 25, 46, 232, 288, 280, ["save"]),
    ("INT", 129, 146, 500, 613, 626, ["save", "Arcana", "Historia", "Investigación",
                                      "Naturaleza", "Religión"]),
    ("SAB", 129, 146, 335, 446, 450, ["save", "Trato con animales", "Perspicacia",
                                      "Medicina", "Percepción", "Supervivencia"]),
    ("CAR", 129, 146, 170, 266, 273, ["save", "Engaño", "Intimidación",
                                      "Interpretación", "Persuasión"]),
]
_ARMAS_OFICIAL_YS = [573, 553, 533, 514, 494, 474]


def _palabras_pagina(path, pno):
    from pymupdf import open as _open
    doc = _open(str(path))
    try:
        pg = doc[pno]
        H = pg.rect.height
        return pg.get_text("words"), H
    finally:
        doc.close()


def _estatico(words, H, rect):
    x0, y0, x1, y1 = rect
    return " ".join(w[4] for w in words
                    if w[0] >= x0 - 2 and w[2] <= x1 + 2
                    and (H - w[3]) >= y0 - 2 and (H - w[1]) <= y1 + 2)


def _leer_oficial(paginas, val, path):
    try:
        words0, H0 = _palabras_pagina(path, 0)
    except Exception:
        words0, H0 = [], 0
    try:
        words1, H1 = _palabras_pagina(path, 1)
    except Exception:
        words1, H1 = [], 0
    _W = {0: (words0, H0), 1: (words1, H1)}

    def leer(pag, x, y):
        w, d = _widget_cerca(paginas, pag, x, y)
        if not w or d > TOL:
            return ""
        v = val(w["nombre"]).strip()
        if v:
            return v
        words, H = _W.get(pag, ([], 0))
        r = w.get("rect")
        if words and H > 0 and r:
            return _estatico(words, H, r).strip()
        return v

    datos = {}
    for clave, pag, x, y in _ANCHORS_OFICIAL:
        datos[clave] = leer(pag, x, y)
    # PG actual vacío -> se asume lleno (máximo)
    if not datos.get("pg_actual", "").strip() and datos.get("pg_max", "").strip():
        datos["pg_actual"] = datos["pg_max"]
    datos["pg"] = datos.pop("pg_actual", "")
    m = re.search(r"\d+", datos.get("velocidad_raw", ""))
    datos["velocidad"] = m.group(0) if m else "30"
    datos["metros"] = "m" in datos.get("velocidad_raw", "").lower()
    datos["clase_trasfondo"] = datos.pop("clase_sola", "")
    datos["especie_subclase"] = (datos.pop("especie_sola", "") + " "
                                 + datos.pop("subclase", "")).strip()
    nivel = max(1, min(20, _num(datos.get("nivel"), 1)))
    datos["nivel"] = str(nivel)
    pb = 2 + (nivel - 1) // 4
    mods = {c: _mod(_num(datos.get(k.lower()))) for c, k in
            (("FUE", "fue"), ("DES", "des"), ("CON", "con"),
             ("INT", "int"), ("SAB", "sab"), ("CAR", "car"))}
    # widgets de la pág. 0 con rect para emparejar y leer estático
    mods_w = [w for w in paginas[0] if "rect" in w]
    words, H = _W[0]
    by_name = {}
    for w in mods_w:
        by_name[w["nombre"]] = w

    def valor_mod(w, es_box=False):
        v = val(w["nombre"]).strip()
        if v or not words or H <= 0:
            return v
        r = w.get("rect")
        return _estatico(words, H, r).strip() if r else v

    skills, saves = {}, {}
    for car, x0, x1, y_lo, y_hi, y_score, slots in _BANDAS_OFICIAL:
        cands = sorted(
            (w for w in mods_w if x0 <= w["x"] <= x1 and y_lo <= w["y"] <= y_hi
             and abs(w["y"] - y_score) > 8),  # fuera el modificador gordo del círculo
            key=lambda w: -w["y"])
        # agrupa por fila (|dy|<=8) quedándose con el primero de cada fila
        filas = []
        for w in cands:
            if not filas or abs(filas[-1][0] - w["y"]) > 8:
                filas.append((w["y"], w))
        for (slot, (_ry, mw)) in zip(slots, filas):
            bv, bd = _cerca_caja(mods_w, mw["x"], mw["y"])
            mod_txt = valor_mod(mw)
            m = _num(mod_txt, None) if mod_txt not in ("", None) else None
            if m is None:
                m = mods[car]
            prof = _box_checked(bv, valor_mod(bv)) if bv else (m == mods[car] + pb)
            if slot == "save":
                saves[car] = 1 if (prof or m == mods[car] + pb) else 0
                continue
            if prof and m == mods[car] + 2 * pb:
                skills[slot] = 2
            elif prof or m == mods[car] + pb:
                skills[slot] = 1
            else:
                skills[slot] = 0
        for slot in slots[len(filas):]:
            (saves if slot == "save" else skills).__setitem__(
                slot if slot != "save" else car, 0)
    ex = sum(1 for x, y in _MU_EX_OF if _caja_marcada(paginas, val, 0, x, y))
    fr = sum(1 for x, y in _MU_FR_OF if _caja_marcada(paginas, val, 0, x, y))
    datos["armadura"] = [n for n, x, y in _ARMOR_OFICIAL
                         if _caja_marcada(paginas, val, 0, x, y, tol=12)]
    datos["herramientas"] = datos.get("herramientas", "")
    datos["equipo"] = ""
    datos["idiomas"] = datos.get("idiomas", "")
    datos["rasgos_clase"] = "\n".join(t for t in
                                      (datos.pop("rasgos_a", ""), datos.pop("rasgos_b", ""))
                                      if t.strip())
    datos["rasgos_especie"] = datos.get("rasgos_especie", "")
    datos["dotes"] = datos.get("dotes", "")
    datos["skills"] = {h: skills.get(h, 0) for _, _, _, _, _, _, ss in _BANDAS_OFICIAL for h in ss if h != "save"}
    datos["saves"] = {c: saves.get(c, 0) for c, _, _, _, _, _, _ in _BANDAS_OFICIAL}
    datos.update({"mu_exitos": ex, "mu_fracasos": fr, "armas": _armas_oficial(paginas, val),
                  "pb": pb})
    return datos


def _cerca_caja(mods_w, mx, my):
    """Caja más cercana a la izquierda del mod (dx -35..-5, |dy|<=8)."""
    mejor, bd = None, float("inf")
    for w in mods_w:
        dx, dy = w["x"] - mx, w["y"] - my
        if -35 <= dx <= -5 and abs(dy) <= 8:
            d = abs(dx) + abs(dy)
            if d < bd:
                mejor, bd = w, d
    return mejor, bd


def _armas_oficial(paginas, val):
    armas = []
    for yn in _ARMAS_OFICIAL_YS:
        fila = [w for w in paginas[0]
                if w["y"] >= yn - 9 and w["y"] <= yn + 9 and w["x"] >= 200]
        fila.sort(key=lambda w: w["x"])
        if not fila:
            continue
        vals = [val(w["nombre"]).strip() for w in fila[:4]]
        while len(vals) < 4:
            vals.append("")
        if not vals[0]:
            continue
        armas.append({"nombre": vals[0], "atk": vals[1],
                      "dano": vals[2], "notas": vals[3]})
    return armas


def _num(txt, por_defecto=10):
    try:
        return int(str(txt).replace("+", "").strip() or por_defecto)
    except (ValueError, TypeError):
        return por_defecto


def _mod(score):
    return (score - 10) // 2


def _split_clase(txt):
    toks = txt.split()
    for i in range(len(toks) - 1, -1, -1):
        low = toks[i].lower()
        if low in _CLASES_EN_ES:
            return " ".join(toks[:i]).strip(), _CLASES_EN_ES[low]
        if low in _CLASES_ES:
            return " ".join(toks[:i]).strip(), toks[i]
    return "", txt.strip()


def _split_especie(txt):
    toks = txt.split()
    if toks and toks[0].lower().strip(",") in _ESPECIES:
        return toks[0], " ".join(toks[1:]).strip()
    return txt.strip(), ""


def _normalizar(d: dict) -> dict:
    trasfondo, clase = _split_clase(d.get("clase_trasfondo", ""))
    if d.get("trasfondo", "").strip():
        trasfondo = d["trasfondo"].strip()  # plantilla oficial: campo propio
    especie, subclase = _split_especie(d.get("especie_subclase", ""))
    pg = _num(d.get("pg"), 10)
    pg_max = _num(d.get("pg_max"), 0) or pg
    des_mod = _mod(_num(d.get("des")))
    try:
        ini_pdf = int(str(d.get("iniciativa", "")).replace("+", "").strip())
        ini_bono = ini_pdf - des_mod
    except (ValueError, TypeError):
        ini_bono = 0
    comp = []
    if d.get("armadura"):
        comp.append("Armadura: " + ", ".join(d["armadura"]))
    if d.get("comp_armas", "").strip():
        comp.append("Armas: " + d["comp_armas"].strip())
    partes = [f"Percepción pasiva: {d['percepcion_pasiva'].strip()}"] if d.get("percepcion_pasiva", "").strip() else []
    if d.get("iniciativa", "").strip():
        partes.append(f"Iniciativa en ficha: {d['iniciativa'].strip()}")
    if d.get("metros"):
        partes.append("Velocidad en metros (hoja en español).")
    return {
        "nombre": d.get("nombre", "").strip() or "Sin nombre",
        "clase": clase, "especie": especie, "trasfondo": trasfondo, "subclase": subclase,
        "nivel": max(1, min(20, _num(d.get("nivel"), 1))),
        "px": _num(d.get("px"), 0),
        "alineamiento": d.get("alineamiento", "").strip(),
        "ca": _num(d.get("ca"), 10),
        "pg_actual": pg, "pg_max": pg_max, "pg_temp": _num(d.get("pg_temp"), 0),
        "dados_golpe": d.get("dados_golpe", "").strip(),
        "velocidad": _num(d.get("velocidad"), 30),
        "tamano": d.get("tamano", "").strip(),
        "inspiracion_heroica": 1 if _checked(d.get("heroica", "")) else 0,
        "mu_exitos": d.get("mu_exitos", 0), "mu_fracasos": d.get("mu_fracasos", 0),
        "iniciativa_bono": ini_bono,
        "fuerza": _num(d.get("fue")), "destreza": _num(d.get("des")),
        "constitucion": _num(d.get("con")), "inteligencia": _num(d.get("int")),
        "sabiduria": _num(d.get("sab")), "carisma": _num(d.get("car")),
        "competencias": " | ".join(comp),
        "equipo": d.get("equipo", "").strip(),
        "idiomas": d.get("idiomas", "").strip(),
        "herramientas": d.get("herramientas", "").strip(),
        "rasgos": " ".join(x.strip() for x in (d.get("rasgos_clase", ""), d.get("pericia", "")) if x.strip()),
        "rasgos_especie": d.get("rasgos_especie", "").strip(),
        "dotes": d.get("dotes", "").strip(),
        "skills": d.get("skills", {}), "saves": d.get("saves", {}),
        "armas": d.get("armas", []),
        "retrato_path": "",
        "notas": "\n".join(partes),
    }
