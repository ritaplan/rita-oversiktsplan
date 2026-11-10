"""Exportera en plan ur databasen som en leverans i Lantmäteriets JSON-format (se ``core.export_lm``), för
databashanteraren, utan att öppna planen i projektet: planen kopieras till en tillfällig GeoPackage (se
``core.transfer.export_plan``), läses in i ett eget, fristående projekt och exporteras som vid *Leverans och export*. Det
ändrar inget i databasen eller i det öppna projektet.

Leveransen kan ha anmärkningar (fel och varningar) som kontrollen i *Leverans och export* visar; här skrivs den som den är."""
from __future__ import annotations

import gc
import tempfile
from pathlib import Path

from qgis.core import QgsProject

from .core import export_lm, transfer
from .core.project import PlanError, active_plan_group, load_plan
from .core.storage import PostgisStorage
from .core.transfer import TransferError


def export_delivery(plan: PostgisStorage, path: Path) -> Path:
    """Sparar planen som en leverans (JSON) på ``path``. Kastar ``TransferError`` om filen redan finns eller något går
    fel."""
    path = Path(path)
    if path.exists():
        raise TransferError(f"{path.name} finns redan.")
    text, message = "", ""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        gpkg = transfer.export_plan(plan, Path(folder) / "plan.gpkg")
        project = QgsProject()  # fristående: rör inte användarens öppna projekt
        try:
            load_plan(gpkg, project)
            collection, _problems = export_lm.export(active_plan_group(project))
            text = export_lm.dumps(collection)
        except (PlanError, ValueError, RuntimeError) as exc:
            message = f"Kunde inte exportera planen {plan.plan_id}: {exc}"
        finally:
            project.clear()
            del project
            gc.collect()  # lagren släpper filen, annars går den inte att ta bort på Windows
    if message:
        raise TransferError(message)
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise TransferError(f"Kunde inte skriva {path.name}: {exc}") from exc
    return path
