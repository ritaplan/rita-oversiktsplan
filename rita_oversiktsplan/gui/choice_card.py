"""Ett val som ett kort (ikon, rubrik och förklaring), för dialogen Leverans och export (som i Rita Detaljplan). Kortet som
är valt har en färgad ram, ett klick var som helst på ett kort väljer det, och ett val som inte går ritas grått."""
from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout

ICONS = Path(__file__).resolve().parent.parent / "icons"
ICON_SIZE = 28
# korten: en tunn ram, och en färgad ram med lätt bakgrund på det valda kortet (genomskinligt, så att det passar båda teman)
CARD_STYLE = """
QFrame#choiceCard { border: 1px solid rgba(128, 128, 128, 100); border-radius: 6px; }
QFrame#choiceCard:hover { border-color: rgba(30, 110, 200, 170); }
QFrame#choiceCard[chosen="true"] { border: 2px solid rgba(30, 110, 200, 220); background-color: rgba(30, 110, 200, 22); }
QFrame#choiceCard[available="false"] { background-color: rgba(128, 128, 128, 18); }
QLabel#muted { color: palette(placeholder-text); }
"""


class ChoiceCard(QFrame):
    """Ett val med ikon, rubrik (radioknappen) och förklaring. Radioknappen och innehållet läggs i ``body``."""

    def __init__(self, radio: QRadioButton, icon_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("choiceCard")
        self.radio = radio
        self.setProperty("chosen", False)
        self.setProperty("available", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        symbol = QLabel()
        symbol.setPixmap(QIcon(str(ICONS / icon_name)).pixmap(QSize(ICON_SIZE, ICON_SIZE)))
        symbol.setAlignment(Qt.AlignmentFlag.AlignTop)
        font = radio.font()
        font.setBold(True)
        radio.setFont(font)
        self.body = QVBoxLayout()
        self.body.setSpacing(2)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(radio)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)  # kortet är precis så stort som innehållet
        row.setSpacing(10)
        row.addWidget(symbol)
        row.addLayout(self.body, 1)
        radio.toggled.connect(self._mark)

    def _restyle(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)

    def _mark(self, chosen: bool) -> None:
        self.setProperty("chosen", chosen)
        self._restyle()

    def set_available(self, available: bool) -> None:
        """Ett val som inte går just nu (t.ex. leverans utan inställningar) ritas grått. Själva kortet är inte avstängt:
        knappen till inställningarna och förklaringen ska fungera."""
        self.radio.setEnabled(available)
        self.setProperty("available", available)
        self._restyle()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt
        if self.radio.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.radio.setChecked(True)
        super().mousePressEvent(event)


def muted(text: str = "") -> QLabel:
    """Förklarande text i dämpad färg, något mindre än rubriken."""
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    font = label.font()
    font.setPointSizeF(max(font.pointSizeF() - 1, 7))
    label.setFont(font)
    return label
