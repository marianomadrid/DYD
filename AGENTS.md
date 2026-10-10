# AGENTS.md — D&D 2024 Desktop (PySide6 + SQLite)

## Ejecución
- Raíz `C:\Proyecto IA DYD`; ejecuta siempre desde ahí: `python main.py`.
- `main.py` hace `sys.path.insert(0, <root>)` y usa `from src...`; los módulos internos con relativo `from ..database import connect`. Nunca ejecutes widgets/vistas sueltos.
- Python: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`. Única dependencia: PySide6 (`requirements.txt`).
- Sin tests/linter/CI: verifica con `python -m py_compile main.py src/database.py src/motor.py src/widgets/battlemap.py src/widgets/worldmap.py src/widgets/aventura.py src/views/*.py`

## Prueba sin pantalla
- La GUI necesita pantalla; para lógica usa `QT_QPA_PLATFORM=offscreen` e instancia los widgets. Un `QMessageBox`/diálogo modal cuelga el test para siempre: parchea `exec` o llama al método directo.
## SQLite — fuente de verdad
- `src/database.py:BASE` = raíz del repo; BD en `data/dnd.db`, esquema `data/db/schema.sql`, semilla `data/seed/compendio_base.json`.
- `init_db()` corre en cada arranque con `executescript(schema.sql)`. Migrar = `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` / `ALTER TABLE ADD COLUMN` idempotente (ver `script`). Nunca `DROP`.
- La semilla solo se inserta si la tabla está vacía (`COUNT(*) == 0`); compendio con `INSERT OR IGNORE`.
- `connect()` fija `row_factory = Row` + `PRAGMA foreign_keys = ON`. Siempre `commit()` + `close()`.
- Cadena: `campanas → mapas_mundo → localizaciones → battlemaps`; `personajes.localizacion_id/battlemap_id + token_x,token_y`; niebla en `battlemap_fog(battlemap_id,cx,cy)`.

## Battlemap (`src/widgets/battlemap.py`)
- Escena única en `_reconstruir()`: fondo (z=-10) → grid → tokens (z=10) → niebla (z=20) → medición (z=30/31); el estado vive en `self._fog`, no en la escena (`clear()` lo borra).
- Modos en `self._mode` (`mover|niebla_add|niebla_del|medir`); `BattleView` solo intercepta clics en modos no-mover y debe poner `NoDrag` (si no, `ScrollHandDrag` se come los clics). Arrastre = `mouseMoveEvent` + `LeftButton`.
- `TokenItem.pid` puede ser `None` (token temporal) — `guardar_todo()` salta los `None`. `colocar_token()` usa el color real de la BD; el temporal, gris.
- `refrescar_listas()` conserva la selección de `self._battlemap_id` al reconstruir el combo — mantenerlo o vuelven duplicados/renombres perdidos. Reglas: 1 casilla = 5 pies (Chebyshev); iniciativa en memoria (d20+mod DES).

## Modo aventura (`src/motor.py`, `src/widgets/aventura.py`)
- Guiones JSON en `data/scripts/<guion>.json`: `nodos{id:{titulo,texto,retrato,opciones[{texto,ir,set,req}]}}`; `ir:null` = final. `Aventura.elegir(i)` aplica `set` (flags) y avanza; `req` oculta opciones.
- Estado por campaña en ajustes `partida:<campana_id>` (solo flags); `leer_ref("guion:nodo")` valida la referencia.
- `localizaciones.script` / `puntos_interes.script` = nodo inicial; se edita en Ciudades (campo «Guion») y se lanza con «Jugar aquí ▶» en Mapas (mundo / localización / punto). `worldmap` suma `_loc_actual()` y `_poi_actual()` con respaldo al `currentItem`.
- `DialogoAventura` escribe el texto con `QTimer` y usa `_vaciar(layout)` (takeAt + setParent(None) + sendPostedEvents) para no duplicar botones al cambiar de nodo.

## PDF a personaje (`src/pdf_import.py`)
- Mapeo por posición (`_ANCHORS`: página + x,y, tol 25pt), nunca por nombre de campo: los sufijos (`text_1imkp`) cambian en cada exportación. Recalibrar si cambia la plantilla. Verificado con `Personajes/Sacuago 9.pdf` y `Octavio_Hoja_nivel9_editable.pdf`.
- `_SKILLS`/`_SAVES` dan (habilidad/car, pos_mod, pos_box); pericia (2) si mod == base + 2×PB; expone `HABILIDADES`, `bono_competencia()`, `mod_car()`. `_box_checked` lee `/AS`, no `/V`.
- Plantilla oficial rellenable: valores impresos (no campos) -> `_estatico(words,H,rect)` como fallback; OCTAVIO = nombre y Sabio = trasfondo (anclas distintas).

## Ficha (`src/views/ficha_view.py`)
- Réplica hoja 2024 (cabecera + tarjetas FUE/DES/CON | INT/SAB/CAR + armas/rasgos + inferior); modificadores en vivo.
- `skills`/`saves` son JSON en BD (`{"Sigilo": 0|1|2}`); armas en tabla `armas` (borrado+reinserción al guardar). Tests offscreen sin diálogos modales.
- Archivos: `Personajes/<nombre>/` (PDF+foto) es el formato principal; `escanear_carpetas()` lo importa junto. `buscar_pdf/retrato()` miran carpeta y luego suelto; importar nunca pisa links.
## Compendio 5eTools (`tools/importar_5etools.py`)
- Baja JSON a `data/5etools/` y vuelca a `compendio` (fuente `5eTools · LIBRO`); reejecutar regenera solo esas filas; datos en inglés; deduplica prefiriendo XPHB/XDMG/XMM; `--limite` no borra. Monstruos/objetos/hechizos/clases guardan `datos` y se pintan HTML (solo lectura); clase trae tabla compuesta + pills (`clase_subs`); filtro por libros en `fuentes` + `fuentes_off`; la lista solo se reconstruye si cambia algo (`_sucia`), nunca se destruye nada: UN QStandardItemModel fuente (7k filas, una vez) + QSortFilterProxyModel con tope; CRUD incremental por fila.
## Arte (`src/arte.py`, `assets/`)
- Fuentes OFL con reserva serif si falta el TTF; QSS Bloodborne centralizado en `qss()`; splash y fondo vacío usan el Caronte (dominio público, ver `assets/CREDITOS.md`).

## Avisos
- QLabel con pixmap en un layout: `QSizePolicy.Ignored` + escalar a mano (`_ajustar_mapa` en worldmap) o el minimumSizeHint realimenta `resizeEvent` y la ventana crece sin fin.
- El roadmap de `README.md` está desactualizado. Fíate del código, no del README.
- `QMessageBox.Yes` vs `StandardButton.Yes`: existen ambos en el repo; prefiere `QMessageBox.StandardButton.Yes`.
- Sin texto propietario de WotC: la semilla del compendio son solo resúmenes/SRD.
## Reglas
- Este documento nunca puede tener mas de 50 líneas, todo lo que sobre genéralo en el documento memory.md
