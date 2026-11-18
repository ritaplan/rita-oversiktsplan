"""Pluginets inställningar (sparas i QGIS användarprofil): leveransen till NGP. Från Rita Detaljplan, med egna
nycklar så att de två pluginen inte delar inställningar av misstag."""
from __future__ import annotations

from qgis.core import QgsApplication, QgsSettings

KEY_NGP = "rita_oversiktsplan/ngp/"


def _environment_name(value) -> str:
    """Miljön som ett av de kända namnen ("ver", "prod"), annars "egen" (en tidigare inställning med egen adress)."""
    from . import ngp_client as ngp
    text = str(value)
    return text if text in ngp.ENVIRONMENTS else "egen"


def active_ngp_environment() -> str:
    """Miljön leveransen går till ("ver", "prod" eller "egen")."""
    return _environment_name(QgsSettings().value(KEY_NGP + "environment", "ver"))


def ngp_environment_config(environment: str):
    """Adresser och nyckel för en miljö. Varje miljö har egna inställningar. Inställningar som sparats före uppdelningen
    (en enda uppsättning för den miljö som var vald) gäller fortfarande för den miljön tills man sparar på nytt."""
    from . import ngp_client as ngp
    store = QgsSettings()
    defaults = ngp.ENVIRONMENTS.get(environment)
    legacy_here = active_ngp_environment() == environment

    def read(name: str, default: str = "") -> str:
        value = store.value(f"{KEY_NGP}{environment}/{name}")
        if value is None and legacy_here:
            value = store.value(KEY_NGP + name)
        return default if value is None else str(value or "")

    return ngp.NgpConfig(environment=environment,
                         base_url=read("base_url", defaults.base_url if defaults else ""),
                         token_url=read("token_url", defaults.token_url if defaults else ""),
                         authcfg=read("authcfg"))


def ngp_config():
    """Inställningarna för leverans till NGP: den miljö leveransen går till, med dess adresser och autentiseringskonfiguration."""
    return ngp_environment_config(active_ngp_environment())


def set_ngp_config(config) -> None:
    """Sparar inställningarna för en miljö (config.environment). Miljön som leveransen går till ändras med ``set_ngp_active``."""
    store = QgsSettings()
    prefix = f"{KEY_NGP}{config.environment}/"
    store.setValue(prefix + "base_url", config.base_url.strip())
    store.setValue(prefix + "token_url", config.token_url.strip())
    store.setValue(prefix + "authcfg", config.authcfg)
    if QgsSettings().value(KEY_NGP + "environment") is None:  # första sparningen: den miljön blir den aktiva
        store.setValue(KEY_NGP + "environment", config.environment)


def set_ngp_active(environment: str) -> None:
    QgsSettings().setValue(KEY_NGP + "environment", environment)


def auth_configs() -> list[tuple[str, str]]:
    """QGIS autentiseringskonfigurationer som (id, namn). Tom lista om autentiseringsdatabasen inte kan läsas."""
    try:
        configs = QgsApplication.authManager().availableAuthMethodConfigs()
        return sorted(((cid, cfg.name()) for cid, cfg in configs.items()), key=lambda item: item[1].lower())
    except Exception:  # noqa: BLE001 - till exempel låst databas
        return []
