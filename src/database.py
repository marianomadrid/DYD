"""Capa SQLite: crea schema, seed y expone CRUD mínimo."""
import json
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB_PATH = DATA / "dnd.db"
SCHEMA = DATA / "db" / "schema.sql"
SEED = DATA / "seed" / "compendio_base.json"

# Columnas añadidas tras el scaffold: para BDs viejas se migran con ADD COLUMN.
NUEVAS_COLUMNAS_PERSONAJE = [
    ("ficha_path", "TEXT DEFAULT ''"),
    ("trasfondo", "TEXT DEFAULT ''"),
    ("subclase", "TEXT DEFAULT ''"),
    ("pg_temp", "INTEGER DEFAULT 0"),
    ("dados_golpe", "TEXT DEFAULT ''"),
    ("velocidad", "INTEGER DEFAULT 30"),
    ("tamano", "TEXT DEFAULT ''"),
    ("inspiracion", "INTEGER DEFAULT 0"),
    ("inspiracion_heroica", "INTEGER DEFAULT 0"),
    ("mu_exitos", "INTEGER DEFAULT 0"),
    ("mu_fracasos", "INTEGER DEFAULT 0"),
    ("iniciativa_bono", "INTEGER DEFAULT 0"),
    ("competencias", "TEXT DEFAULT ''"),
    ("equipo", "TEXT DEFAULT ''"),
    ("idiomas", "TEXT DEFAULT ''"),
    ("herramientas", "TEXT DEFAULT ''"),
    ("rasgos", "TEXT DEFAULT ''"),
    ("rasgos_especie", "TEXT DEFAULT ''"),
    ("dotes", "TEXT DEFAULT ''"),
    ("skills", "TEXT DEFAULT '{}'"),
    ("saves", "TEXT DEFAULT '{}'"),
    ("retrato_path", "TEXT DEFAULT ''"),
]

# Carpetas de usuario (creadas por el usuario en la raíz del repo)
PERSONAJES_DIR = BASE / "Personajes"  # fichas de personaje en PDF
MAPAS_DIR = BASE / "Mapas"  # imágenes de mapas para fondos
RETRATOS_DIR = BASE / "Retratos"  # imágenes de personaje para la ficha


def importar_archivo(origen, carpeta, nombre_base):
    """Copia un archivo a la carpeta del repo y devuelve su ruta relativa.

    Ej: importar_archivo("C:/fotos/mago.png", RETRATOS_DIR, "Squawks")
    -> "Retratos/Squawks.png" (sobrescribe si ya existe).
    """
    import os
    import re
    import shutil
    src = Path(origen)
    seguro = re.sub(r"[^\w\- ]", "", Path(nombre_base).stem).strip() or "archivo"
    destino = Path(carpeta) / f"{seguro}{src.suffix.lower()}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != destino.resolve():
        shutil.copy2(src, destino)
    return str(destino.relative_to(BASE)).replace(os.sep, "/")


IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _rel(p: Path) -> str:
    return str(p.relative_to(BASE)).replace(os.sep, "/")


def _carpeta_personaje(nombre):
    """Subcarpeta Personajes/<nombre>/ si existe (insensible a mayúsculas)."""
    if not nombre or not PERSONAJES_DIR.exists():
        return None
    bajo = nombre.strip().lower()
    for d in PERSONAJES_DIR.iterdir():
        if d.is_dir() and d.name.strip().lower() == bajo:
            return d
    return None


def buscar_pdf(nombre) -> str:
    """PDF de la ficha: Personajes/<nombre>/*.pdf, si no Personajes/<nombre>.pdf."""
    d = _carpeta_personaje(nombre)
    if d is not None:
        pdfs = sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")
        if pdfs:
            return _rel(pdfs[0])
    if not nombre:
        return ""
    cand = PERSONAJES_DIR / f"{nombre.strip()}.pdf"
    return _rel(cand) if cand.exists() else ""


def buscar_retrato(nombre) -> str:
    """Foto: Personajes/<nombre>/imagen, si no Retratos/<nombre>.<ext>."""
    d = _carpeta_personaje(nombre)
    if d is not None:
        imgs = sorted(f for f in d.iterdir()
                      if f.is_file() and f.suffix.lower() in IMG_EXTS)
        if imgs:
            return _rel(imgs[0])
    if not nombre or not RETRATOS_DIR.exists():
        return ""
    bajo = nombre.strip().lower()
    for f in RETRATOS_DIR.iterdir():
        if f.is_file() and f.stem.strip().lower() == bajo \
                and f.suffix.lower() in IMG_EXTS:
            return _rel(f)
    return ""


def escanear_carpetas() -> list:
    """[{nombre, pdf, retrato}] por cada subcarpeta de Personajes/ con PDF o foto."""
    out = []
    if not PERSONAJES_DIR.exists():
        return out
    for d in sorted(PERSONAJES_DIR.iterdir()):
        if not d.is_dir():
            continue
        pdfs = sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")
        imgs = sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXTS)
        if pdfs or imgs:
            out.append({"nombre": d.name,
                        "pdf": _rel(pdfs[0]) if pdfs else "",
                        "retrato": _rel(imgs[0]) if imgs else ""})
    return out


def connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    con = connect()
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    # Migración ligera para BDs creadas antes de cada columna (sin DROP ni ALTER destructivos)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(personajes)").fetchall()}
    for col, ddl in NUEVAS_COLUMNAS_PERSONAJE:
        if col not in cols:
            con.execute(f"ALTER TABLE personajes ADD COLUMN {col} {ddl}")
    ccols = {r["name"] for r in con.execute("PRAGMA table_info(compendio)").fetchall()}
    if "datos" not in ccols:
        con.execute("ALTER TABLE compendio ADD COLUMN datos TEXT DEFAULT '{}'")
    lcols = {r["name"] for r in con.execute("PRAGMA table_info(localizaciones)").fetchall()}
    if "imagen_path" not in lcols:
        con.execute("ALTER TABLE localizaciones ADD COLUMN imagen_path TEXT DEFAULT ''")
    if "script" not in lcols:
        con.execute("ALTER TABLE localizaciones ADD COLUMN script TEXT DEFAULT ''")
    try:
        pcols = {r["name"] for r in con.execute("PRAGMA table_info(puntos_interes)").fetchall()}
        if "script" not in pcols:
            con.execute("ALTER TABLE puntos_interes ADD COLUMN script TEXT DEFAULT ''")
    except Exception:
        pass
    PERSONAJES_DIR.mkdir(parents=True, exist_ok=True)
    MAPAS_DIR.mkdir(parents=True, exist_ok=True)
    RETRATOS_DIR.mkdir(parents=True, exist_ok=True)
    # Seed compendio solo si está vacío
    n = con.execute("SELECT COUNT(*) c FROM compendio").fetchone()["c"]
    if n == 0 and SEED.exists():
        items = json.loads(SEED.read_text(encoding="utf-8"))
        con.executemany(
            "INSERT OR IGNORE INTO compendio(categoria,nombre,fuente,contenido) VALUES(?,?,?,?)",
            [(i["categoria"], i["nombre"], i.get("fuente", ""), i.get("contenido", "")) for i in items],
        )
    # Campaña + datos de ejemplo si BD vacía
    n = con.execute("SELECT COUNT(*) c FROM campanas").fetchone()["c"]
    if n == 0:
        cur = con.execute("INSERT INTO campanas(nombre,descripcion) VALUES(?,?)",
                          ("Mi primera campaña", "Campaña de ejemplo. Edítala o crea la tuya."))
        camp_id = cur.lastrowid
        mm = con.execute("INSERT INTO mapas_mundo(campana_id,nombre,notas) VALUES(?,?,?)",
                         (camp_id, "Faerûn (ejemplo)", "Sube tu imagen de mapa en la pestaña Mapas.")).lastrowid
        loc1 = con.execute(
            "INSERT INTO localizaciones(mapa_mundo_id,nombre,tipo,descripcion,x,y) VALUES(?,?,?,?,?,?)",
            (mm, "Puerta de Baldur", "ciudad", "Gran ciudad portuaria en la Costa de la Espada.", 0.35, 0.55)).lastrowid
        loc2 = con.execute(
            "INSERT INTO localizaciones(mapa_mundo_id,nombre,tipo,descripcion,x,y) VALUES(?,?,?,?,?,?)",
            (mm, "Mazmorra Olvidada", "mazmorra", "Ruina para la primera sesión.", 0.65, 0.35)).lastrowid
        bm = con.execute(
            "INSERT INTO battlemaps(localizacion_id,nombre,ancho_celdas,alto_celdas,px_celda) VALUES(?,?,?,?,?)",
            (loc2, "Sala inicial", 20, 14, 50)).lastrowid
        con.execute(
            "INSERT INTO personajes(campana_id,nombre,clase,especie,nivel,pg_actual,pg_max,ca,localizacion_id,battlemap_id,token_x,token_y,color) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (camp_id, "Kael", "Guerrero", "Humano", 1, 12, 12, 16, loc1, bm, 3, 4, "#e74c3c"))
        con.execute(
            "INSERT INTO personajes(campana_id,nombre,clase,especie,nivel,pg_actual,pg_max,ca,localizacion_id,battlemap_id,token_x,token_y,color) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (camp_id, "Lyra", "Mago", "Elfo", 1, 8, 8, 12, loc1, bm, 5, 6, "#3498db"))
    con.commit()
    con.close()


def get_ajuste(clave, defecto=""):
    con = connect()
    r = con.execute("SELECT valor FROM ajustes WHERE clave=?", (clave,)).fetchone()
    con.close()
    return r["valor"] if r else defecto


def set_ajuste(clave, valor):
    con = connect()
    con.execute("INSERT INTO ajustes(clave,valor) VALUES(?,?) "
                "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (clave, valor))
    con.commit(); con.close()
