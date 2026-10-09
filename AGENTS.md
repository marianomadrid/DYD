# AGENTS.md — D&D 2024 Desktop (PySide6 + SQLite)

## Ejecución
- La raíz del repo es `C:\Proyecto IA DYD`. Ejecuta siempre desde la raíz: `python main.py`
- `main.py` hace `sys.path.insert(0, <root>)` y luego `from src...`; los módulos internos usan relativo `from ..database import connect`. No ejecutes los ficheros de widgets/vistas directamente.
- Python está en `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` (instalación de usuario, añadida al PATH de usuario). Única dependencia: `pip install -r requirements.txt` (PySide6).
- No hay tests, linter, typechecker ni CI. Para verificar usa: `python -m py_compile main.py src/database.py src/widgets/battlemap.py src/widgets/worldmap.py src/views/*.py`

## Prueba sin pantalla (sin display)
- La GUI necesita pantalla; para comprobar lógica usa `QT_QPA_PLATFORM=offscreen` + instanciar los widgets (patrón ya probado en las 5 vistas).

## SQLite — fuente de verdad
- `src/database.py:BASE` = raíz del repo; BD en `data/dnd.db`, esquema en `data/db/schema.sql`, semilla en `data/seed/compendio_base.json`.
- `init_db()` se ejecuta en cada arranque con `executescript(schema.sql)`. Migrar = añadir `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` a schema.sql (ver ejemplo `battlemap_fog`). Nunca `DROP` ni alterar tablas existentes en el sitio.
- La semilla solo se inserta si las tablas están vacías (`COUNT(*) == 0`); compendio con `INSERT OR IGNORE`.
- `connect()` fija `row_factory = Row` + `PRAGMA foreign_keys = ON`. Siempre `commit()` + `close()`.
- Cadena de correlación: `campanas → mapas_mundo → localizaciones → battlemaps`; `personajes.localizacion_id / battlemap_id + token_x,token_y`; niebla en `battlemap_fog(battlemap_id,cx,cy)`; enlaces genéricos en `enlaces`.

## Battlemap (`src/widgets/battlemap.py`) — peculiaridades
- Escena única en `_reconstruir()`: fondo (z=-10) → grid → tokens (z=10) → niebla (z=20) → medición (z=30/31); el estado vive en `self._fog`, no en la escena (`clear()` lo borra).
- Modos en `self._mode` (`mover|niebla_add|niebla_del|medir`); `BattleView` solo intercepta clics en modos no-mover y debe poner `NoDrag` (si no, `ScrollHandDrag` se come los clics). Pintar también gestiona arrastre vía `mouseMoveEvent` + `LeftButton`.
- `TokenItem.pid` puede ser `None` (token temporal de monstruo) — `guardar_todo()` debe saltar los `None` al escribir en `personajes`. `colocar_token()` usa el color real de la BD; el temporal usa gris.
- `refrescar_listas()` conserva la selección de `self._battlemap_id` al reconstruir el combo — mantén ese comportamiento o vuelven los duplicados/renombres perdidos.
- Reglas: 1 casilla = 5 pies (Chebyshev); iniciativa del battlemap en memoria (d20+mod DES, rondas).

## PDF a personaje (`src/pdf_import.py`)
- Mapeo por posición (`_ANCHORS`: página + x,y, tol 25pt), nunca por nombre de
  campo: los sufijos (`text_1imkp`) cambian en cada exportación. Recalibrar si
  cambia la plantilla. Parse verificado contra `Personajes/Sacuago 9.pdf`.
- `_SKILLS`/`_SAVES` dan (habilidad/car, pos_mod, pos_box); pericia (2) si mod == base + 2×PB; expone `HABILIDADES`, `bono_competencia()`, `mod_car()`.

## Ficha (`src/views/ficha_view.py`)
- Réplica hoja 2024 (cabecera + tarjetas FUE/DES/CON | INT/SAB/CAR + armas/rasgos + inferior); modificadores en vivo.
- `skills`/`saves` son JSON en BD (`{"Sigilo": 0|1|2}`); armas van en tabla
  `armas` (borrado+reinserción al guardar). Tests offscreen: sin diálogos
  modales (un `QMessageBox` colgaría el test para siempre).
- Archivos: `Personajes/<nombre>/` (PDF+foto) es el formato principal; `escanear_carpetas()` lo importa junto. `buscar_pdf/retrato()` miran carpeta y luego suelto; importar nunca pisa links.
## Compendio 5eTools (`tools/importar_5etools.py`)
- Baja JSON a `data/5etools/` y vuelca a `compendio` (fuente `5eTools · LIBRO`); reejecutar regenera solo esas filas; datos en inglés; deduplica prefiriendo XPHB/XDMG/XMM; `--limite` no borra. Monstruos/objetos/hechizos/clases guardan `datos` y se pintan HTML (solo lectura); clase trae tabla compuesta + pills (`clase_subs`); filtro por libros en `fuentes` + `fuentes_off`; la lista solo se reconstruye si cambia algo (`_sucia`), nunca se destruye nada: UN QStandardItemModel fuente (7k filas, una vez) + QSortFilterProxyModel con tope; CRUD incremental por fila.
## Arte (`src/arte.py`, `assets/`)
- Fuentes OFL con reserva serif si falta el TTF; QSS Bloodborne centralizado en `qss()`; splash y fondo vacío usan el Caronte (dominio público, ver `assets/CREDITOS.md`).

## Avisos
- QLabel con pixmap en un layout: poner QSizePolicy.Ignored y escalar a mano
  (`_ajustar_mapa` en worldmap); si no, el minimumSizeHint realimenta `resizeEvent` y la ventana crece sin fin.
- El roadmap de `README.md` está desactualizado (niebla/medición/iniciativa ya implementadas). Fíate de `battlemap.py`, no del README.
- `QMessageBox.Yes` vs `StandardButton.Yes`: ambos aparecen en el repo; prefiere `QMessageBox.StandardButton.Yes`.
- Sin texto propietario de WotC: la semilla del compendio son solo resúmenes/SRD. No subir transcripciones de manuales.
## Reglas
- Este documento nunca puede tener mas de 50 líneas, todo lo que sobre genéralo en el documento memory.md