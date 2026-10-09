"""Importa reglas, objetos, clases y monstruos de 5eTools al compendio local.

Fuente: mirror público https://github.com/5etools-mirror-3/5etools-src (rama main).
Uso privado: descarga los JSON a data/5etools/ (caché) y vuelca el contenido
a la tabla `compendio` con fuente "5eTools · <LIBRO>". Solo libros oficiales
(excluye UA y contenido no oficial). No ejecuta la app: uso directo de SQLite.

Ejemplos:
  python tools/importar_5etools.py --fuentes          # lista libros detectados
  python tools/importar_5etools.py --categorias regla --limite 5
  python tools/importar_5etools.py                     # importación completa
  python tools/importar_5etools.py --recargar          # redescarga los JSON

Nota: los datos 5eTools están en INGLÉS; se importan tal cual con su fuente.
"""
import argparse
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from src.database import init_db, DB_PATH  # noqa: E402

REPO = "https://raw.githubusercontent.com/5etools-mirror-3/5etools-src/main/data"
API = "https://api.github.com/repos/5etools-mirror-3/5etools-src/contents/data"
CACHE = BASE / "data" / "5etools"
UA = "DnD2024App/1.0 (uso privado)"

# Prefijos/códigos NO oficiales (playtest y similares)
DENY = ("UA",)
DENY_EXACT = {"HB", "UAv2"}

# Libros preferidos al deduplicar por nombre (2024 antes que 2014)
RANK = {"XPHB": 0, "XDMG": 0, "XMM": 0, "PHB": 1, "DMG": 1, "MM": 1}

CLASES = ["barbarian", "bard", "cleric", "druid", "fighter", "monk", "paladin",
          "ranger", "rogue", "sorcerer", "warlock", "wizard", "artificer", "sidekick"]

ESCUELAS = {"A": "Abjuration", "C": "Conjuration", "D": "Divination",
            "E": "Enchantment", "I": "Illusion", "N": "Necromancy",
            "T": "Transmutation", "V": "Evocation"}
TIEMPO_U = {"action": "acción", "bonus": "acción adicional", "reaction": "reacción",
            "minute": "minuto", "hour": "hora", "day": "día"}
ALCANCE_U = {"self": "Personal", "touch": "Toque", "sight": "Vista",
             "unlimited": "Ilimitado", "special": "Especial",
             "sphere": "Esfera", "cube": "Cubo", "cone": "Cono", "line": "Línea",
             "hemisphere": "Hemisferio", "radius": "Radio"}
DUR_TIPO = {"instant": "Instantánea", "permanent": "Permanente", "special": "Especial"}

# Nombres largos de los libros principales (el resto sale de books/adventures.json)
LIBROS = {
    "XPHB": "Player's Handbook (2024)", "XDMG": "Dungeon Master's Guide (2024)",
    "XMM": "Monster Manual (2025)", "PHB": "Player's Handbook (2014)",
    "DMG": "Dungeon Master's Guide (2014)", "MM": "Monster Manual (2014)",
    "XGE": "Xanathar's Guide to Everything", "TCE": "Tasha's Cauldron of Everything",
    "VGM": "Volo's Guide to Monsters", "MTF": "Mordenkainen's Tome of Foes",
    "SCAG": "Sword Coast Adventurer's Guide", "ERLW": "Eberron: Rising from the Last War",
    "EGW": "Explorer's Guide to Wildemount", "MOT": "Mythic Odysseys of Theros",
    "FTD": "Fizban's Treasury of Dragons", "SCC": "Strixhaven: A Curriculum of Chaos",
    "MPP": "Mordenkainen Presents: Monsters of the Multiverse",
    "MPMM": "Mordenkainen Presents: Monsters of the Multiverse",
    "BGG": "Bigby Presents: Glory of Giants", "AAG": "Astral Adventurer's Guide",
    "AI": "Acquisitions Incorporated", "GoS": "Ghosts of Saltmarsh",
    "OotA": "Out of the Abyss", "CoS": "Curse of Strahd", "ToA": "Tomb of Annihilation",
    "SKT": "Storm King's Thunder", "WDH": "Waterdeep: Dragon Heist",
    "WDMM": "Waterdeep: Dungeon of the Mad Mage", "IDRotF": "Icewind Dale: Rime of the Frostmaiden",
    "WBtW": "The Wild Beyond the Witchlight", "CRCotN": "Critical Role: Call of the Netherdeep",
    "DSotDQ": "Dragonlance: Shadow of the Dragon Queen",
    "GGR": "Guildmasters' Guide to Ravnica",
}

ARCHIVOS_FIJOS = {
    "regla": ["variantrules.json", "conditionsdiseases.json", "actions.json",
              "objects.json", "skills.json"],
    "objeto": ["items.json", "items-base.json", "magicvariants.json"],
    "clase": [f"class/class-{c}.json" for c in CLASES],
    "especie": ["races.json"],
    "trasfondo": ["backgrounds.json"],
    "dote": ["feats.json", "optionalfeatures.json"],
}

# ---------------------------------------------------------------- descarga
def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def descargar(rel, recargar=False):
    dest = CACHE / rel
    if dest.exists() and not recargar:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_get(f"{REPO}/{rel}"))
    print(f"  ok {rel} ({dest.stat().st_size // 1024} KB)", flush=True)
    return dest


def listar_api(subdir):
    d = json.loads(_get(f"{API}/{subdir}").decode("utf-8"))
    return [x["name"] for x in d if x["type"] == "file"]


def archivos_categoria(cat):
    if cat in ARCHIVOS_FIJOS:
        return ARCHIVOS_FIJOS[cat]
    if cat == "monstruo":  # todo bestiary-* salvo fluff/índices/plantillas
        malos = ("fluff-", "index.json", "foundry.json", "legendarygroups.json",
                 "template.json")
        return [f"bestiary/{n}" for n in listar_api("bestiary")
                if n.startswith("bestiary-") and not n.startswith(malos)]
    if cat == "hechizo":
        return [f"spells/{n}" for n in listar_api("spells")
                if n.startswith("spells-") and not n.startswith(("fluff-", "index",
                                                                 "foundry", "sources"))]
    raise ValueError(cat)


def nombre_libro(codigo, libros_json):
    if codigo in LIBROS:
        return LIBROS[codigo]
    return libros_json.get(codigo, codigo)


def cargar_nombres_libros():
    """books.json + adventures.json: id -> nombre largo."""
    nombres = {}
    for rel, clave in (("books.json", "book"), ("adventures.json", "adventure")):
        try:
            d = json.loads(descargar(rel).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  (sin {rel}: {e})")
            continue
        for b in d.get(clave, []):
            if b.get("id") and b.get("name"):
                nombres[b["id"]] = b["name"]
    return nombres


def oficial(source):
    s = (source or "").strip()
    return bool(s) and not s.startswith(DENY) and s not in DENY_EXACT


# ------------------------------------------------------- render de entradas
TAG = re.compile(r"\{@([^}]*)\}")


def _tag(m):
    body = m.group(1).strip()
    if " " in body:
        tag, rest = body.split(" ", 1)
    else:
        tag, rest = body, ""
    nom = rest.split("|")[0].strip()
    if tag in ("damage", "dice", "scaledamage", "scaledice", "d20", "chance",
               "coin", "actSave", "actAttack", "skillCheck", "savingThrow"):
        return nom
    if tag == "dc":
        return f"DC {nom}"
    if tag == "hit":
        return "+{0}".format(nom) if nom and not nom.startswith(("+", "-")) else nom
    if tag == "atkr":
        return {"m": "Melee Attack Roll:", "r": "Ranged Attack Roll:",
                "m,r": "Melee or Ranged Attack Roll:",
                "mw": "Melee Weapon Attack:", "rw": "Ranged Weapon Attack:"}.get(nom, nom)
    if tag == "h":
        return "Hit:"
    if tag == "i":
        return nom
    if tag == "recharge":
        return f"(Recharge {nom})" if nom else "(Recharge)"
    if tag in ("b", "s", "u", "code", "kbd"):
        return ""
    if tag == "footnote":
        return ""
    return nom


def _tags(txt):
    return TAG.sub(_tag, txt)


def plano(e):
    """Cualquier nodo de entries 5eTools -> texto legible."""
    if e is None:
        return ""
    if isinstance(e, str):
        return _tags(e).strip()
    if isinstance(e, (int, float)):
        return str(e)
    if isinstance(e, list):
        return "\n".join(t for t in (plano(x) for x in e) if t)
    if isinstance(e, dict):
        t = e.get("type")
        if t in ("entries", "inset", "insetReadaloud", "quote", "variant",
                 "variantSub", "optionalfeature", "patron", "deity"):
            head = f"### {e['name']}\n" if e.get("name") else ""
            return head + plano(e.get("entries", []))
        if t == "list":
            return "\n".join("• " + plano(i) for i in e.get("items", []))
        if t == "table":
            out = []
            if e.get("caption"):
                out.append(f"[{plano(e['caption'])}]")
            if e.get("colLabels"):
                out.append(" | ".join(plano(c) for c in e["colLabels"]))
            for row in e.get("rows", []):
                cells = row.get("row") if isinstance(row, dict) else row
                out.append(" | ".join(plano(c) for c in (cells or [])))
            return "\n".join(out)
        if t == "tableGroup":
            return plano(e.get("tables", []))
        if t in ("statblock", "statblockInline"):
            return plano(e.get("entries", []))
        if t in ("image", "gallery", "link", "flowchart", "abilityGeneric"):
            return ""
        if t in ("abilityDc", "abilityAttackMod", "abilityGeneric"):
            return plano(e.get("entries", e.get("name", "")))
        if t == "actions":
            return plano(e.get("entries", []))
        if "toRoll" in e:
            dados = e["toRoll"] if isinstance(e["toRoll"], list) else [e["toRoll"]]
            partes = []
            for dd in dados:
                if isinstance(dd, dict) and dd.get("faces"):
                    partes.append(f"{dd.get('number', 1)}d{dd['faces']}")
            if e.get("mod"):
                partes.append(str(e["mod"]))
            if partes:
                return "+".join(partes).replace("+-", "-")
            return ""
        if "value" in e:
            return plano(e["value"])
        if "entries" in e:
            head = f"### {e['name']}\n" if e.get("name") else ""
            return head + plano(e["entries"])
        if "items" in e:
            return plano(e["items"])
        if "text" in e:
            return plano(e["text"])
        return ""
    return ""


def txt(v):
    if isinstance(v, list):
        return ", ".join(plano(x) for x in v)
    if isinstance(v, dict):
        return plano(v)
    return "" if v is None else str(v)


# ---------------------------------------------------------------- registros
def _f(fuente, nombre, texto):
    nombre, texto = (nombre or "").strip(), (texto or "").strip()
    if not nombre or not texto:
        return None
    return (nombre, f"5eTools · {fuente}", texto)


def reglas_de(d):
    out = []
    for v in d.get("variantrule", []):
        out.append((v.get("source"), v.get("name"), plano(v.get("entries"))))
    for v in d.get("condition", []) + d.get("disease", []):
        out.append((v.get("source"), v.get("name"), plano(v.get("entries"))))
    for v in d.get("action", []):
        out.append((v.get("source"), v.get("name"), plano(v.get("entries"))))
    for v in d.get("object", []):
        extra = []
        for k in ("ac", "hp", "speed", "resist", "immune", "vuln"):
            if v.get(k) is not None:
                extra.append(f"{k}: {txt(v[k])}")
        out.append((v.get("source"), v.get("name"),
                    ("\n".join(extra) + "\n" if extra else "") + plano(v.get("entries"))))
    for v in d.get("skill", []):
        out.append((v.get("source"), v.get("name"), plano(v.get("entries"))))
    return [r for r in (_f(*x) for x in out) if r]


ITEM_TIPO = {"M": "Melee Weapon", "R": "Ranged Weapon", "A": "Ammunition",
             "AF": "Firearm Ammunition", "AT": "Artisan's Tools", "INS": "Instrument",
             "SCF": "Spellcasting Focus", "LA": "Light Armor", "MA": "Medium Armor",
             "HA": "Heavy Armor", "S": "Shield", "P": "Potion", "RD": "Rod",
             "RG": "Ring", "SC": "Scroll", "WD": "Wand", "G": "Adventuring Gear",
             "T": "Tools", "GS": "Gaming Set", "VEH": "Vehicle", "SHP": "Ship",
             "MNT": "Mount", "OTH": "Other", "TAH": "Tack and Harness",
             "TB": "Trade Bar", "TG": "Trade Good", "EXP": "Explosive",
             "FD": "Food and Drink", "AIR": "Airship", "$A": "Art Object",
             "$G": "Gemstone", "$C": "Currency", "SPC": "Other"}
ITEM_PROP = {"2H": "Two-Handed", "A": "Ammunition", "F": "Finesse", "H": "Heavy",
             "L": "Light", "LD": "Loading", "R": "Range", "RLD": "Reload",
             "S": "Special", "T": "Thrown", "V": "Versatile", "BF": "Burst Fire",
             "Vst": "Vestige"}
DMG_TIPO = {"B": "Bludgeoning", "P": "Piercing", "S": "Slashing", "A": "Acid",
            "C": "Cold", "F": "Fire", "O": "Force", "L": "Lightning",
            "N": "Necrotic", "I": "Poison", "Y": "Psychic", "R": "Radiant",
            "T": "Thunder"}


def _uid(x):
    """'V|XPHB' o {'uid': 'V|XPHB', 'note': ...} -> (código, nota)."""
    if isinstance(x, dict):
        u = str(x.get("uid", ""))
        return u.split("|")[0], str(x.get("note", ""))
    return str(x).split("|")[0], ""


def _monedas(cp):
    try:
        cp = int(cp)
    except (ValueError, TypeError):
        return str(cp)
    if cp % 100 == 0:
        return f"{cp // 100} gp"
    if cp % 10 == 0:
        return f"{cp // 10} sp"
    return f"{cp} cp"


def _rango(r):
    s = str(r).strip()
    if re.fullmatch(r"[\d\s/]+", s):
        return f"{s} pies"
    return s


def _plantilla(nodo, inh):
    """Sustituye {=clave} con los valores de `inherits` (magicvariant)."""
    if isinstance(nodo, str):
        return re.sub(r"\{=([^}]*)\}", lambda m: str((inh or {}).get(m.group(1), "")), nodo)
    if isinstance(nodo, list):
        return [_plantilla(x, inh) for x in nodo]
    if isinstance(nodo, dict):
        return {k: _plantilla(val, inh) for k, val in nodo.items()}
    return nodo


def itemblock_de(v):
    """Objeto 5eTools -> dict display-ready (clasificación como la página)."""
    cod, _ = _uid(v.get("type", ""))
    if cod == "GV":
        reqs = []
        for r in v.get("requires") or []:
            if isinstance(r, dict) and r.get("type"):
                c, _ = _uid(r["type"])
                reqs.append(ITEM_TIPO.get(c) or ("Wondrous Item" if not c else c))
        tipo = "Generic Variant" + (f" ({', '.join(reqs)})" if reqs else "")
    else:
        tipo = ITEM_TIPO.get(cod) or ("Wondrous Item" if not cod else cod)
    props = []
    for p in v.get("property") or []:
        cod, nota = _uid(p)
        nom = ITEM_PROP.get(cod, cod)
        props.append(f"{nom} ({nota})" if nota else nom)
    maest = []
    for m in v.get("mastery") or []:
        cod, nota = _uid(m)
        maest.append(f"{cod} ({nota})" if nota else cod)
    rar = v.get("rarity")
    rar = "" if rar in (None, "none") else str(rar).title()
    att = v.get("reqAttune")
    sint = "" if not att else ("Requires Attunement" if att is True else f"Requires Attunement ({att})")
    arm = {}
    if isinstance(v.get("armor"), dict):
        for k, et in (("ac", "CA"), ("strength", "Fuerza"), ("stealth", "Sigilo")):
            if v["armor"].get(k) is not None:
                v_ = v["armor"][k]
                arm[et] = "desventaja" if v_ is True and k == "stealth" else txt(v_)
    elif v.get("armor") is True:
        arm = {}
    src = v.get("source", "?")
    inh = v.get("inherits") or {}
    try:
        vcp = int(v.get("value"))
    except (ValueError, TypeError):
        vcp = -1
    try:
        plb = float(v.get("weight"))
    except (ValueError, TypeError):
        plb = -1.0
    return {
        "v": 1, "nombre": v.get("name", "?"), "fuente": src,
        "corta": FUENTE_CORTA.get(src, src), "pagina": v.get("page"),
        "ref": v.get("referenceSources") or [],
        "tipo": tipo,
        "cat_arma": str(v.get("weaponCategory") or "").capitalize(),
        "rareza": rar, "sintonia": sint,
        "valor": _monedas(v["value"]) if v.get("value") is not None else "",
        "peso": f"{v['weight']} lb." if v.get("weight") is not None else "",
        "props": props, "maestrias": maest,
        "dano": str(v.get("dmg1") or ""), "dano_tipo": DMG_TIPO.get(v.get("dmgType"), v.get("dmgType") or ""),
        "dano2": str(v.get("dmg2") or ""),
        "alcance": _rango(v["range"]) if v.get("range") is not None else "",
        "armadura": arm, "base": inh.get("name", ""),
        "valor_cp": vcp, "peso_lb": plb,
        "texto": plano(v.get("entries")),
    }


def objetos_de(d):
    out = []
    for v in d.get("item", []) + d.get("baseitem", []) + d.get("magicvariant", []):
        inh = v.get("inherits") or {}
        if inh:  # variantes genéricas: heredan libro/rareza/entradas (+ plantillas {=x})
            v = {**v, **{k: inh[k] for k in
                         ("source", "rarity", "value", "weight", "entries", "page")
                         if v.get(k) is None and k in inh}}
            if v.get("entries"):
                v["entries"] = _plantilla(v["entries"], inh)
        b = itemblock_de(v)
        det = [t for t in [b["tipo"], b["cat_arma"]] if t]
        if b["rareza"]:
            det.append(b["rareza"] + (f" ({b['sintonia']})" if b["sintonia"] else ""))
        elif b["sintonia"]:
            det.append(b["sintonia"])
        for et, k in (("Valor", "valor"), ("Peso", "peso"), ("Daño", "dano"),
                       ("Daño 2M", "dano2"), ("Alcance", "alcance")):
            if b[k]:
                det.append(f"{et}: {b[k]}")
        if b["dano_tipo"]:
            det.append(f"Tipo: {b['dano_tipo']}")
        if b["props"]:
            det.append("Prop.: " + ", ".join(b["props"]))
        if b["maestrias"]:
            det.append("Maestría: " + ", ".join(b["maestrias"]))
        for et, v_ in b["armadura"].items():
            det.append(f"{et}: {v_}")
        cabe = ("[" + " · ".join(det) + "]\n") if det else ""
        base = f"Basado en: {b['base']}\n" if b["base"] else ""
        r = _f(v.get("source"), v.get("name"), cabe + base + b["texto"])
        if r:
            out.append((*r, b))
    return out


def ordinal_nivel(n):
    if n == 0:
        return "Truco"
    if n == 1:
        return "1st-level"
    if n == 2:
        return "2nd-level"
    if n == 3:
        return "3rd-level"
    return f"{n}th-level"


def _tiempo(ts):
    out = []
    for t in ts or []:
        if not isinstance(t, dict):
            continue
        n, u = t.get("number", 1), TIEMPO_U.get(t.get("unit"), t.get("unit", ""))
        s = f"{n} {u}"
        if n != 1 and u in ("minuto", "hora", "día", "acción", "reacción"):
            s += "s" if not u.endswith("s") else ""
            s = s.replace("accións", "acciones").replace("reaccións", "reacciones")
        if t.get("condition"):
            s += f" ({plano(t['condition'])})"
        out.append(s)
    return ", ".join(out)


def _alcance(r):
    if not isinstance(r, dict):
        return txt(r)
    if r.get("type") == "point":
        d = r.get("distance") or {}
        if d.get("type") == "feet":
            return f"{d.get('amount', '?')} pies"
        return txt(d)
    t = r.get("type")
    if t in ALCANCE_U:
        s = ALCANCE_U[t]
        d = r.get("distance") or {}
        if isinstance(d, dict) and d.get("amount"):
            s += f" ({d['amount']} pies)"
        return s
    return txt(r)


def _duracion(ds):
    out = []
    for x in ds or []:
        if not isinstance(x, dict):
            out.append(txt(x))
            continue
        if x.get("type") == "timed":
            dd = x.get("duration") or {}
            u = {"minute": "minuto", "hour": "hora", "day": "día",
                 "round": "asalto", "week": "semana"}.get(dd.get("type"), dd.get("type", ""))
            n = dd.get("amount", "?")
            s = f"hasta {n} {u}{'s' if isinstance(n, int) and n != 1 else ''}"
            if x.get("concentration"):
                s = "Concentración, " + s.lower()
            out.append(s)
        elif x.get("type") in DUR_TIPO:
            out.append(DUR_TIPO[x["type"]])
        else:
            out.append(txt(x))
    return ", ".join(out)


def _componentes(c):
    if not isinstance(c, dict):
        return ""
    partes = []
    if c.get("v"):
        partes.append("V")
    if c.get("s"):
        partes.append("S")
    if c.get("m"):
        m = c["m"]
        partes.append(f"M ({txt(m) if not isinstance(m, bool) else 'componente material'})")
    return ", ".join(partes)


def hechizos_de(d, clases_por_hechizo):
    out = []
    for v in d.get("spell", []):
        niv, esc = v.get("level", 0), ESCUELAS.get(v.get("school"), v.get("school", ""))
        cabe = [ordinal_nivel(niv) + (f" {esc}" if niv else f" de {esc}" if esc else "")]
        for et, val in (("Tiempo", _tiempo(v.get("time"))), ("Alcance", _alcance(v.get("range"))),
                        ("Componentes", _componentes(v.get("components"))),
                        ("Duración", _duracion(v.get("duration")))):
            if val:
                cabe.append(f"{et}: {val}")
        cls = clases_por_hechizo.get((v.get("name"), v.get("source")), [])
        if cls:
            cabe.append("Clases: " + ", ".join(cls))
        ritual = bool((v.get("meta") or {}).get("ritual"))
        texto = "\n".join(cabe)
        if v.get("entriesHigherLevel"):
            texto += "\n\n### En niveles superiores\n" + plano(v["entriesHigherLevel"])
        texto += ("\n\n" if texto else "") + plano(v.get("entries"))
        b = {"v": "hechizo", "nombre": v.get("name", "?"), "fuente": v.get("source", "?"),
             "corta": FUENTE_CORTA.get(v.get("source"), v.get("source", "?")),
             "pagina": v.get("page"), "ref": v.get("referenceSources") or [],
             "nivel": niv, "escuela": esc, "tiempo": _tiempo(v.get("time")),
             "alcance": _alcance(v.get("range")), "comp": _componentes(v.get("components")),
             "duracion": _duracion(v.get("duration")), "clases": cls,
             "ritual": ritual,
             "conc": _duracion(v.get("duration")).startswith("Concentración"),
             "texto": plano(v.get("entries")) + (
                 "\n\n### En niveles superiores\n" + plano(v["entriesHigherLevel"])
                 if v.get("entriesHigherLevel") else "")}
        r = _f(v.get("source"), v.get("name"), texto)
        if r:
            out.append((*r, b))
    return out


def especies_de(d):
    out = []
    for v in d.get("race", []):
        det = []
        if v.get("size"):
            sz = v["size"] if isinstance(v["size"], list) else [v["size"]]
            det.append("Tamaño: " + ", ".join(TAMANO.get(x, x) for x in sz))
        if v.get("speed"):
            det.append("Velocidad: " + _vel(v["speed"]))
        ab = v.get("ability")
        if isinstance(ab, dict):
            det.append("Mejoras: " + ", ".join(
                f"{str(k).upper()} +{val}" for k, val in ab.items()))
        elif isinstance(ab, list):
            det.append("Mejoras: " + "; ".join(txt(x) for x in ab))
        cabe = ("[" + " · ".join(det) + "]\n") if det else ""
        r = _f(v.get("source"), v.get("name"), cabe + plano(v.get("entries")))
        if r:
            out.append(r)
    for v in d.get("subrace", []):
        base = ""
        cp = v.get("_copy") or {}
        if cp.get("name"):
            base = f"Subespecie de: {cp['name']}\n"
        r = _f(v.get("source"), f"{v.get('name')} ({cp.get('name', '')})",
               base + plano(v.get("entries")))
        if r:
            out.append(r)
    return out


SKILL_EN = {"acrobatics": "Acrobatics", "animal handling": "Animal Handling",
             "arcana": "Arcana", "athletics": "Athletics", "deception": "Deception",
             "history": "History", "insight": "Insight", "intimidation": "Intimidation",
             "investigation": "Investigation", "medicine": "Medicine",
             "nature": "Nature", "perception": "Perception",
             "performance": "Performance", "persuasion": "Persuasion",
             "religion": "Religion", "sleight of hand": "Sleight of Hand",
             "stealth": "Stealth", "survival": "Survival"}
ANY_ES = {"anystandard": "estándar", "anyartisanstool": "de artesano",
          "anymusicalinstrument": "musicales", "anygamingset": "de juego",
          "anytool": "herramientas", "anylanguage": "idiomas",
          "anyskill": "habilidades"}


def _origen(ab):
    if not ab:
        return "None"
    items = ab if isinstance(ab, list) else [ab]
    for x in items:
        if isinstance(x, dict) and isinstance(x.get("choose"), dict):
            ch = x["choose"]
            w = ch.get("weighted") or {}
            fr = w.get("from") or ch.get("from") or []
            if fr:
                return "Origin (" + "/".join(str(t)[:3].capitalize() for t in fr) + ")"
    det = []
    for x in items:
        if isinstance(x, dict):
            det += [f"{str(k).upper()} +{v}" for k, v in x.items()
                    if k != "choose" and isinstance(v, int)]
    return "; ".join(det) if det else "None"


def _hab_list(v):
    habs = []
    for x in (v if isinstance(v, list) else [v] if v else []):
        if isinstance(x, dict):
            habs += [SKILL_EN.get(str(k).lower(), str(k).title()) for k in x]
        elif x:
            habs.append(str(x))
    return ", ".join(habs)


def _prof_cualquiera(v):
    if isinstance(v, dict):
        partes = []
        for k, val in v.items():
            low = str(k).lower()
            if low.startswith("any"):
                partes.append(f"{val} {ANY_ES.get(low, low[3:])}")
            elif val is True:
                partes.append(str(k).title())
            else:
                partes.append(f"{k}: {txt(val)}")
        return "; ".join(partes)
    if isinstance(v, list):
        return "; ".join(_prof_cualquiera(x) for x in v)
    return txt(v)


def _equipo_txt(v):
    if isinstance(v, str):
        return v.split("|")[0]
    if isinstance(v, list):
        return ", ".join(_equipo_txt(x) for x in v)
    if isinstance(v, dict):
        if "item" in v and isinstance(v["item"], str):
            base = v.get("displayName", v["item"].split("|")[0])
            if v.get("quantity"):
                base += f" ({v['quantity']})"
            return base
        if "special" in v and len(v) == 1 or (set(v) == {"special", "quantity"}):
            base = str(v.get("special", ""))
            if v.get("quantity"):
                base += f" ({v['quantity']})"
            return base
        if "value" in v and len(v) == 1:
            return _monedas(v["value"])
        return "; ".join(f"{k}: {_equipo_txt(x)}" for k, x in v.items())
    return txt(v)


def trasfondos_de(d):
    out = []
    for v in d.get("background", []):
        hab = _hab_list(v.get("skillProficiencies"))
        ori = _origen(v.get("ability"))
        det = []
        if hab:
            det.append(f"Habilidades: {hab}")
        herr = _prof_cualquiera(v.get("toolProficiencies"))
        if herr:
            det.append(f"Herramientas: {herr}")
        idi = _prof_cualquiera(v.get("languageProficiencies"))
        if idi:
            det.append(f"Idiomas: {idi}")
        eq = _equipo_txt(v.get("startingEquipment"))
        if eq:
            det.append(f"Equipo: {eq}")
        dotes = []
        for f_ in v.get("feats") or []:
            if isinstance(f_, dict):
                dotes += [k.split("|")[0] for k in f_]
            elif f_:
                dotes.append(str(f_).split("|")[0])
        if dotes:
            det.append("Dote: " + ", ".join(dotes))
        cabe = ("[" + " · ".join(det) + "]\n") if det else ""
        b = {"v": "trasfondo", "nombre": v.get("name", "?"),
             "fuente": v.get("source", "?"),
             "corta": FUENTE_CORTA.get(v.get("source"), v.get("source", "?")),
             "pagina": v.get("page"), "ref": v.get("referenceSources") or [],
             "origen": ori, "habilidades": hab}
        r = _f(v.get("source"), v.get("name"), cabe + plano(v.get("entries")))
        if r:
            out.append((*r, b))
    return out


TIPOS_DOTE = {"EI": "Invocación", "MM": "Metamagia", "MV": "Maniobra",
              "FS": "Estilo de combate", "AS": "Disparo arcano", "AI": "Infusión",
              "ED": "Decreto", "OR": "Origen", "PB": "Pacto", "OG": "Don",
              "FS:F": "Estilo de combate", "MV:B": "Maniobra"}


def _req_txt(pre):
    if not pre:
        return ""
    if isinstance(pre, str):
        return pre.strip()
    items = pre if isinstance(pre, list) else [pre]
    partes = []
    for x in items:
        if isinstance(x, str):
            partes.append(x)
            continue
        if not isinstance(x, dict):
            continue
        for k, v in x.items():
            if k == "level":
                if isinstance(v, int):
                    partes.append(f"Nivel {v}")
                elif isinstance(v, dict):
                    lv = v.get("level", "?")
                    cn = v.get("class")
                    cn = cn.get("name") if isinstance(cn, dict) else cn
                    partes.append(f"Nivel {lv}" + (f" ({cn})" if cn else ""))
                elif v:
                    partes.append(f"Nivel {txt(v)}")
            elif k == "ability":
                habs = v if isinstance(v, list) else [v]
                bits = []
                for h in habs:
                    if isinstance(h, dict):
                        bits += [f"{str(a).upper()} {b}" for a, b in h.items()]
                    elif h:
                        bits.append(txt(h))
                if bits:
                    partes.append(" + ".join(bits))
            elif k == "spell":
                sp = v if isinstance(v, list) else [v]
                bits = []
                for s in sp:
                    if isinstance(s, str):
                        bits.append(s.split("#")[0])
                    elif isinstance(s, dict):
                        bits.append(s.get("entry") or s.get("choose") or txt(s))
                bits = [str(b) for b in bits if b]
                if bits:
                    partes.append("Conjuro: " + ", ".join(bits))
            elif k == "item":
                it = v if isinstance(v, list) else [v]
                bits = [txt(i) for i in it]
                bits = [b for b in bits if b]
                if bits:
                    partes.append("Objeto: " + ", ".join(bits))
            elif k == "campaign":
                vv = v if isinstance(v, list) else [v]
                partes.append("Campaña: " + ", ".join(str(t) for t in vv))
            elif k in ("race", "background", "feat", "other", "patron", "deity",
                       "proficiency", "skill", "senses", "language"):
                vv = v if isinstance(v, list) else [v]
                bits = []
                for e in vv:
                    if isinstance(e, dict):
                        bits.append(", ".join(f"{kk}: {txt(x) or x}" for kk, x in e.items()))
                    elif e:
                        bits.append(txt(e) or str(e))
                if bits:
                    pref = "Competencia: " if k in ("proficiency", "skill") else ""
                    partes.append(pref + "; ".join(bits))
            elif k == "exclusiveFeatCategory":
                continue
            else:
                t = txt(v)
                partes.append(f"{k}: {t}" if t else f"{k}: {str(v)[:60]}")
    return "; ".join(p for p in partes if p)


def dotes_de(d):
    out = []
    for v in d.get("feat", []):
        req = _req_txt(v.get("prerequisite"))
        cabe = f"Requisito: {req}\n" if req else ""
        r = _f(v.get("source"), v.get("name"), cabe + plano(v.get("entries")))
        if r:
            out.append((*r, {"v": "dote", "nombre": v.get("name", "?"),
                             "fuente": v.get("source", "?"),
                             "corta": FUENTE_CORTA.get(v.get("source"), v.get("source", "?")),
                             "pagina": v.get("page"), "ref": v.get("referenceSources") or [],
                             "tipo": "Dote", "requisito": req}))
    for v in d.get("optionalfeature", []):
        tipos = v.get("featureType") or []
        tipos = [tipos] if isinstance(tipos, str) else tipos
        tipo = ", ".join(TIPOS_DOTE.get(str(t).split(":")[0], str(t)) for t in tipos)
        req = _req_txt(v.get("prerequisite"))
        cabe = f"Requisito: {req}\n" if req else ""
        r = _f(v.get("source"), f"{v.get('name')} [{', '.join(str(t) for t in tipos)}]",
               cabe + plano(v.get("entries")))
        if r:
            out.append((*r, {"v": "dote", "nombre": v.get("name", "?"),
                             "fuente": v.get("source", "?"),
                             "corta": FUENTE_CORTA.get(v.get("source"), v.get("source", "?")),
                             "pagina": v.get("page"), "ref": v.get("referenceSources") or [],
                             "tipo": tipo or "Opción", "requisito": req}))
    return out


SAVE_NOMBRE = {"str": "Strength", "dex": "Dexterity", "con": "Constitution",
               "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma"}
ORDINAL = ["1st", "2nd", "3rd"] + [f"{i}th" for i in range(4, 21)]

SLOTS_FULL = [
    [2, 0, 0, 0, 0, 0, 0, 0, 0], [3, 0, 0, 0, 0, 0, 0, 0, 0],
    [4, 2, 0, 0, 0, 0, 0, 0, 0], [4, 3, 0, 0, 0, 0, 0, 0, 0],
    [4, 3, 2, 0, 0, 0, 0, 0, 0], [4, 3, 3, 0, 0, 0, 0, 0, 0],
    [4, 3, 3, 1, 0, 0, 0, 0, 0], [4, 3, 3, 2, 0, 0, 0, 0, 0],
    [4, 3, 3, 3, 1, 0, 0, 0, 0], [4, 3, 3, 3, 2, 0, 0, 0, 0],
    [4, 3, 3, 3, 2, 1, 0, 0, 0], [4, 3, 3, 3, 2, 1, 0, 0, 0],
    [4, 3, 3, 3, 2, 1, 1, 0, 0], [4, 3, 3, 3, 2, 1, 1, 0, 0],
    [4, 3, 3, 3, 2, 1, 1, 1, 0], [4, 3, 3, 3, 2, 1, 1, 1, 0],
    [4, 3, 3, 3, 2, 1, 1, 1, 1], [4, 3, 3, 3, 3, 1, 1, 1, 1],
    [4, 3, 3, 3, 3, 2, 1, 1, 1], [4, 3, 3, 3, 3, 2, 2, 1, 1]]
SLOTS_HALF = [
    [0, 0, 0, 0, 0], [2, 0, 0, 0, 0], [3, 0, 0, 0, 0], [3, 0, 0, 0, 0],
    [4, 2, 0, 0, 0], [4, 2, 0, 0, 0], [4, 3, 0, 0, 0], [4, 3, 0, 0, 0],
    [4, 3, 2, 0, 0], [4, 3, 2, 0, 0], [4, 3, 3, 0, 0], [4, 3, 3, 0, 0],
    [4, 3, 3, 1, 0], [4, 3, 3, 1, 0], [4, 3, 3, 2, 0], [4, 3, 3, 2, 0],
    [4, 3, 3, 3, 1], [4, 3, 3, 3, 1], [4, 3, 3, 3, 2], [4, 3, 3, 3, 2]]
SLOTS_THIRD = [
    [0, 0, 0, 0], [0, 0, 0, 0], [2, 0, 0, 0], [3, 0, 0, 0], [3, 0, 0, 0],
    [3, 0, 0, 0], [4, 2, 0, 0], [4, 2, 0, 0], [4, 2, 0, 0], [4, 3, 2, 0],
    [4, 3, 2, 0], [4, 3, 2, 0], [4, 3, 2, 1], [4, 3, 2, 1], [4, 3, 2, 1],
    [4, 3, 2, 1], [4, 3, 3, 1, 0], [4, 3, 3, 1, 0], [4, 3, 3, 2, 0],
    [4, 3, 3, 2, 0]]
SLOTS_PACT = [(1, 1), (2, 1), (2, 2), (2, 2), (2, 3), (2, 3), (2, 4), (2, 4),
              (2, 5), (2, 5), (3, 5), (3, 5), (3, 5), (3, 5), (3, 5), (3, 5),
              (4, 5), (4, 5), (4, 5), (4, 5)]


def _prof_item(x):
    if isinstance(x, str):
        return _tags(x)
    if isinstance(x, dict):
        if "any" in x:
            return f"cualquiera ({x['any']})"
        if isinstance(x.get("choose"), dict) and isinstance(x["choose"].get("from"), list):
            return "elegir: " + ", ".join(str(t) for t in x["choose"]["from"])
        return txt(x)
    return txt(x)


def _celda_tabla(c):
    if isinstance(c, (int, float)):
        return "—" if c == 0 else str(c)
    if isinstance(c, str):
        return c if c not in ("", "—") else "—"
    t = plano(c)
    return t if t else "—"


def _tabla_clase(c, rasgos_nivel):
    """Compone la tabla de clase estilo la página: Level/PB/Features +
    progresiones + conjuros (full/half/third/pact). Devuelve (cols, filas)."""
    cols = ["Level", "PB", "Features"]
    prog = []  # [(labels, rows20)]
    for t in c.get("classTableGroups") or []:
        filas = t.get("rows") or []
        if not filas:
            continue
        etiq = [plano(x) for x in t.get("colLabels", [])]
        celdas = []
        for r in filas:
            celdas.append([_celda_tabla(x) for x in (r if isinstance(r, list) else [r])])
        while len(celdas) < 20:
            celdas.append(["—"] * max(1, len(etiq)))
        prog.append((etiq, celdas[:20]))
        cols += etiq
    prog_caster = c.get("casterProgression")
    slots, slot_cols = None, []
    if prog_caster == "full":
        slots, slot_cols = SLOTS_FULL, ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"]
    elif prog_caster == "half":
        slots, slot_cols = [r + [0] * 4 for r in SLOTS_HALF], ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"]
    elif prog_caster == "third":
        slots, slot_cols = [r + [0] * 5 for r in SLOTS_THIRD], ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"]
    elif prog_caster == "artificer":
        base = [[2, 0, 0, 0, 0]] + [r[:] for r in SLOTS_HALF[1:]]
        slots, slot_cols = [r + [0] * 4 for r in base], ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"]
    if slots:
        cols += slot_cols
    pact = prog_caster == "pact"
    if pact:
        cols += ["Slots", "Slot Level"]
    filas = []
    for i in range(20):
        feats = ", ".join(rasgos_nivel.get(i + 1, [])) or "—"
        fila = [ORDINAL[i], f"+{2 + i // 4}", feats]
        for _, celdas in prog:
            fila += celdas[i] if i < len(celdas) else ["—"] * 99
        if slots:
            fila += ["—" if x == 0 else str(x) for x in slots[i]]
        if pact:
            s, sl = SLOTS_PACT[i]
            fila += [str(s), f"{sl}th" if sl > 3 else (["1st", "2nd", "3rd"])[sl - 1]]
        filas.append(fila)
    # normaliza anchos
    ancho = max(len(f) for f in filas) if filas else len(cols)
    cols = (cols + [""] * ancho)[:ancho]
    filas = [(f + ["—"] * ancho)[:ancho] for f in filas]
    return cols, filas, bool(slots or pact)


def _multiclase(mc):
    if not isinstance(mc, dict):
        return ""
    partes = []
    req = mc.get("requirements")
    if isinstance(req, dict):
        partes.append("Requisitos: " + ", ".join(
            f"{SAVE_NOMBRE.get(k, k)} {v}" for k, v in req.items()))
    elif req:
        partes.append("Requisitos: " + txt(req))
    gana = mc.get("proficienciesGained") or {}
    if isinstance(gana, dict) and gana:
        partes.append("Ganas: " + "; ".join(
            f"{k}: {txt(v)}" for k, v in gana.items() if txt(v)))
    return "Multiclase: " + " · ".join(partes) if partes else ""


def clases_de(d):
    """Solo filas de CLASE (una por clase). Todo lo demás vive en `datos`."""
    out = []
    for c in d.get("class", []):
        nom, src = c.get("name", "?"), c.get("source", "?")
        hd = c.get("hd") or {}
        faces = hd.get("faces", "?")
        try:
            media = int(faces) // 2 + 1
        except (ValueError, TypeError):
            media = "?"
        cab = [f"Dados de golpe: d{faces} (PG nivel 1: {faces} + CON; "
               f"superiores: 1d{faces}+CON, media {media})"]
        salv = [SAVE_NOMBRE.get(x, x) for x in c.get("proficiency", []) or []]
        if salv:
            cab.append("Salvaciones: " + ", ".join(salv))
        sp = c.get("startingProficiencies") or {}
        ARM = {"light": "Light armor", "medium": "Medium armor",
               "heavy": "Heavy armor", "shields": "Shields"}
        WPN = {"simple": "Simple weapons", "martial": "Martial weapons"}
        for k, et in (("armor", "Armadura"), ("weapons", "Armas"),
                      ("tools", "Herramientas"), ("skills", "Habilidades")):
            vv = sp.get(k)
            if vv:
                vals = vv if isinstance(vv, list) else [vv]
                norm = []
                for x in vals:
                    if isinstance(x, str) and k == "armor" and x.lower() in ARM:
                        norm.append(ARM[x.lower()])
                    elif isinstance(x, str) and k == "weapons" and x.lower() in WPN:
                        norm.append(WPN[x.lower()])
                    else:
                        norm.append(_prof_item(x))
                cab.append(f"{et}: " + "; ".join(norm))
        se = c.get("startingEquipment") or {}
        eq = se.get("default") or []
        if eq:
            cab.append("Equipo:\n" + "\n".join("• " + _tags(x) if isinstance(x, str) else "• " + plano(x) for x in eq))
        if c.get("spellcastingAbility"):
            hab = {"int": "Inteligencia", "wis": "Sabiduría", "cha": "Carisma"}.get(
                c["spellcastingAbility"], c["spellcastingAbility"])
            prog = {"full": "completa", "half": "media", "third": "terciada",
                    "pact": "de pacto", "artificer": "de artífice"}.get(c.get("casterProgression"), "")
            cab.append(f"Conjuros: {hab}" + (f" (progresión {prog})" if prog else ""))
        mc = _multiclase(c.get("multiclassing"))
        if mc:
            cab.append(mc)
        feats = [v for v in d.get("classFeature", [])
                 if v.get("className") == nom and v.get("source") == src]
        rasgos_nivel = {}
        rasgos = []
        for v in sorted(feats, key=lambda x: (x.get("level") if isinstance(x.get("level"), int) else 99)):
            nv = v.get("level", "?")
            rasgos_nivel.setdefault(nv if isinstance(nv, int) else 0, []).append(v.get("name", "?"))
            rasgos.append({"n": v.get("name", "?"), "t": plano(v.get("entries")),
                           "nivel": nv, "fuente": v.get("source", "?"),
                           "pagina": v.get("page")})
        cols, filas, con_conjuros = _tabla_clase(c, rasgos_nivel)
        subs = []
        vistos = set()
        for s in d.get("subclass", []):
            if s.get("className") != nom:
                continue
            if (s.get("name"), s.get("source")) in vistos:
                continue
            vistos.add((s.get("name"), s.get("source")))
            ssrc = s.get("source", "?")
            fr = [v for v in d.get("subclassFeature", [])
                  if v.get("className") == nom and v.get("source") == ssrc
                  and (v.get("subclassShortName") == s.get("shortName")
                       or v.get("subclassShortName") == s.get("name"))]
            fr.sort(key=lambda x: (x.get("level") if isinstance(x.get("level"), int) else 99))
            subs.append({"nombre": s.get("name", "?"), "corto": s.get("shortName") or s.get("name", "?"),
                         "fuente": ssrc, "corta": FUENTE_CORTA.get(ssrc, ssrc),
                         "pagina": s.get("page"),
                         "desc": plano(s.get("entries")),
                         "rasgos": [{"n": v.get("name", "?"), "t": plano(v.get("entries")),
                                     "nivel": v.get("level", "?"), "fuente": v.get("source", "?"),
                                     "pagina": v.get("page")} for v in fr]})
        texto = "\n".join(cab)
        texto += "\n\n### Tabla de " + nom + "\n"
        for f_ in rasgos:
            texto += f"\n### Nv {f_['nivel']} — {f_['n']}\n{f_['t']}\n"
        for s in subs:
            texto += f"\n### Subclase: {s['nombre']}\n{s['desc']}\n"
            for f_ in s["rasgos"]:
                texto += f"\n### Nv {f_['nivel']} — {f_['n']}\n{f_['t']}\n"
        b = {"v": "clase", "nombre": nom, "fuente": src,
             "corta": FUENTE_CORTA.get(src, src), "pagina": c.get("page"),
             "ref": c.get("referenceSources") or [],
             "cabecera": cab, "columnas": cols, "filas": filas,
             "con_conjuros": con_conjuros, "rasgos": rasgos, "subclases": subs,
             "texto": plano(c.get("entries"))}
        r = _f(src, nom, texto)
        if r:
            out.append((*r, b))
    return out


def monstruos_de(d):
    out = []
    for v in d.get("monster", []):
        cab = []
        sz = v.get("size")
        szs = ", ".join(TAMANO.get(x, x) for x in (sz if isinstance(sz, list) else [sz])) \
            if sz else ""
        tipo = " ".join(t for t in [szs, _tipo(v.get("type"))] if t)
        al = _alin(v.get("alignment"))
        cab.append(tipo + (f", {al}" if al else "") if tipo else al)
        ac, pg = _ca(v.get("ac")), _pg(v.get("hp"))
        if ac or pg:
            cab.append(f"CA {ac} · PG {pg}")
        if v.get("speed"):
            cab.append(f"Vel {_vel(v['speed'])}")
        ab = v.get("str"), v.get("dex"), v.get("con"), v.get("int"), \
            v.get("wis"), v.get("cha")
        if any(x is not None for x in ab):
            cab.append("FUE {} DES {} CON {} INT {} SAB {} CAR {}".format(
                *[x if x is not None else "—" for x in ab]))
        for k, et in (("save", "Salv"), ("skill", "Hab"), ("senses", "Sentidos"),
                      ("languages", "Idiomas"), ("cr", "CR")):
            if v.get(k) is not None:
                cab.append(f"{et}: {_pares(v[k]) if isinstance(v[k], dict) else txt(v[k])}")
        partes = ["\n".join(cab)] if cab else []
        for tit, arr in (("Rasgos", v.get("trait")), ("Acciones", v.get("action")),
                         ("Acc. legendarias", v.get("legendary")),
                         ("Acc. de guarida", v.get("lairActions")),
                         ("Efectos regionales", v.get("regionalEffects"))):
            if arr:
                partes.append(f"--- {tit} ---\n" + plano(arr))
        if v.get("spellcasting"):
            partes.append("--- Conjuros ---\n" + plano(v["spellcasting"]))
        r = _f(v.get("source"), v.get("name"), "\n\n".join(partes))
        if r:
            out.append((*r, statblock_de(v)))
    return out


EXTRACT = {"regla": reglas_de, "objeto": objetos_de, "clase": clases_de,
           "monstruo": monstruos_de, "hechizo": lambda d: hechizos_de(d, _CLASES_IDX),
           "especie": especies_de, "trasfondo": trasfondos_de, "dote": dotes_de}

_CLASES_IDX = {}


def cargar_clases_hechizo():
    """spells/sources.json: (hechizo, libro) -> [clases]."""
    idx = {}
    try:
        d = json.loads(descargar("spells/sources.json").read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  (sin índice de clases: {e})")
        return idx
    for libro, hechizos in d.items():
        if not isinstance(hechizos, dict):
            continue
        for nombre, info in hechizos.items():
            cls = []
            for c in (info.get("class") or []) if isinstance(info, dict) else []:
                if isinstance(c, dict) and c.get("name") and c["name"] not in cls:
                    cls.append(c["name"])
            if cls:
                idx[(nombre, libro)] = cls
    return idx


TAMANO = {"T": "Diminuto", "S": "Pequeño", "M": "Mediano", "L": "Grande",
          "H": "Enorme", "G": "Gargantuesco", "V": "Varía"}
ALIN = {"L": "legal", "N": "neutral", "C": "caótico", "G": "bueno", "E": "malvado",
        "A": "cualquiera", "U": "sin alineamiento", "NX": "neutral",
        "LX": "legal", "CX": "caótico", "NG": "neutral bueno", "NE": "neutral malvado",
        "LG": "legal bueno", "LE": "legal malvado", "CG": "caótico bueno",
        "CE": "caótico malvado"}
TIPO = {"aberration": "aberración", "beast": "bestia", "celestial": "celestial",
        "construct": "constructo", "dragon": "dragón", "elemental": "elemental",
        "fey": "feérico", "fiend": "infernal", "giant": "gigante",
        "humanoid": "humanoide", "monstrosity": "monstruosidad", "ooze": "cieno",
        "plant": "planta", "swarm": "enjambre", "undead": "no muerto"}


def _alin(v):
    if isinstance(v, str):
        return ALIN.get(v, v)
    if isinstance(v, list):
        return " ".join(ALIN.get(x, x) if isinstance(x, str) else txt(x) for x in v)
    if isinstance(v, dict):
        return _alin(v.get("alignment"))
    return ""


def _tipo(v):
    if isinstance(v, str):
        return TIPO.get(v, v)
    if isinstance(v, dict):
        t = v.get("type", "")
        base = TIPO.get(t, t) if isinstance(t, str) else txt(t)
        tags = v.get("tags") or []
        tags = [tags] if isinstance(tags, str) else tags
        extra = ", ".join(str(t) for t in tags)
        return f"{base} ({extra})" if extra else base
    return txt(v)


def _ca(v):
    if isinstance(v, list):
        partes = []
        for x in v:
            if isinstance(x, dict):
                n = x.get("ac", "?")
                d = x.get("from")
                d = ", ".join(plano(i) for i in d) if isinstance(d, list) else plano(d)
                c = plano(x.get("condition")) if x.get("condition") else ""
                partes.append(f"{n}" + (f" ({d})" if d else "") + (f" {c}" if c else ""))
            else:
                partes.append(str(x))
        return ", ".join(partes)
    return txt(v)


VEL = {"walk": "", "fly": "volar", "swim": "nadar", "climb": "trepar",
       "burrow": "excavar"}


def _vel(v):
    if isinstance(v, dict):
        partes = []
        for k, val in v.items():
            if isinstance(val, dict):
                n = val.get("number", "?")
                c = val.get("condition")
                c = ", ".join(plano(i) for i in c) if isinstance(c, list) else plano(c)
                etiqueta = VEL.get(k, k)
                partes.append(f"{etiqueta + ' ' if etiqueta else ''}{n} pies" + (f" {c}" if c else ""))
            elif isinstance(val, bool):
                if val and k not in VEL:
                    partes.append(str(k))
            else:
                etiqueta = VEL.get(k, k)
                partes.append(f"{etiqueta + ' ' if etiqueta else ''}{val} pies")
        return ", ".join(partes)
    return txt(v)


def _pares(v):
    if isinstance(v, dict):
        return ", ".join(f"{str(k).capitalize()} {txt(val)}" for k, val in v.items())
    return txt(v)


def _pg(v):
    if isinstance(v, dict):
        med = v.get("average", "?")
        return f"{med} ({v['formula']})" if v.get("formula") else str(med)
    return txt(v)


def _pg(v):
    if isinstance(v, dict):
        med = v.get("average", "?")
        return f"{med} ({v['formula']})" if v.get("formula") else str(med)
    return txt(v)


SKILL_ES = {"acrobatics": "Acrobacias", "animal handling": "Trato con animales",
            "arcana": "Arcana", "athletics": "Atletismo", "deception": "Engaño",
            "history": "Historia", "insight": "Perspicacia",
            "intimidation": "Intimidación", "investigation": "Investigación",
            "medicine": "Medicina", "nature": "Naturaleza",
            "perception": "Percepción", "performance": "Interpretación",
            "persuasion": "Persuasión", "religion": "Religión",
            "sleight of hand": "Juego de manos", "stealth": "Sigilo",
            "survival": "Supervivencia"}
CAR_ES = {"str": "FUE", "dex": "DES", "con": "CON", "int": "INT",
          "wis": "SAB", "cha": "CAR"}
SENT_ES = {"darkvision": "visión en la oscuridad",
           "blindsight": "vista ciega", "tremorsense": "sentido sísmico",
           "truesight": "visión verdadera"}
FUENTE_CORTA = {"XMM": "MM '25", "XPHB": "PHB '24", "XDMG": "DMG '24",
                "MM": "MM '14", "PHB": "PHB '14", "DMG": "DMG '14"}

XP_POR_CR = {0: 10, 0.125: 25, 0.25: 50, 0.5: 100, 1: 200, 2: 450, 3: 700,
             4: 1100, 5: 1800, 6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900,
             11: 7200, 12: 8400, 13: 10000, 14: 11500, 15: 13000, 16: 15000,
             17: 18000, 18: 20000, 19: 22000, 20: 25000, 21: 33000, 22: 41000,
             23: 50000, 24: 62000, 25: 75000, 26: 90000, 27: 105000,
             28: 120000, 29: 135000, 30: 155000}


def _cr_num(cr):
    try:
        if isinstance(cr, dict):
            cr = cr.get("cr", "?")
        s = str(cr).strip()
        if "/" in s:
            a, b = s.split("/")
            return float(a) / float(b)
        return float(s)
    except (ValueError, TypeError):
        return None


def _pb_por_cr(num):
    if num is None:
        return None
    if num <= 4:
        return 2
    if num <= 8:
        return 3
    if num <= 12:
        return 4
    if num <= 16:
        return 5
    if num <= 20:
        return 6
    if num <= 24:
        return 7
    return 8


def _mod(score):
    try:
        m = (int(score) - 10) // 2
    except (ValueError, TypeError):
        return "+0"
    return f"+{m}" if m >= 0 else str(m)


def _mod_int(score):
    try:
        return (int(score) - 10) // 2
    except (ValueError, TypeError):
        return 0


def _iniciativa(v, dex_score, pb):
    """Fórmula 5e.tools: bono explícito o mod DES (+ pericia×PB); pasiva 10+bono."""
    try:
        base = _mod_int(dex_score)
    except (ValueError, TypeError):
        base = 0
    ini = v.get("initiative")
    if isinstance(ini, bool):
        ini = None
    if isinstance(ini, (int, float)):
        b, pas = int(ini), 10 + int(ini)
    elif isinstance(ini, dict):
        if isinstance(ini.get("initiative"), (int, float)):
            b = int(ini["initiative"])
            pas = 10 + b
        else:
            mult = ini.get("proficiency", 0)
            mult = mult if isinstance(mult, (int, float)) else 0
            b = base + mult * (pb or 0)
            adv = ini.get("advantageMode")
            pas = 10 + b + (5 if adv == "adv" else -5 if adv == "dis" else 0)
    else:
        b, pas = base, 10 + base
    return f"{b:+d} ({pas})"


def _bloques(arr):
    """[{name, entries}] -> [{n, t}] con texto plano."""
    out = []
    for x in arr or []:
        if isinstance(x, dict):
            t = plano(x.get("entries", []))
            if x.get("name") or t:
                out.append({"n": _tags(x.get("name", "")), "t": t})
    return out


def _conjuros(arr):
    """Spellcasting 5eTools -> bloques clasificados por displayAs."""
    acc, rea, otros = [], [], []
    for x in arr or []:
        if not isinstance(x, dict):
            continue
        partes = []
        if x.get("headerEntries"):
            partes.append(plano(x["headerEntries"]))
        for etiqueta, clave in (("A voluntad", "will"),):
            if x.get(clave):
                partes.append(f"{etiqueta}: " + ", ".join(
                    _tags(s).strip() for s in x[clave] if isinstance(s, str)))
        for etiqueta, clave in (("Día", "daily"),):
            dd = x.get(clave) or {}
            if isinstance(dd, dict):
                for niv, lst in dd.items():
                    if isinstance(lst, list):
                        partes.append(f"{niv}/día: " + ", ".join(
                            _tags(s).strip() for s in lst if isinstance(s, str)))
        t = "\n".join(partes)
        dest = {"action": acc, "reaction": rea}.get(x.get("displayAs"), otros)
        dest.append({"n": _tags(x.get("name", "Conjuros")),
                     "t": t or plano(x.get("entries", []))})
    return acc, rea, otros


def statblock_de(v):
    """Monstruo 5eTools -> dict display-ready para el statblock HTML."""
    abil = {}
    for c in ("str", "dex", "con", "int", "wis", "cha"):
        abil[c] = v.get(c, 10)
    mods = {c: _mod(abil[c]) for c in abil}
    saves_d = v.get("save") or {}
    saves = {c: str(saves_d.get(c, mods[c])) for c in abil}
    hab = [(SKILL_ES.get(k.lower(), k.capitalize()), str(val))
           for k, val in (v.get("skill") or {}).items()]
    sen = v.get("senses")
    sen = ", ".join(f"{SENT_ES.get(k.lower(), k)} {txt(val)}".strip()
                    for k, val in sen.items()) if isinstance(sen, dict) else txt(sen)
    sen = sen.replace("ft.", "pies").replace("ft", "pies")
    cr = v.get("cr", "?") if not isinstance(v.get("cr"), dict) else v["cr"].get("cr", "?")
    num = _cr_num(cr)
    pb = _pb_por_cr(num)
    acc, rea, otros = _conjuros(v.get("spellcasting"))
    acciones = _bloques(v.get("action")) + acc
    reacciones = _bloques(v.get("reaction")) + rea
    rasgos = _bloques(v.get("trait")) + otros
    hab_names = {k.lower() for k in (v.get("skill") or {})}
    try:
        pp = int(v.get("passive"))
    except (ValueError, TypeError):
        try:
            wm = int(mods.get("wis", "+0"))
        except (ValueError, TypeError):
            wm = 0
        b = pb if (pb and "perception" in hab_names) else 0
        pp = 10 + wm + b
    src = v.get("source", "?")
    return {
        "v": 1, "nombre": v.get("name", "?"), "fuente": src,
        "corta": FUENTE_CORTA.get(src, src), "pagina": v.get("page"),
        "ref": v.get("referenceSources") or [],
        "tam": ", ".join(TAMANO.get(x, x) for x in
                         ([y for y in v["size"] if y] if isinstance(v.get("size"), list)
                          else ([v["size"]] if v.get("size") else []))),
        "tipo": _tipo(v.get("type")), "alin": _alin(v.get("alignment")),
        "ca": _ca(v.get("ac")), "pg": _pg(v.get("hp")), "vel": _vel(v.get("speed")),
        "ini": _iniciativa(v, abil["dex"], pb),
        "car": {CAR_ES[c]: {"score": abil[c], "mod": mods[c], "save": saves[c]} for c in abil},
        "hab": hab, "sentidos": sen, "pp": pp,
        "idiomas": txt(v.get("languages")), "cr": str(cr),
        "xp": XP_POR_CR.get(num), "pb": pb,
        "rasgos": rasgos, "acciones": acciones, "reacciones": reacciones,
        "legendarias": _bloques(v.get("legendary")),
        "habitat": ", ".join(str(x).capitalize() for x in (v.get("environment") or [])),
        "tesoro": ", ".join(str(x).capitalize() for x in (v.get("treasure") or [])),
    }


def rango_fuente(f):
    return RANK.get(f, 2)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Importa datos 5eTools al compendio")
    ap.add_argument("--categorias", default="regla,objeto,clase,monstruo,hechizo,especie,trasfondo,dote",
                    help="coma-separado entre regla,objeto,clase,monstruo,hechizo,especie,trasfondo,dote")
    ap.add_argument("--limite", type=int, default=0, help="máx. registros por categoría (0 = todo)")
    ap.add_argument("--recargar", action="store_true", help="redescarga los JSON")
    ap.add_argument("--fuentes", action="store_true", help="lista libros y sale")
    args = ap.parse_args()
    cats = [c.strip() for c in args.categorias.split(",") if c.strip() in EXTRACT]

    global _CLASES_IDX
    if "hechizo" in cats:
        print("[hechizo] índice de clases por libro")
        _CLASES_IDX = cargar_clases_hechizo()

    registros = {}  # (cat, nombre) -> (rank, fuente, texto, datos)
    fuentes = set()
    for cat in cats:
        archs = archivos_categoria(cat)
        print(f"[{cat}] {len(archs)} ficheros")
        for rel in archs:
            d = json.loads(descargar(rel, args.recargar).read_text(encoding="utf-8"))
            for rec in EXTRACT[cat](d):
                nombre, fuente, texto = rec[0], rec[1], rec[2]
                datos = rec[3] if len(rec) > 3 else {}
                if not oficial(fuente.rsplit("·", 1)[-1].strip()):
                    continue
                fuentes.add(fuente)
                if args.limite and sum(1 for k in registros if k[0] == cat) >= args.limite:
                    break
                clave = (cat, nombre)
                rk = rango_fuente(fuente.rsplit("·", 1)[-1].strip())
                if clave not in registros or rk < registros[clave][0]:
                    registros[clave] = (rk, fuente, texto, datos)

    print(f"\nLibros detectados ({len(fuentes)}):")
    for f in sorted(fuentes):
        print("  " + f)
    if args.fuentes:
        return

    init_db()
    con = sqlite3.connect(DB_PATH)
    antes = con.execute("SELECT COUNT(*) FROM compendio").fetchone()[0]
    borrados = 0
    if not args.limite:
        # Regeneración completa de esas categorías (las filas del usuario no se tocan)
        con.execute("DELETE FROM compendio WHERE fuente LIKE '5eTools · %' AND categoria IN ({})".format(
            ",".join("?" * len(cats))), cats)
        borrados = con.total_changes
    con.executemany("INSERT OR IGNORE INTO compendio(categoria,nombre,fuente,contenido,datos) VALUES(?,?,?,?,?)",
                    [(c, n, f, t, json.dumps(dt, ensure_ascii=False))
                     for (c, n), (_, f, t, dt) in registros.items()])
    con.commit()
    # Tabla de fuentes para el filtro por libros (código -> nombre largo)
    libros_json = cargar_nombres_libros()
    codigos = {f.rsplit("·", 1)[-1].strip() for _, f, _, _ in registros.values()}
    con.executemany("INSERT OR IGNORE INTO fuentes(codigo,nombre) VALUES(?,?)",
                    [(cod, nombre_libro(cod, libros_json)) for cod in codigos])
    con.commit()
    despues = con.execute("SELECT COUNT(*) FROM compendio").fetchone()[0]
    con.close()
    print(f"\nRegistros procesados: {len(registros)} · 5eTools anteriores: {borrados} "
          f"(compendio: {antes} -> {despues})")


if __name__ == "__main__":
    main()
