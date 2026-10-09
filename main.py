"""D&D 2024 Desktop - ventana principal."""
import faulthandler
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.database import init_db
from src.arte import cargar_fuentes, qss, splash
from src.widgets.worldmap import WorldMapWidget
from src.widgets.battlemap import BattleMapWidget
from src.views.personajes_view import PersonajesView
from src.views.ficha_view import FichaView
from src.views.ciudades_view import CiudadesView
from src.views.compendio_view import CompendioView

QSS = None  # el tema vive en src/arte.py (estilo Bloodborne)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("D&D 2024 — Mapas, Personajes y Compendio")
        self.resize(1360, 860)
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)

        self.battle = BattleMapWidget()
        self.world = WorldMapWidget(goto_battlemap=self.ir_battlemap)
        self.pers = PersonajesView()
        self.ficha = FichaView()
        self.ciud = CiudadesView()
        self.comp = CompendioView()

        tabs.addTab(self.world, "🗺 Mapas del mundo")
        tabs.addTab(self.battle, "⚔ Battlemap (cuadrícula)")
        tabs.addTab(self.pers, "🧙 Personajes")
        tabs.addTab(self.ficha, "📄 Ficha")
        tabs.addTab(self.ciud, "🏙 Ciudades")
        tabs.addTab(self.comp, "📚 Compendio 2024")
        tabs.currentChanged.connect(self._refresh)
        self.tabs = tabs
        self.setCentralWidget(tabs)
        self.statusBar().showMessage("Que la sangre te guíe · 1 casilla = 5 pies")

    def _refresh(self, i):
        w = self.tabs.widget(i)
        if hasattr(w, "refrescar"):
            w.refrescar()
        if hasattr(w, "refresh"):
            w.refresh()

    def ir_battlemap(self, mid=None):
        self.tabs.setCurrentWidget(self.battle)
        if mid is not None:
            self.battle.seleccionar(mid)


def main():
    init_db()
    import io
    log = open(Path(__file__).resolve().parent / "data" / "crash.log",
               "a", encoding="utf-8")
    faulthandler.enable(file=log)
    sys.stderr = io.TextIOWrapper(open(Path(__file__).resolve().parent / "data" / "error.log",
                                       "ab", buffering=0),
                                  encoding="utf-8", errors="replace", write_through=True)
    app = QApplication(sys.argv)
    cargar_fuentes()
    app.setStyleSheet(qss())
    sp = splash()
    if sp is not None:
        sp.show()
        app.processEvents()
    m = Main()
    m.show()
    if sp is not None:
        import time
        t0 = time.time()
        while time.time() - t0 < 2.2:
            app.processEvents()
            time.sleep(0.05)
        sp.finish(m)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
