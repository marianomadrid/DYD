# D&D 2024 - App de Campaña Desktop

App de escritorio para D&D 2024 (en español) con:
- Mapas interactivos de mundo (ciudades / localizaciones con pines)
- Creador de mapas de batalla con cuadrícula + colocación de personajes/tokens
- Ficha de personaje réplica de la hoja oficial 2024 (todos los campos, cálculo en vivo)
- Personajes, Ciudades y Compendio correlacionados (todo enlazado por BD)
- Base de datos local SQLite

> Nota legal: este proyecto NO incluye texto propietario de WotC. Incluye estructura
> compatible con D&D 2024 + contenido semilla de ejemplo / SRD 5.2 (CC-BY).
> Introduce tus datos de manuales manualmente para uso privado.

## Stack recomendado (elegido por simplicidad)

- **Python 3.11+ + PySide6 (Qt)** → desktop real (.exe), QGraphicsScene ideal para battlemaps
- **SQLite** (incluido en Python) → correlación Personaje <-> Ciudad <-> Mapa
- Sin Node, sin Rust, sin servidor. Todo local.

## Instalación (Windows)

1. Instala Python 3.12 desde Microsoft Store o https://www.python.org/downloads/
   (marca "Add python.exe to PATH")
2. En esta carpeta:
```powershell
pip install -r requirements.txt
python main.py
```

## Estructura

```
main.py                 → ventana principal con pestañas
requirements.txt
src/
  database.py           → SQLite + schema + CRUD
  models.py             → dataclasses
  widgets/
    battlemap.py        → editor de mapa con cuadrícula y tokens arrastrables
    worldmap.py         → mapa de mundo con pines de ciudades
  views/
    personajes_view.py
    ciudades_view.py
    compendio_view.py
    campañas_view.py
data/
  dnd.db                → se crea solo al arrancar
  db/schema.sql
  seed/compendio_base.json
  maps/                 → pon aquí tus imágenes .jpg/.png de mapas
Personajes/             → fichas en PDF. Formato principal: Personajes/<nombre>/ con PDF + foto
                        (botón Importar carpetas los da de alta juntos). También vale PDF suelto.
Mapas/                  → imágenes de mapas (los diálogos de fondo abren aquí)
Retratos/               → imágenes sueltas (si se llaman como el personaje, se autovinculan)
```

## Modelo de datos (correlación)

```
Campaña (1) ──< MapasMundo ──< Localizaciones/Ciudades ──< BattleMaps ──< Tokens
Personaje ──> Localización actual (FK)
Personaje ──> BattleMap + posición x,y
Entrada Compendio <──> Localizaciones / Personajes (tabla enlaces)
```

Todo clicable: desde un Personaje saltas a su Ciudad y a su Mapa, y viceversa.

## Compendio 2024
- 7.400+ entradas importadas de 5eTools (todos los libros oficiales): reglas,
  objetos, clases (+rasgos por nivel) y monstruos con statblock. En inglés,
  con su libro en cada entrada. Reimportar: `python tools/importar_5etools.py`.

## Generar .exe (opcional, más tarde)

```powershell
pip install pyinstaller
pyinstaller --windowed --name DnD2024 main.py
```

## Roadmap v1

- [x] Base + BD + navegación
- [x] Battlemap con cuadrícula, fondo, tokens arrastrables, guardar/cargar
- [x] Worldmap con pines
- [x] CRUD Personajes / Ciudades / Compendio
- [ ] Niebla de guerra, medición de distancia, iniciativa
- [ ] Importar D&D Beyond / Foundry
