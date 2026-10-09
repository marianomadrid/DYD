-- D&D 2024 App - Esquema SQLite
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campanas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT DEFAULT '',
  creada_en TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS personajes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campana_id INTEGER REFERENCES campanas(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL,
  clase TEXT DEFAULT '',
  especie TEXT DEFAULT '',
  nivel INTEGER DEFAULT 1,
  alineamiento TEXT DEFAULT '',
  px INTEGER DEFAULT 0,
  fuerza INTEGER DEFAULT 10,
  destreza INTEGER DEFAULT 10,
  constitucion INTEGER DEFAULT 10,
  inteligencia INTEGER DEFAULT 10,
  sabiduria INTEGER DEFAULT 10,
  carisma INTEGER DEFAULT 10,
  pg_actual INTEGER DEFAULT 10,
  pg_max INTEGER DEFAULT 10,
  ca INTEGER DEFAULT 10,
  notas TEXT DEFAULT '',
  localizacion_id INTEGER REFERENCES localizaciones(id) ON DELETE SET NULL,
  battlemap_id INTEGER REFERENCES battlemaps(id) ON DELETE SET NULL,
  token_x REAL DEFAULT 0,
  token_y REAL DEFAULT 0,
  color TEXT DEFAULT '#e74c3c',
  ficha_path TEXT DEFAULT '', -- PDF de ficha en carpeta Personajes/ (ruta relativa o absoluta)
  trasfondo TEXT DEFAULT '',
  subclase TEXT DEFAULT '',
  pg_temp INTEGER DEFAULT 0,
  dados_golpe TEXT DEFAULT '',
  velocidad INTEGER DEFAULT 30,
  tamano TEXT DEFAULT '',
  inspiracion INTEGER DEFAULT 0,
  inspiracion_heroica INTEGER DEFAULT 0,
  mu_exitos INTEGER DEFAULT 0, -- salvaciones contra muerte: éxitos
  mu_fracasos INTEGER DEFAULT 0, -- salvaciones contra muerte: fracasos
  iniciativa_bono INTEGER DEFAULT 0, -- bono extra sobre el mod. DES
  competencias TEXT DEFAULT '', -- entrenamiento armadura + armas
  equipo TEXT DEFAULT '',
  idiomas TEXT DEFAULT '',
  herramientas TEXT DEFAULT '',
  rasgos TEXT DEFAULT '', -- rasgos de clase (+ pericia)
  rasgos_especie TEXT DEFAULT '',
  dotes TEXT DEFAULT '',
  skills TEXT DEFAULT '{}', -- JSON {"Atletismo": 0|1|2} 0=no,1=competente,2=pericia
  saves TEXT DEFAULT '{}', -- JSON {"FUE": 0|1, ...}
  retrato_path TEXT DEFAULT '' -- imagen en carpeta Retratos/ (ruta relativa o absoluta)
);

CREATE TABLE IF NOT EXISTS armas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  personaje_id INTEGER NOT NULL REFERENCES personajes(id) ON DELETE CASCADE,
  nombre TEXT DEFAULT '',
  atk TEXT DEFAULT '',
  dano TEXT DEFAULT '',
  notas TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_armas_pers ON armas(personaje_id);

CREATE TABLE IF NOT EXISTS mapas_mundo (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campana_id INTEGER REFERENCES campanas(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL,
  imagen_path TEXT DEFAULT '',
  notas TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS localizaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mapa_mundo_id INTEGER REFERENCES mapas_mundo(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL,
  tipo TEXT DEFAULT 'ciudad', -- ciudad, pueblo, mazmorra, punto_interes...
  descripcion TEXT DEFAULT '',
  x REAL DEFAULT 0.25, -- posición relativa 0..1 sobre la imagen del mapa mundo
  y REAL DEFAULT 0.25,
  imagen_path TEXT DEFAULT '', -- mapa propio de la localización (ciudad, mazmorra...)
  FOREIGN KEY (mapa_mundo_id) REFERENCES mapas_mundo(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS puntos_interes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  localizacion_id INTEGER NOT NULL REFERENCES localizaciones(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL,
  descripcion TEXT DEFAULT '',
  x REAL DEFAULT 0.5, -- posición relativa 0..1 sobre la imagen de la localización
  y REAL DEFAULT 0.5,
  imagen_path TEXT DEFAULT '' -- mapa o foto del punto (taberna, estatua...)
);
CREATE INDEX IF NOT EXISTS idx_poi_loc ON puntos_interes(localizacion_id);

CREATE TABLE IF NOT EXISTS battlemaps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  localizacion_id INTEGER REFERENCES localizaciones(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL,
  imagen_path TEXT DEFAULT '',
  ancho_celdas INTEGER DEFAULT 20,
  alto_celdas INTEGER DEFAULT 14,
  px_celda INTEGER DEFAULT 50,
  notas TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS compendio (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  categoria TEXT NOT NULL, -- clase, especie, hechizo, objeto, monstruo, regla...
  nombre TEXT NOT NULL,
  fuente TEXT DEFAULT 'homebrew',
  contenido TEXT DEFAULT '',
  datos TEXT DEFAULT '{}', -- JSON estructurado (statblock de monstruo, etc.)
  UNIQUE(categoria, nombre)
);

-- Enlaces genéricos para correlacionar todo: ej. hechizo <-> personaje, ciudad <-> facción...
CREATE TABLE IF NOT EXISTS enlaces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  desde_tipo TEXT NOT NULL, -- personaje, localizacion, battlemap, compendio
  desde_id INTEGER NOT NULL,
  hacia_tipo TEXT NOT NULL,
  hacia_id INTEGER NOT NULL,
  etiqueta TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_enlaces_desde ON enlaces(desde_tipo, desde_id);
CREATE INDEX IF NOT EXISTS idx_enlaces_hacia ON enlaces(hacia_tipo, hacia_id);

-- Fuentes de los libros (código 5eTools -> nombre largo) para el filtro del compendio
CREATE TABLE IF NOT EXISTS fuentes (
  codigo TEXT PRIMARY KEY,
  nombre TEXT NOT NULL
);

-- Ajustes de la app (clave -> valor, ej. fuentes_off = JSON con códigos desactivados)
CREATE TABLE IF NOT EXISTS ajustes (
  clave TEXT PRIMARY KEY,
  valor TEXT DEFAULT ''
);

-- Niebla de guerra por battlemap: una fila por celda tapada
CREATE TABLE IF NOT EXISTS battlemap_fog (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  battlemap_id INTEGER NOT NULL REFERENCES battlemaps(id) ON DELETE CASCADE,
  cx INTEGER NOT NULL,
  cy INTEGER NOT NULL,
  UNIQUE(battlemap_id, cx, cy)
);
CREATE INDEX IF NOT EXISTS idx_fog_map ON battlemap_fog(battlemap_id);
