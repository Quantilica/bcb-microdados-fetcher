"""Dataset catalog for bcb-microdados-fetcher.

Apenas o SCR.data tem URL pública estável. Os endpoints históricos de ESTBAN e
COSIF (`/estban/<pasta>/...`, `/cosif/<pasta>/...`) passaram a devolver a página
HTML da SPA do BCB; os grupos foram removidos até que o novo canal seja
identificado (ver plano `2026-11-02-inclusao-fontes-novembro-crons-fetchers`).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from ._catalog_base import DatasetEntry, GroupInfo, annual_datasets
from .constants import SCR_START_YEAR, SCR_URL_TEMPLATE

__all__ = [
    "DatasetEntry",
    "GroupInfo",
    "GROUPS",
    "GROUP_ALIASES",
    "list_datasets",
]


def _build_scr_entries() -> list[DatasetEntry]:
    """Build entries for SCR.data (annual ZIPs)."""
    current_year = dt.date.today().year
    return annual_datasets(
        group="scr",
        base_id="scrdata",
        name_template="SCR.data — Carteira de Crédito ({year})",
        url_template=SCR_URL_TEMPLATE,
        start_year=SCR_START_YEAR,
        end_year=current_year,
        ext="zip",
    )


def _build_all_groups() -> dict[str, GroupInfo]:
    """Assemble all dataset groups."""
    return {
        "scr": GroupInfo(
            name="SCR.data — Carteira de Crédito Agregada",
            entries=_build_scr_entries(),
        ),
    }


_GROUPS_MAP = _build_all_groups()

GROUPS: dict[str, dict[str, Any]] = {
    grp: info.to_dict() for grp, info in _GROUPS_MAP.items()
}

GROUP_ALIASES: dict[str, str] = {
    "padrao": "scr",
    "credito": "scr",
    "scr_data": "scr",
}


def list_datasets(group: str | None = None) -> list[dict[str, Any]]:
    """List datasets for a group or all groups."""
    if group is None:
        entries: list[dict[str, Any]] = []
        for g_data in GROUPS.values():
            entries.extend(g_data["entries"])
        return entries

    canon = GROUP_ALIASES.get(group, group)
    if canon not in GROUPS:
        raise ValueError(f"Grupo desconhecido: {group!r}")
    return list(GROUPS[canon]["entries"])
