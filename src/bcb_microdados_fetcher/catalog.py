"""Dataset catalog for bcb-microdados-fetcher."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ._catalog_base import DatasetEntry, GroupInfo, annual_datasets, monthly_datasets
from .constants import (
    BCB_BASE_URL,
    COSIF_SEGMENTOS,
    ESTBAN_PASTAS,
    SCR_START_YEAR,
    SCR_URL_TEMPLATE,
)

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


def _build_estban_entries() -> list[DatasetEntry]:
    """Build entries for ESTBAN (município e agência)."""
    current_year = dt.date.today().year
    entries: list[DatasetEntry] = []
    for slug, meta in ESTBAN_PASTAS.items():
        base_id = f"estban_{slug}"
        pasta = meta["pasta"]
        prefixo = meta["prefixo"]
        start_year = meta["start_year"]
        url_tmpl = f"{BCB_BASE_URL}/estban/{pasta}/{{year}}{{month}}_{prefixo}.csv.zip"
        name_tmpl = f"{meta['name']} ({{year}}-{{month}})"
        entries.extend(
            monthly_datasets(
                group="estban",
                base_id=base_id,
                name_template=name_tmpl,
                url_template=url_tmpl,
                start_year=start_year,
                end_year=current_year,
                ext="zip",
                extra={"pasta": pasta, "tipo": slug},
            )
        )
    return entries


def _build_cosif_entries() -> list[DatasetEntry]:
    """Build entries for COSIF (8 segmentos)."""
    current_year = dt.date.today().year
    entries: list[DatasetEntry] = []
    for slug, meta in COSIF_SEGMENTOS.items():
        base_id = f"cosif_{slug}"
        pasta = meta["pasta"]
        sufixo = meta["sufixo"]
        start_year = meta["start_year"]
        end_year = meta["end_year"] or current_year
        url_tmpl = f"{BCB_BASE_URL}/cosif/{pasta}/{{year}}{{month}}{sufixo}.csv.zip"
        name_tmpl = f"COSIF — {meta['name']} ({{year}}-{{month}})"
        entries.extend(
            monthly_datasets(
                group="cosif",
                base_id=base_id,
                name_template=name_tmpl,
                url_template=url_tmpl,
                start_year=start_year,
                end_year=end_year,
                ext="zip",
                extra={"pasta": pasta, "segmento": slug, "sufixo": sufixo},
            )
        )
    return entries


def _build_all_groups() -> dict[str, GroupInfo]:
    """Assemble all dataset groups."""
    return {
        "scr": GroupInfo(
            name="SCR.data — Carteira de Crédito Agregada",
            entries=_build_scr_entries(),
        ),
        "estban": GroupInfo(
            name="ESTBAN — Estatística Bancária Mensal",
            entries=_build_estban_entries(),
        ),
        "cosif": GroupInfo(
            name="COSIF — Balancetes e Balanços Patrimoniais",
            entries=_build_cosif_entries(),
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
    "estatistica_bancaria": "estban",
    "bancos": "cosif",
    "balancetes": "cosif",
    "balancos": "cosif",
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
