"""Motor de aventura jugable: guiones JSON con nodos, opciones, flags y finales.

Formato data/scripts/<guion>.json:
{
  "titulo": "...", "inicio": "nodo_id",
  "nodos": {"id": {"titulo": "...", "texto": "...", "retrato": "ruta/opcional",
                   "opciones": [{"texto": "...", "ir": "otro|None(fin)",
                                  "set": {"flag": 1}, "req": {"flag": 1}}]}}
}
El estado (flags) se guarda por campaña en ajustes ("partida:<id>").
"""
import json
from pathlib import Path
from .database import BASE, get_ajuste, set_ajuste

GUIONES = BASE / "data" / "scripts"


def cargar_guion(nombre):
    p = GUIONES / f"{nombre}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    if "nodos" not in d or d.get("inicio") not in d["nodos"]:
        raise ValueError(f"Guion {nombre!r} sin inicio válido")
    return d


def leer_ref(ref):
    """'guion:nodo' -> (guion, nodo). ValueError si mal formada."""
    if not ref or ":" not in ref:
        raise ValueError(f"Referencia de guion inválida: {ref!r}")
    g, n = ref.split(":", 1)
    if not g.strip() or not n.strip():
        raise ValueError(f"Referencia de guion inválida: {ref!r}")
    return g.strip(), n.strip()


def estado_partida(campana_id):
    try:
        d = json.loads(get_ajuste(f"partida:{campana_id}", "") or "{}")
        return {"flags": d.get("flags", {}) if isinstance(d, dict) else {}}
    except (ValueError, TypeError):
        return {"flags": {}}


def guardar_partida(campana_id, estado):
    set_ajuste(f"partida:{campana_id}", json.dumps({"flags": estado.get("flags", {})}))


class Aventura:
    """Partida sobre un guion. Sin diálogos: la vista va aparte."""

    def __init__(self, guion_nombre, campana_id, nodo_inicial=None):
        self.guion_nombre = guion_nombre
        self.guion = cargar_guion(guion_nombre)
        self.campana_id = campana_id
        self.estado = estado_partida(campana_id)
        self.nodo_id = nodo_inicial or self.guion["inicio"]
        if self.nodo_id not in self.guion["nodos"]:
            raise ValueError(f"Nodo inicial desconocido: {self.nodo_id!r}")

    @property
    def nodo(self):
        return self.guion["nodos"][self.nodo_id]

    def opciones(self):
        flags = self.estado.get("flags", {})
        out = []
        for op in self.nodo.get("opciones", []) or []:
            req = op.get("req") or {}
            if all(flags.get(k) == v for k, v in req.items()):
                out.append(op)
        return out

    def es_final(self):
        return not self.opciones()

    def elegir(self, indice):
        """Aplica set y avanza. Devuelve el nodo nuevo o None si terminó."""
        ops = self.opciones()
        if not 0 <= indice < len(ops):
            raise IndexError(indice)
        op = ops[indice]
        flags = self.estado.setdefault("flags", {})
        for k, v in (op.get("set") or {}).items():
            flags[k] = v
        guardar_partida(self.campana_id, self.estado)
        destino = op.get("ir")
        if not destino or destino not in self.guion["nodos"]:
            return None
        self.nodo_id = destino
        return self.nodo
