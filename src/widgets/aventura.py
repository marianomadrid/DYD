"""Diálogo de aventura estilo videojuego: texto progresivo + opciones."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, QTimer, Signal, QCoreApplication, QEvent
from ..database import BASE


def _vaciar(lay):
    """Quita los widgets de un layout sin dejar duplicados colgando."""
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


class DialogoAventura(QDialog):
    terminada = Signal(bool)  # True si llegó a un final (sin opciones)

    def __init__(self, aventura, velocidad=18, parent=None):
        super().__init__(parent)
        self.av = aventura
        self._vel = velocidad
        self._texto = ""
        self._pos = 0
        self.setWindowTitle(aventura.guion.get("titulo", "Aventura"))
        self.resize(620, 480)
        self.setModal(True)

        self.lbl_titulo = QLabel("")
        self.lbl_titulo.setFont(QFont("Cinzel Decorative", 16, QFont.Bold))
        self.lbl_titulo.setStyleSheet("color:#c8a44d;")
        self.lbl_retrato = QLabel()
        self.lbl_retrato.setFixedHeight(180)
        self.lbl_retrato.setAlignment(Qt.AlignCenter)
        self.lbl_retrato.setVisible(False)
        self.txt = QTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setFont(QFont("Libre Baskerville", 13))
        self.caja_opciones = QVBoxLayout()
        self.b_cerrar = QPushButton("Cerrar")

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl_titulo)
        lay.addWidget(self.lbl_retrato)
        lay.addWidget(self.txt, 1)
        lay.addLayout(self.caja_opciones)
        fila = QHBoxLayout()
        fila.addStretch(1)
        fila.addWidget(self.b_cerrar)
        lay.addLayout(fila)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._avanza_texto)
        self.b_cerrar.clicked.connect(self._cerrar)
        self.txt.mousePressEvent = lambda ev: self._completar()
        self._mostrar_nodo()

    # ---- flujo ----
    def _mostrar_nodo(self):
        n = self.av.nodo
        self.lbl_titulo.setText(n.get("titulo", ""))
        ruta = n.get("retrato", "")
        if ruta:
            from pathlib import Path
            p = Path(ruta)
            if not p.is_absolute():
                p = BASE / p
            pm = QPixmap(str(p))
            if not pm.isNull():
                self.lbl_retrato.setPixmap(
                    pm.scaledToHeight(180, Qt.SmoothTransformation))
                self.lbl_retrato.setVisible(True)
            else:
                self.lbl_retrato.setVisible(False)
        else:
            self.lbl_retrato.setVisible(False)
        _vaciar(self.caja_opciones)
        self._texto = n.get("texto", "")
        self._pos = 0
        self.txt.clear()
        if self._vel <= 0:
            self.txt.setPlainText(self._texto)
            self._pos = len(self._texto)
            self._pintar_opciones(True)
        else:
            self.timer.start(self._vel)
            self._pintar_opciones(False)

    def _avanza_texto(self):
        self._pos += 3
        if self._pos >= len(self._texto):
            self._completar()
            return
        self.txt.setPlainText(self._texto[:self._pos])
        self.txt.verticalScrollBar().setValue(self.txt.verticalScrollBar().maximum())

    def _completar(self):
        self.timer.stop()
        if self._pos < len(self._texto):
            self._pos = len(self._texto)
            self.txt.setPlainText(self._texto)
        self._pintar_opciones(True)

    def _pintar_opciones(self, activas):
        _vaciar(self.caja_opciones)
        ops = self.av.opciones()
        if not ops:
            b = QPushButton("Terminar")
            b.clicked.connect(self._cerrar)
            self.caja_opciones.addWidget(b)
            return
        for i, op in enumerate(ops):
            b = QPushButton(f"{i + 1}. {op.get('texto', '')}")
            b.setEnabled(activas)
            b.clicked.connect(lambda _=False, n=i: self._elegir(n))
            self.caja_opciones.addWidget(b)

    def _elegir(self, i):
        if self.av.elegir(i) is None:
            self.terminada.emit(True)
            self.accept()
        else:
            self._mostrar_nodo()

    def _cerrar(self):
        self.terminada.emit(self.av.es_final())
        self.accept()
