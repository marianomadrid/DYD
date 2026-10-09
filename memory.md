# memory.md — Changelog (máx. 80 líneas; si se supera, resumir/eliminar)

## Regla
- Este fichero es el changelog. Máximo 80 líneas: resumir o eliminar lo viejo.

## 2026-10-05 — Scaffold + entorno
- Python 3.12 + PySide6 + SQLite en `C:\Proyecto IA DYD`; `AGENTS.md` (≤50).
- 5 pestañas; BD correlacionada (campañas→mapas→ciudades→battlemaps→pjs).
- Seed SRD, sin texto WotC; battlemap con niebla/medición/iniciativa (1 casilla = 5 pies).

## 2026-10-06 — Archivos de personaje (carpetas, PDF, retratos)
- `Personajes/<nombre>/` con PDF + foto (nombres libres); col `ficha_path`;
  Vincular/Abrir/Quitar + autodetección; `Mapas/` origen de fondos.
- Botón `Importar carpetas` (manda la carpeta, no el nombre interno del PDF);
  núcleo sin diálogos (un modal colgaba los tests offscreen).
- Retrato 150×180 en ficha con Cambiar/Quitar; `importar_archivo()` copia a
  `Retratos/<nombre>.<ext>` + ruta `/`; autodetección por nombre.

## 2026-10-06 — PDF a personaje + ficha réplica
- `pdf_import.py`: mapeo por posición (sufijos aleatorios, recalibrar si cambia
  la plantilla); Squawks verificado (Pícaro 9, 18 skills/saves); `pypdf>=5`.
- Ficha espejo de la hoja: cabecera + 6 tarjetas + 18 habilidades (—/C/E),
  6 armas, cálculo en vivo; 21 cols + tabla `armas`. Página 2 no se importa.

## 2026-10-06 — Arte Bloodborne
- Fuentes OFL (Cinzel/IM Fell/Cardo estática); Caronte de Doré (dominio
  público) + textura procedural. `src/arte.py`: QSS, splash, fondo vacío.
- OJO: verificar magia TTF `00 01 00 00` (Baskerville solo existe en variable).

## 2026-10-07 — Compendio 5eTools (7.287 entradas)
- 8 categorías con fuente `5eTools · LIBRO`; reejecutar regenera solo esas
  filas; XPHB/XDMG/XMM primero; excluye UA. Tablas `fuentes` y `ajustes`.
- Monstruos/objetos/hechizos/clases en HTML (solo lectura); statblocks con
  tabla CAR/PTOS/MOD/SALV, CR con XP/PB, iniciativa `+X (Y)` (Tiamat +0 (10)
  correcto: DES 10, fórmula exacta del site); dotes con requisito y libro.
- Clase = 16 filas con tabla compuesta (PB/rasgos/progresión/conjuros estándar
  full/half/third/pact) + pills de subclase (`clase_subs`, ninguna marcada) con
  rasgos inline por nivel (azul luna); filtro por libros en diálogo grande.
- Tablas ordenables (hechizo/objeto/dote) con clic en cabecera y claves en
  R_SORT (ritual/conc, valor/peso numéricos). OJO: `--limite` no borra.

## 2026-10-07 — Estabilidad: bucle de ventana + crasheo en lista
- Mapa vacío realimentaba resizeEvent: etiqueta Ignored + `_ajustar_mapa()`.
- Crasheo (shiboken, use-after-free): UN modelo fuente + QSortFilterProxyModel
  con tope; CERO destrucciones en sesión; CRUD incremental; debounce 250 ms;
  undo OFF; casillas una vez; `_todas` sincroniza. `faulthandler` + logs.

## 2026-10-08 — Fondos gigantes incompatibles
- Qt no abre JPEG enormes/raros (Costa de 19 MB, 10200×6600): `normalizar_fondo()`
  en arte.py crea `<nombre> (Qt).png` útil con Pillow (requiere `Pillow>=10`);
  avisos en vez de silencio al fallar. Vale para mapamundi y battlemap.

## 2026-10-08 — Zoom en el mapamundi
- Etiqueta dentro de QScrollArea + `_zoom` (0.2–8.0): botones +/-, 1:1,
  Ajustar y Ctrl+rueda; clic de ciudades sigue en relativo a la etiqueta.

## 2026-10-08 — Mapas jerárquicos + zoom
- `MapCanvas` pinta imagen + pines con nombre (clic selecciona, doble entra);
  mundo → localización (mapa propio `imagen_path`) → punto (`puntos_interes`
  con imagen opcional). Zoom Ctrl+rueda/botones en scroll; scroll Padre = viewport.

## 2026-10-08 — Arrastrar el mapa
- `MapCanvas` con pan por arrastre (botón izq. en vacío o central): mueve
  scrollbars con umbral 4px; clic quieto sigue seleccionando/creando.

## 2026-10-08 — Borrar mundo + battlemap en localización
- Botón Borrar mundo (confirma con conteos; cascada, pjs intactos) y
  `+ Battlemap aquí` en la localización (salta al mapa creado).

## 2026-10-08 — Trasfondos en tabla (Origen/Habilidades)
- Columnas Nombre/Origen/Habilidades/Libro; origen de `ability.choose`,
  habilidades con nombres completos; detalle con equipo/herramientas/dote.

## 2026-10-08 — Segunda plantilla PDF (hoja oficial rellenable)
- Detección por nombres (`Text11` vs `text_1imkp`) + mapa propio: PG actual
  vacío→máx, velocidad en metros, saves/habs por filas con valor visible
  (campo o impreso) y pericia por comparación. Botón Importar carpetas fuera.

## 2026-10-08 — Casillas se leen por /AS, no /V
- `_box_checked` manda /AS (lo visible) y si no /V; vale para muertes/armaduras.
