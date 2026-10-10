# memory.md — Changelog (máx. 80 líneas; si se supera, resumir/eliminar)

## Regla
- Este fichero es el changelog. Máximo 80 líneas: resumir o eliminar lo viejo.

## Histórico resumido (2026-10-05 → 10-08)
- Scaffold PySide6+SQLite, 5 pestañas, BD correlacionada (campañas→mapas→ciudades
  →battlemaps→pjs); seed SRD; battlemap con niebla, medición e iniciativa.
- `personajes` con `ficha_path`, retrato 150×180, `Mapas/` como origen de fondos.
- `pdf_import.py` por posición + ficha réplica de la hoja 2024 (21 cols + `armas`).
- Arte Bloodborne (fuentes OFL, Caronte de Doré, QSS); `normalizar_fondo()` con
  Pillow para JPEG gigantes; zoom/arrastre en `MapCanvas`; mapas jerárquicos
  mundo→localización→punto (`imagen_path`, `puntos_interes`).
- Compendio 5eTools (7.287 entradas, 10 categorías, filtro por libros, tablas
  ordenables, statblocks/fichas HTML) y su arreglo de crash: UN modelo fuente +
  QSortFilterProxyModel sin destrucciones, debounce 250 ms, `faulthandler`+logs.
- Trasfondos en tabla; segunda plantilla PDF (hoja oficial rellenable, /AS).

## 2026-10-10 — PDF: OCTAVIO es el nombre, Sabio el trasfondo
- La plantilla oficial imprime el nombre arriba y rellena solo trasfondo/clase:
  anclas separadas (`nombre` 756 → `trasfondo` 737 → `clase_sola` 151/737).
- Fallback a texto impreso `_estatico(words,H,rect)` cuando el campo viene vacío
  (hoja oficial); rasgos de clase y dotes en `rasgos_clase`+`pericia`.
- Verificado con Octavio (Artífice Artillero 9, PG 93/93, 6 armas) y Squawks.

## 2026-10-10 — Subida a GitHub
- git instalado con winget; `.gitignore` (BD, PDF, retratos, mapas, 5eTools,
  logs y `__pycache__` NO se suben); commit `c10c2e9` → `marianomadrid/DYD`.
- Token fino de un solo uso; el usuario debe revocarlo tras el push.

## 2026-10-11 — Modo aventura jugable (Nilgotia)
- `src/motor.py`: guiones JSON en `data/scripts/` con `nodos` (titulo/texto/
  retrato/opciones), `set` (flags) y `req`; estado por campaña en ajustes
  `partida:<id>`; `leer_ref("guion:nodo")`; `ir:null` = final.
- `src/widgets/aventura.py`: `DialogoAventura` con texto progresivo (QTimer) y
  botones de opción; `_vaciar(layout)` (takeAt + setParent(None) +
  sendPostedEvents) evita duplicar botones; sin diálogos modales al testar.
- Col `script` en `localizaciones` y `puntos_interes` (migración + schema.sql);
  se edita en Ciudades («Guion (aventura)») y se lanza con «Jugar aquí ▶» en
  Mapas (mundo/localización/punto) vía `_loc_actual()`/`_poi_actual()`.
- Guion `nilgotia.json` (Puerto Ceniza → taberna/sótano → chapitel, 2 finales)
  enganchado a Puerto Ceniza y Chapitel Ahogado del mundo NILGOTIA del usuario.

## 2026-10-11 — Bug esquema: coma dentro del comentario
- `imagen_path TEXT DEFAULT '' -- nota,` deja la coma DENTRO del comentario y
  `script` pega con la línea anterior → `executescript` revienta y la app no
  arranca. La coma SIEMPRE antes del `--`. También: al crear el mundo Nilgotia
  el nombre del usuario venía en mayúsculas (`NILGOTIA`) y se duplicó;
  comparar en minúsculas y unir en el mundo existente antes de sembrar.
