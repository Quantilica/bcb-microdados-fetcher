"""Dataset catalog for bcb-microdados-fetcher.

- **SCR.data**: não há listagem JSON; o catálogo itera os anos com HEAD (``/pda/desig/
  scrdata_{ano}.zip``) e só inclui os que existem. Se o HEAD for inconclusivo (rede),
  mantém o ano (aritmética) e conta o erro.
- **ESTBAN** e **COSIF**: os caminhos antigos (``/estban/...``, ``/cosif/...``) viraram
  a SPA do BCB (HTML), mas a listagem JSON interna segue respondendo
  (``conteudosite`` -> ``Documentos/byListGuid``). O catálogo usa sempre a ``Url`` da
  listagem, nunca monta o nome do arquivo.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from ._catalog_base import DatasetEntry, GroupInfo, annual_datasets
from .client import BcbMicrodadosClient
from .constants import (
    BCB_BASE_URL,
    COSIF_IDENTIFICADOR,
    COSIF_SEGMENTOS,
    ESTBAN_IDENTIFICADOR,
    ESTBAN_PASTAS,
    PIX_MUNICIPIO_URL_TEMPLATE,
    PIX_START,
    SCR_START_YEAR,
    SCR_SUBREGIAO_START,
    SCR_SUBREGIAO_URL_TEMPLATE,
    SCR_URL_TEMPLATE,
)

__all__ = [
    "DatasetEntry",
    "GroupInfo",
    "GROUPS",
    "GROUP_ALIASES",
    "DiscoveryReport",
    "discover",
    "list_datasets",
    "parse_documentos",
]

logger = logging.getLogger(__name__)


def _build_scr_entries(
    years: list[int] | None = None, *, end_year: int | None = None
) -> list[DatasetEntry]:
    """Build entries for SCR.data (annual ZIPs), opcionalmente só ``years``."""
    entries = annual_datasets(
        group="scr",
        base_id="scrdata",
        name_template="SCR.data — Carteira de Crédito ({year})",
        url_template=SCR_URL_TEMPLATE,
        start_year=SCR_START_YEAR,
        end_year=end_year or dt.date.today().year,
        ext="zip",
    )
    if years is not None:
        entries = [e for e in entries if e.year in set(years)]
    return entries


#: grupos mensais servidos por funções OData do Olinda (um JSON por mês).
OLINDA_GROUPS: dict[str, dict[str, Any]] = {
    "pix_municipio_transacoes": {
        "name": "Pix — Transações por Município (Olinda Pix_DadosAbertos)",
        "template": PIX_MUNICIPIO_URL_TEMPLATE,
        "start": PIX_START,
    },
    "scr_sub_regiao": {
        "name": "SCR por Sub-região (Olinda scr_sub_regiao)",
        "template": SCR_SUBREGIAO_URL_TEMPLATE,
        "start": SCR_SUBREGIAO_START,
    },
}


def _build_olinda_entries(
    group: str, *, today: dt.date | None = None
) -> list[DatasetEntry]:
    """Uma entrada por mês, do primeiro mês com dados até o mês corrente."""
    meta = OLINDA_GROUPS[group]
    today = today or dt.date.today()
    year, month = meta["start"]
    entries: list[DatasetEntry] = []
    while (year, month) <= (today.year, today.month):
        entries.append(
            DatasetEntry(
                id=f"{group}_{year}_{month:02d}",
                base_id=group,
                name=f"{meta['name']} ({year}-{month:02d})",
                url=meta["template"].format(ym=f"{year}{month:02d}"),
                ext="json",
                group=group,
                year=year,
                month=month,
                extra={"stable_name": True, "protocol": "olinda-function"},
            )
        )
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return entries


def _build_all_groups() -> dict[str, GroupInfo]:
    """Assemble all dataset groups (ESTBAN/COSIF só existem via descoberta)."""
    return {
        "scr": GroupInfo(
            name="SCR.data — Carteira de Crédito Agregada",
            entries=_build_scr_entries(),
        ),
        **{
            group: GroupInfo(name=meta["name"], entries=_build_olinda_entries(group))
            for group, meta in OLINDA_GROUPS.items()
        },
        "estban": GroupInfo(name="ESTBAN — Estatística Bancária Mensal", entries=[]),
        "cosif": GroupInfo(
            name="COSIF — Balancetes e Balanços Patrimoniais", entries=[]
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
    "pix": "pix_municipio_transacoes",
    "pix_municipio": "pix_municipio_transacoes",
    "scr_risco": "scr_sub_regiao",
}


# --------------------------------------------------------------------------- #
# Descoberta
# --------------------------------------------------------------------------- #

_PERIODO_NOME = re.compile(r"^(\d{4})(\d{2})")


@dataclass
class DiscoveryReport:
    """Resultado da descoberta: entradas por grupo e erros contados."""

    entries: dict[str, list[DatasetEntry]] = field(default_factory=dict)
    #: (grupo/pasta) cuja listagem falhou ou veio malformada.
    listing_errors: list[str] = field(default_factory=list)
    #: itens da listagem sem período identificável (nome e data ausentes).
    unparsed: list[str] = field(default_factory=list)
    #: (base_id, ano, mes) com mais de um arquivo; escolhido o canônico.
    duplicates: list[tuple[str, int, int]] = field(default_factory=list)
    #: anos de SCR em que o HEAD foi inconclusivo (mantidos por aritmética).
    scr_inconclusive: list[int] = field(default_factory=list)
    #: meses Olinda (pix, scr_sub_regiao) sem resposta conclusiva (mantidos).
    olinda_inconclusive: list[str] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return len(self.listing_errors) + len(self.unparsed)


def _periodo(item: dict[str, Any]) -> tuple[int, int] | None:
    m = _PERIODO_NOME.match(str(item.get("Nome") or ""))
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)), int(m.group(2))
    raw = str(item.get("DataDocumento") or "")[:7]
    m2 = re.match(r"^(\d{4})-(\d{2})$", raw)
    if m2:
        return int(m2.group(1)), int(m2.group(2))
    return None


def _ext(nome: str) -> str:
    return "csv" if nome.lower().endswith(".csv") else "zip"


def _is_canonical(nome: str) -> bool:
    # 2025-12 tem ``X.csv.zip`` e ``X.zip.csv.zip``: o segundo é artefato.
    return ".zip.csv" not in nome.lower()


def parse_documentos(
    items: list[dict[str, Any]],
    *,
    group: str,
    base_id: str,
    name_prefix: str,
    extra: dict[str, Any],
    report: DiscoveryReport,
) -> list[DatasetEntry]:
    """Converte a listagem JSON em entradas, deduplicando por período."""
    by_period: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for item in items:
        url = item.get("Url")
        if not url or not item.get("Nome"):
            continue  # pastas/linhas sem arquivo
        per = _periodo(item)
        if per is None:
            report.unparsed.append(f"{base_id}:{item.get('Nome')}")
            continue
        by_period.setdefault(per, []).append(item)

    entries: list[DatasetEntry] = []
    for (year, month), cands in sorted(by_period.items()):
        # mais recente primeiro; depois (estável) os canônicos na frente
        cands.sort(key=lambda i: str(i.get("DataPublicacao") or ""), reverse=True)
        cands.sort(key=lambda i: not _is_canonical(str(i["Nome"])))
        chosen, others = cands[0], cands[1:]
        if others:
            report.duplicates.append((base_id, year, month))
        nome = str(chosen["Nome"])
        url = str(chosen["Url"])
        entries.append(
            DatasetEntry(
                id=f"{base_id}_{year}_{month:02d}",
                base_id=base_id,
                name=f"{name_prefix} ({year}-{month:02d})",
                url=url if url.startswith("http") else f"{BCB_BASE_URL}{url}",
                ext=_ext(nome),
                group=group,
                year=year,
                month=month,
                extra={
                    **extra,
                    "arquivo": nome,
                    "tamanho": int(chosen.get("Tamanho") or 0),
                    "data_publicacao": chosen.get("DataPublicacao"),
                    "duplicatas": [str(o["Nome"]) for o in others],
                },
            )
        )
    return entries


def _discover_listing(
    api: BcbMicrodadosClient, identificador: str, report: DiscoveryReport
) -> tuple[str, str] | None:
    try:
        meta = api.get_conteudo_site(identificador)
        tronco, guid = meta["tronco"], meta["guidLista"]
    except Exception as exc:
        logger.warning("BCB: conteudosite(%s) falhou: %s", identificador, exc)
        report.listing_errors.append(f"conteudosite:{identificador}")
        return None
    return tronco, guid


def discover(
    client: BcbMicrodadosClient | None = None, *, scr: bool = True
) -> DiscoveryReport:
    """Monta o catálogo a partir da listagem real do BCB (ESTBAN, COSIF e SCR)."""
    api = client or BcbMicrodadosClient()
    report = DiscoveryReport(
        entries={"scr": [], "estban": [], "cosif": [], **{g: [] for g in OLINDA_GROUPS}}
    )

    plans: list[tuple[str, str, list[tuple[str, str, str, dict[str, Any]]]]] = [
        (
            "estban",
            ESTBAN_IDENTIFICADOR,
            [
                (
                    meta["pasta"],
                    f"estban_{slug}",
                    meta["name"],
                    {"pasta": meta["pasta"], "tipo": slug},
                )
                for slug, meta in ESTBAN_PASTAS.items()
            ],
        ),
        (
            "cosif",
            COSIF_IDENTIFICADOR,
            [
                (
                    meta["pasta"],
                    f"cosif_{slug}",
                    f"COSIF — {meta['name']}",
                    {
                        "pasta": meta["pasta"],
                        "segmento": slug,
                        "sufixo": meta["sufixo"],
                    },
                )
                for slug, meta in COSIF_SEGMENTOS.items()
            ],
        ),
    ]
    for group, ident, pastas in plans:
        loc = _discover_listing(api, ident, report)
        if loc is None:
            continue
        tronco, guid = loc
        for pasta, base_id, name, extra in pastas:
            try:
                items = api.list_documentos(tronco=tronco, guid_lista=guid, pasta=pasta)
            except Exception as exc:
                logger.warning("BCB: listagem %s/%s falhou: %s", group, pasta, exc)
                report.listing_errors.append(f"{group}/{pasta}")
                continue
            if not items:
                logger.warning("BCB: listagem %s/%s vazia", group, pasta)
                report.listing_errors.append(f"{group}/{pasta}:vazia")
                continue
            report.entries[group].extend(
                parse_documentos(
                    items,
                    group=group,
                    base_id=base_id,
                    name_prefix=name,
                    extra=extra,
                    report=report,
                )
            )

    if scr:
        # Sem listagem JSON para o SCR.data: HEAD ano a ano (inclui o ano seguinte,
        # que passa a existir quando o BCB publica o primeiro mês).
        years: list[int] = []
        for e in _build_scr_entries(end_year=dt.date.today().year + 1):
            ok = api.url_exists(e.url)
            if ok is None:
                report.scr_inconclusive.append(e.year or 0)
            if ok is not False:
                years.append(e.year or 0)
        report.entries["scr"] = _build_scr_entries(
            years, end_year=dt.date.today().year + 1
        )
    for group in OLINDA_GROUPS:
        report.entries[group] = _prune_unpublished(
            api, _build_olinda_entries(group), report
        )
    return report


def _prune_unpublished(
    api: BcbMicrodadosClient, entries: list[DatasetEntry], report: DiscoveryReport
) -> list[DatasetEntry]:
    """Tira do fim os meses que o Olinda ainda devolve vazios (não publicados).

    Olha no máximo 4 meses do fim; resposta inconclusiva mantém o mês (e o conta).
    """
    kept = list(entries)
    for _ in range(4):
        if not kept:
            break
        ok = api.has_rows(kept[-1].url)
        if ok is True:
            break
        if ok is None:
            report.olinda_inconclusive.append(kept[-1].id)
            break
        kept.pop()
    return kept


_REPORT: DiscoveryReport | None = None


def refresh_discovery(client: BcbMicrodadosClient | None = None) -> DiscoveryReport:
    """Executa a descoberta e passa a servir ``list_datasets`` com ela."""
    global _REPORT
    _REPORT = discover(client)
    return _REPORT


def last_discovery() -> DiscoveryReport | None:
    return _REPORT


def _discovery_enabled() -> bool:
    return os.environ.get("BCB_DISCOVER", "1") not in ("0", "false", "no")


def _group_entries(group: str) -> list[dict[str, Any]]:
    if _REPORT is not None and (
        group == "scr" or group in OLINDA_GROUPS or _REPORT.entries.get(group)
    ):
        return [e.to_dict() for e in _REPORT.entries.get(group, [])]
    return list(GROUPS[group]["entries"])


def list_datasets(group: str | None = None) -> list[dict[str, Any]]:
    """List datasets for a group or all groups."""
    if _REPORT is None and _discovery_enabled():
        refresh_discovery()
    if group is None:
        entries: list[dict[str, Any]] = []
        for g in GROUPS:
            entries.extend(_group_entries(g))
        return entries

    canon = GROUP_ALIASES.get(group, group)
    if canon not in GROUPS:
        raise ValueError(f"Grupo desconhecido: {group!r}")
    return _group_entries(canon)
