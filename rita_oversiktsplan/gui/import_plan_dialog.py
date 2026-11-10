"""Dialogruta för att importera en plan ur en GeoPackage-fil till en PostGIS-databas (se ``core.transfer``)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from qgis.gui import QgsFileWidget
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from ..core import storage, transfer
from .database_target import DatabaseTarget

ICONS = Path(__file__).resolve().parent.parent / "icons"


@dataclass(frozen=True)
class ImportValues:
    path: Path
    connection: str
    schema: str
    plan_id: str


class ImportPlanDialog(QDialog):
    def __init__(self, parent=None, connections: Optional[dict] = None, connection: Optional[str] = None,
                 schema: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Importera plan till databasen")
        self.setMinimumWidth(520)
        self._connections = connections if connections is not None else storage.postgis_connections()
        self._plan_edited = False  # användaren har valt plan-id själv: föreslå inte över det
        self._description, self._problem = "", ""  # om filen: vad den innehåller, och varför den inte duger

        self.file = QgsFileWidget()
        self.file.setFilter("GeoPackage (*.gpkg)")
        self.file.setDialogTitle("Välj planens GeoPackage")
        self.target = DatabaseTarget(self._connections, connection, schema)
        self.connection, self.schema = self.target.connection, self.target.schema
        self.plan_id = QLineEdit()
        self.plan_id.setPlaceholderText("plan-id, t.ex. op_2040")
        self.plan_id.setToolTip("Planens identifierare inom schemat (måste vara unik där). Gemener a–z, siffror och "
                                "understreck.")
        self.info = QLabel()
        self.info.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Planfil", self.file)
        self.target.add_rows(form)
        form.addRow("Plan-id", self.plan_id)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.setWindowIcon(QIcon(str(ICONS / "import_plan.svg")))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Importera")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setIcon(QIcon(str(ICONS / "import_plan.svg")))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Avbryt")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.info)
        layout.addWidget(self.buttons)

        self.file.fileChanged.connect(self._file_changed)
        self.connection.currentIndexChanged.connect(self._update)
        self.schema.currentTextChanged.connect(self._update)
        self.plan_id.textEdited.connect(self._plan_id_edited)
        self.plan_id.textChanged.connect(self._update)
        self._update()

    def _plan_id_edited(self, *_) -> None:
        self._plan_edited = True

    def _file_changed(self, path: str) -> None:
        """Läser filen en gång (inte för varje tangent i de andra fälten) och föreslår plan-id."""
        self._description, self._problem = self._inspect(path.strip())
        if not self._plan_edited:
            self.plan_id.setText(storage.identifier(Path(path).stem))
        self._update()

    @staticmethod
    def _inspect(path: str) -> tuple[str, str]:
        """(vad filen innehåller, varför den inte duger) för filen; tomt om ingen fil är vald."""
        if not path:
            return "", ""
        try:
            meta = transfer.read_plan_file(Path(path))
        except transfer.TransferError as exc:
            return "", str(exc)
        return f"Koordinatsystem EPSG:{meta.get('epsg', '3006')}. Ett schema som redan finns måste ha samma.", ""

    def is_valid(self) -> bool:
        return bool(self._description) and self.target.is_valid() and storage.is_valid_plan_id(self.plan_id.text().strip())

    def _update(self, *_) -> None:
        self.info.setText(self._description or self._problem)
        self.info.setStyleSheet("color: #b3261e;" if self._problem else "")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.is_valid())

    def values(self) -> ImportValues:
        return ImportValues(Path(self.file.filePath().strip()), self.target.connection_name(), self.target.schema_name(),
                            self.plan_id.text().strip())
