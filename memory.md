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

## 2026-10-11 — Modo aventura jugable (Nilgotia) — REVERTIDO (ver abajo)
- (Se implementó y el mismo día se retiró a petición del usuario: no quiere
  jugar. Queda el mapa interactivo puro. Detalle histórico en git `a3b8c28`.)
- Guion `nilgotia.json` (Puerto Ceniza → taberna/sótano → chapitel, 2 finales)
  enganchado a Puerto Ceniza y Chapitel Ahogado del mundo NILGOTIA del usuario.

## 2026-10-11 — Bug esquema: coma dentro del comentario
- `imagen_path TEXT DEFAULT '' -- nota,` deja la coma DENTRO del comentario y
  `script` pega con la línea anterior → `executescript` revienta y la app no
  arranca. La coma SIEMPRE antes del `--`. También: al crear el mundo Nilgotia
  el nombre del usuario venía en mayúsculas (`NILGOTIA`) y se duplicó;
  comparar en minúsculas y unir en el mundo existente antes de sembrar.

## 2026-10-11 — Mapa interactivo sin modo juego
- El usuario no quiere jugar: fuera botones «Jugar», diálogo de aventura,
  `src/motor.py`, `src/widgets/aventura.py` y `data/scripts/nilgotia.json`.
  Ciudades pierde el campo «Guion»; el mapa queda como interactivo puro
  (clic selecciona, doble clic entra, zoom/arrastre). Col `script` en BD sin
  uso (se deja por compatibilidad); flags `partida:*` limpiados.
