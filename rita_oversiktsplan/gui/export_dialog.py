"""Dialogen Leverans och export (uppbyggd som i Rita Detaljplan): kontrollen av planen i en egen ruta överst, med en kant i
resultatets färg, och tre alternativ som kort med ikon: leverera planen till NGP, spara den som JSON-fil eller samla den i
ett arkivpaket. Det valda kortet har en färgad ram.

Dialogen öppnas alltid, även om inställningarna för leverans till NGP inte är gjorda: då går leveransen inte att välja,
rutan säger vad som saknas och har en knapp till inställningarna, medan fil och arkivpaket fungerar ändå."""
from __future__ import annotations

from typing import Callable, Optional

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QBrush, QColor, QIcon
from qgis.PyQt.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
                                 QListWidget, QListWidgetItem, QPushButton, QRadioButton, QVBoxLayout)

from ..core import export_lm
from ..core.ngp_client import NgpConfig
from .choice_card import CARD_STYLE, ICONS, ChoiceCard, muted
from .delivery_dialog import confirmation_text

MARKS = {export_lm.FEL: "✘", export_lm.VARNING: "▲"}
COLORS = {export_lm.FEL: QColor(179, 38, 30), export_lm.VARNING: QColor(176, 110, 0)}
UPLOAD, FILE, ARCHIVE = "upload", "file", "archive"
# kontrollen är inte ett av alternativen och får inte se ut som ett valt kort (blå ram): en grå ruta med en bred kant i
# resultatets färg (genomskinlig, så att den fungerar i ljust och mörkt tema)
CHECK_BOX_STYLE = """
QGroupBox#checkBox { background-color: rgba(128, 128, 128, 22); border: 1px solid rgba(128, 128, 128, 70);
                     border-left: 5px solid rgba(%s); border-radius: 4px; margin-top: 8px; padding-top: 4px; }
QGroupBox#checkBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 4px; }
"""
CHECK_COLOURS = {"good": "27, 127, 59, 230", "warning": "214, 140, 0, 230", "error": "179, 38, 30, 230"}
MARKS_RESULT = {"good": ("✔", "#1b7f3b"), "warning": ("▲", "#b06e00"), "error": ("✘", "#b3261e")}


def summary(collection: dict, problems: list[export_lm.Problem]) -> str:
    counts = export_lm.counts(collection)
    parts = [f"{counts.get(kind, 0)} {name}" for kind, name in (("beslutOP", "beslut"), ("innehallOP", "innehåll"))]
    errors = sum(1 for p in problems if p.level == export_lm.FEL)
    warnings = len(problems) - errors
    warning_text = f"{warnings} varning" if warnings == 1 else f"{warnings} varningar"
    text = f"Planen med {parts[0]} och {parts[1]}. "
    if errors:
        text += (f"Kontrollen hittade {errors} fel och {warning_text}. Planen går att spara och arkivera, men den följer "
                 "inte Lantmäteriets format förrän felen är rättade, och NGP stoppar en leverans med fel.")
    elif warnings:
        text += f"Kontrollen hittade inga fel men {warning_text}."
    else:
        text += "Kontrollen hittade inget att anmärka på."
    return text


class _ProblemList(QListWidget):
    """Listan med anmärkningar vill vara låg, så att dialogen inte blir högre än skärmen; den växer om man drar
    dialogen större."""

    def sizeHint(self) -> QSize:  # noqa: N802 - namnet krävs av Qt
        return QSize(400, 120)


class ExportDialog(QDialog):
    """``show`` anropas med (tabell, fid) när man dubbelklickar på en anmärkning som gäller ett objekt. ``save``,
    ``deliver`` och ``archive`` gör jobbet och returnerar en text när det gick (då stängs dialogen) eller None (då
    ligger dialogen kvar). ``config`` ger inställningarna för NGP och ``resuming`` om en tidigare mottagning
    återanvänds."""

    def __init__(self, collection: dict, problems: list[export_lm.Problem], save: Callable[[], Optional[str]],
                 show: Callable[[str, int], None], parent=None, deliver: Optional[Callable[[], Optional[str]]] = None,
                 archive: Optional[Callable[[], Optional[str]]] = None,
                 settings: Optional[Callable[[], None]] = None,
                 config: Optional[Callable[[], NgpConfig]] = None,
                 resuming: Optional[Callable[[NgpConfig], bool]] = None):
        super().__init__(parent)
        self.setWindowTitle("Leverans och export")
        self.setWindowIcon(QIcon(str(ICONS / "export.svg")))
        self.setStyleSheet(CARD_STYLE)
        self.setMinimumWidth(640)
        self.problems = problems
        self.plan = next((f["properties"] for f in collection.get("features", [])
                          if f["properties"].get("feature:typ") == "oversiktsplan"), {})
        self.errors = sum(1 for p in problems if p.level == export_lm.FEL)
        self._save, self._show, self._deliver, self._archive = save, show, deliver, archive
        self._settings, self._config, self._resuming = settings, config, resuming

        # kontrollen
        self.check_mark = QLabel()  # ✔ ▲ ✘: resultatet av kontrollen med en blick
        self.check_mark.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        result = "error" if self.errors else "warning" if problems else "good"
        mark, colour = MARKS_RESULT[result]
        self.check_mark.setText(mark)
        self.check_mark.setStyleSheet(f"color: {colour}; font-size: 18px; font-weight: bold; min-width: 20px;")
        self.summary = QLabel(summary(collection, problems))
        self.summary.setWordWrap(True)
        self.list = _ProblemList()
        self.list.setMinimumHeight(70)
        self.list.setWordWrap(True)  # långa anmärkningar radbryts i stället för att rulla i sidled
        for problem in problems:
            item = QListWidgetItem(f"{MARKS[problem.level]}  {problem.text}")
            item.setForeground(QBrush(COLORS[problem.level]))
            item.setData(Qt.ItemDataRole.UserRole, problem)
            if problem.layer and problem.fid is not None:
                item.setToolTip("Dubbelklicka för att visa objektet.")
            self.list.addItem(item)
        self.list.setVisible(bool(problems))
        self.list.itemDoubleClicked.connect(self._double_clicked)
        self.list_hint = muted("Dubbelklicka på en anmärkning för att visa objektet i kartan.")
        self.list_hint.setVisible(bool(problems))
        self.check_box = QGroupBox("Kontroll av planen")
        self.check_box.setObjectName("checkBox")
        self.check_box.setStyleSheet(CHECK_BOX_STYLE % CHECK_COLOURS[result])
        check_layout = QVBoxLayout(self.check_box)
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        summary_row.addWidget(self.check_mark)
        summary_row.addWidget(self.summary, 1)
        check_layout.addLayout(summary_row)
        check_layout.addWidget(self.list, 1)
        check_layout.addWidget(self.list_hint)

        # alternativen
        self.upload = QRadioButton("Leverera till NGP")
        self.upload_info = QLabel()
        self.upload_info.setWordWrap(True)
        self.upload_info.setTextFormat(Qt.TextFormat.RichText)
        self.upload_problems = QLabel()
        self.upload_problems.setWordWrap(True)
        self.upload_problems.setStyleSheet("color: #b3261e;")
        self.settings_button = QPushButton("Inställningar…")
        self.settings_button.setToolTip("Inställningar för leverans till NGP: miljö, adresser och inloggning.")
        self.settings_button.clicked.connect(self._open_settings)
        self.understand = QCheckBox("Jag förstår att en godkänd plan publiceras i produktionsmiljön")
        self.upload_box = ChoiceCard(self.upload, "export.svg")
        self.upload_box.body.addWidget(self.upload_info)
        self.upload_box.body.addWidget(self.upload_problems)
        settings_row = QHBoxLayout()
        settings_row.addWidget(self.settings_button)
        settings_row.addStretch(1)
        self.upload_box.body.addLayout(settings_row)
        self.upload_box.body.addWidget(self.understand)
        self.upload_box.setVisible(deliver is not None)

        self.file = QRadioButton("Spara som JSON-fil")
        self.file_box = ChoiceCard(self.file, "file_json.svg")
        self.file_box.body.addWidget(muted(f"Skriver planen i Lantmäteriets format för översiktsplan (Översiktsplan 2.0, "
                                           f"testversion, {export_lm.MEDIATYP}) till en fil. Den kan granskas, skickas till "
                                           "NGP-supporten eller laddas upp av en producent."))

        self.archive_radio = QRadioButton("Skapa arkivpaket")
        self.archive_box = ChoiceCard(self.archive_radio, "archive.svg")
        self.archive_box.body.addWidget(muted("Samlar planen och dess handlingar (planhandlingen, underlagen och egna "
                                              "dokument) i ett arkivpaket med bevarandemetadata för långtidsbevarande, "
                                              "enligt Boverkets specifikation. Inget levereras till NGP."))
        self.archive_box.setVisible(archive is not None)

        self.group = QButtonGroup(self)  # alternativen ligger i olika rutor: koppla ihop dem
        for radio in (self.upload, self.file, self.archive_radio):
            self.group.addButton(radio)
            radio.toggled.connect(self._update)
        self.understand.toggled.connect(self._update)

        self.result = QLabel()
        self.result.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Stäng")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        self.buttons.accepted.connect(self.run)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(self.check_box, 1)
        layout.addWidget(self.upload_box)
        layout.addWidget(self.file_box)
        layout.addWidget(self.archive_box)
        layout.addWidget(self.result)
        layout.addWidget(self.buttons)
        self._first = True
        self._forced = False
        self.refresh()

    # -- leveransen till NGP -------------------------------------------------------------
    def config(self) -> Optional[NgpConfig]:
        return self._config() if self._config is not None else None

    def delivery_problems(self) -> list[str]:
        """Skäl till att leveransen inte går: kommunen saknas eller inställningarna är ofullständiga."""
        found = [] if self.plan.get("kommunkod") else [
            "Kommunen saknas i planens uppgifter (den avgör vilken producent som levererar)."]
        config = self.config()
        if config is None:
            return found + ["Inställningarna för leverans till NGP saknas."]
        return found + config.problems()

    def refresh(self) -> None:
        """Läser om inställningarna (till exempel efter Inställningar…) och uppdaterar leveransrutan."""
        problems = self.delivery_problems()
        can_upload = self._deliver is not None and not problems
        config = self.config()
        self.upload_box.set_available(can_upload)
        self.upload_problems.setText("\n".join(problems))
        self.upload_problems.setVisible(bool(problems))
        self.settings_button.setVisible(self._settings is not None)
        self.settings_button.setText("Inställningar…" if problems else "Ändra inställningar…")
        if can_upload:
            resuming = bool(self._resuming(config)) if self._resuming is not None else False
            self.upload_info.setText(confirmation_text(config, self.plan.get("planensTitel", ""),
                                                       self.plan.get("kommunnamn", ""), self.plan.get("kommunkod", ""),
                                                       self.errors, resuming).replace(" Vill du fortsätta?", ""))
        else:
            self.upload_info.setText("Leveransen görs via Lantmäteriets Uppdatering-API och kräver att kommunen har "
                                     "behörighet som producent för översiktsplan.")
        self._fit_upload_info()
        self.understand.setVisible(can_upload and config is not None and config.is_production)
        if not can_upload:
            if self.upload.isChecked() or self._first:  # ett eget val av fil eller arkivpaket ändras inte
                self.file.setChecked(True)
                self._forced = True  # filen valdes av programmet, inte av användaren
        elif self._first or self._forced:
            self.upload.setChecked(True)  # standardval när leveransen går
            self._forced = False
        self._first = False
        self._update()

    def _fit_upload_info(self) -> None:
        """En radbruten etikett med formaterad text får annars för låg höjd i en ruta, och de sista styckena klipps.
        Höjden räknas för dialogens minsta bredd (dialogen kan bli bredare, då blir det bara lite luft kvar)."""
        self.upload_info.setMinimumHeight(self.upload_info.heightForWidth(self.minimumWidth() - 80))
        if self.layout() is not None:
            self.layout().activate()

    def _open_settings(self) -> None:
        if self._settings is not None:
            self._settings()
        self.refresh()

    # -- valet ---------------------------------------------------------------------------
    def choice(self) -> str:
        if self.archive_radio.isChecked() and self._archive is not None:
            return ARCHIVE
        return UPLOAD if self.upload.isChecked() and self.upload.isEnabled() else FILE

    def _update(self, *_) -> None:
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        choice = self.choice()
        config = self.config()
        if choice == UPLOAD:
            ok.setText("Leverera")
            ok.setIcon(QIcon(str(ICONS / "export.svg")))
            ok.setEnabled(config is None or not config.is_production or self.understand.isChecked())
        elif choice == ARCHIVE:
            ok.setText("Skapa arkivpaket…")
            ok.setIcon(QIcon(str(ICONS / "archive.svg")))
            ok.setEnabled(True)
        else:
            ok.setText("Spara fil…")
            ok.setIcon(QIcon(str(ICONS / "file_json.svg")))
            ok.setEnabled(True)
        self.understand.setEnabled(choice == UPLOAD)

    def run(self) -> Optional[str]:
        """Gör det valda. Gick det stängs dialogen; avbröt man (till exempel filvalet) ligger den kvar."""
        action = {UPLOAD: self._deliver, ARCHIVE: self._archive, FILE: self._save}[self.choice()]
        text = action() if action is not None else None
        if text:
            self.result.setText(text)
            self.accept()
        return text

    # behålls för tester och för den som vill göra ett visst val direkt
    def save(self) -> Optional[str]:
        self.file.setChecked(True)
        return self.run()

    def deliver(self) -> Optional[str]:
        self.upload.setChecked(True)
        return self.run()

    def archive(self) -> Optional[str]:
        self.archive_radio.setChecked(True)
        return self.run()

    def _double_clicked(self, item: QListWidgetItem) -> None:
        problem = item.data(Qt.ItemDataRole.UserRole)
        if problem.layer and problem.fid is not None:
            self._show(problem.layer, problem.fid)
