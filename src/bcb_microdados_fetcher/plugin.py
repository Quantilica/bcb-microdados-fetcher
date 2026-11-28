"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

import typer
from quantilica.cli.sdk import CheckPlan, CheckPlanItem, FetcherApp, make_resolve_groups
from quantilica.core.registry import FetcherInfo
from quantilica.core.sync import FreshnessPolicy

from .catalog import GROUP_ALIASES, GROUPS, group_failures, list_datasets
from .geracao import manter_geracao_vigente, versao_vigente_anterior
from .storage import DataRepository

logger = logging.getLogger(__name__)

#: motivo (``skip-up-to-date``) do ``check`` para a geração já descartada.
MOTIVO_GERACAO_DESCARTADA = "geracao-descartada"

resolve_groups = make_resolve_groups(
    GROUPS, {alias: [canon] for alias, canon in GROUP_ALIASES.items()}
)


def path_builder(
    output_dir: Path, entry: dict[str, Any], last_modified: dt.date | None
) -> Path:
    """Build local storage path for a dataset entry."""
    return DataRepository(output_dir).path_for_entry(entry, last_modified=last_modified)


class BcbMicrodadosApp(FetcherApp):
    """``FetcherApp`` do BCB.

    - Descarta download com data de geração anterior à da versão vigente.
    - Faz a falha de descoberta de um grupo pedido (listagem do ESTBAN ou do COSIF
      fora do ar, ``identificador`` mudado, formato novo) contar como erro do
      ``sync``: sem isso o grupo ficava sem arquivo e a saída era 0.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        #: grupo -> falhas de descoberta vistas ao listar os grupos pedidos.
        self._falhas_descoberta: dict[str, list[str]] = {}
        self.list_datasets = self.listar_grupo

    def listar_grupo(self, group: str) -> list[dict[str, Any]]:
        """``list_datasets`` que anota as falhas de descoberta do grupo pedido."""
        entries = list_datasets(group)
        falhas = group_failures(group)
        canon = GROUP_ALIASES.get(group, group)
        if falhas:
            self._falhas_descoberta[canon] = falhas
            for falha in falhas:
                logger.error("BCB: descoberta do grupo %s falhou: %s", canon, falha)
        else:
            self._falhas_descoberta.pop(canon, None)
        return entries

    def check_datasets(
        self,
        entries: list[dict[str, Any]],
        output_dir: Path,
        workers: int = 4,
    ) -> CheckPlan:
        """Verifica o frescor; com falha de descoberta num grupo pedido, sai 1.

        Na coleta em modo de plano o ``check`` e o ``sync --from-plan`` são
        processos separados, e o segundo não lista grupo: a falha de descoberta só
        chega ao código de saída se o ``check`` falhar. Sem plano gravado, quem
        opera cai no ``sync`` completo, que conta ``descoberta:<grupo>`` e sai 3 ou 1.
        """
        falhas, self._falhas_descoberta = self._falhas_descoberta, {}
        if falhas:
            for grupo, causas in sorted(falhas.items()):
                logger.error(
                    "BCB: check abortado, descoberta do grupo %s falhou: %s",
                    grupo,
                    "; ".join(causas),
                )
            raise typer.Exit(1)
        return super().check_datasets(entries, output_dir, workers)

    def check_entry(self, entry: dict[str, Any], output_dir: Path) -> CheckPlanItem:
        """Veredito do host, com o motivo ``geracao-descartada`` quando cabe.

        Se o arquivo do carimbo não existe, o sidecar dá o frescor por em dia
        (``manifest-fresh``) e há uma versão anterior do mesmo arquivo, o download
        daquela geração foi descartado por ser mais velho que a vigente. O motivo
        diz isso ao plano: quem reclassifica o plano por histórico pode mantê-lo
        como ``skip``; quem não o conhece o trata como qualquer
        ``skip-up-to-date``.
        """
        item = super().check_entry(entry, output_dir)
        if item.action != "skip-up-to-date" or item.reason != "manifest-fresh":
            return item
        local = Path(item.local_path)
        if local.exists() or versao_vigente_anterior(local) is None:
            return item
        return replace(item, reason=MOTIVO_GERACAO_DESCARTADA)

    def download_datasets(
        self,
        entries: list[dict[str, Any]],
        output_dir: Path,
        workers: int = 4,
        *,
        force: bool = False,
    ) -> tuple[int, int, list[tuple[str, str]]]:
        """Baixa as entradas e soma, aos erros, as falhas de descoberta pendentes.

        Cada grupo com falha de descoberta entra como um erro ``descoberta:<grupo>``
        com as causas: o ``sync`` sai 3 (algo baixou) ou 1 (nada baixou) e o
        ``--summary-json`` traz o grupo e a causa.
        """
        falhas, self._falhas_descoberta = self._falhas_descoberta, {}
        downloaded, total, errors = super().download_datasets(
            entries, output_dir, workers, force=force
        )
        erros_descoberta = [
            (f"descoberta:{grupo}", "; ".join(causas))
            for grupo, causas in sorted(falhas.items())
        ]
        return downloaded, total + len(erros_descoberta), errors + erros_descoberta

    def _download_file(self, url: str, output: Path, *args: Any, **kwargs: Any) -> Path:
        saved = super()._download_file(url, output, *args, **kwargs)
        return manter_geracao_vigente(Path(saved))


fetcher = BcbMicrodadosApp(
    name="bcb-microdados",
    help="Microdados do Banco Central (SCR, ESTBAN, COSIF)",
    info=FetcherInfo(
        id="bcb-microdados",
        nome="Banco Central - Microdados (SCR, ESTBAN, COSIF, Pix)",
        aliases=("bcb_microdados",),
        orgao="Banco Central do Brasil (BCB)",
        licenca="Open Data Commons Open Database License (ODbL)",
        homepage="https://dadosabertos.bcb.gov.br/",
        cadencia="monthly",
        dominio="financas",
    ),
    groups_dict=GROUPS,
    aliases_dict=GROUP_ALIASES,
    list_datasets=list_datasets,
    path_builder=path_builder,
    default_output=Path("/data/bcb-microdados"),
    freshness_policy=FreshnessPolicy.HEAD_FALLBACK_GET,
)


def convert(
    input_dir: Path,
    lake_dir: Path,
    *,
    dataset: list[str] | None = None,
    force: bool = False,
) -> Any:
    """Converte arquivos brutos de bcb-microdados para o lake Hive (Parquet)."""
    try:
        from bcb_microdados_fetcher import lake
    except ImportError as exc:
        raise RuntimeError(
            "Conversão para o lake requer o extra 'analysis'. "
            "Instale com: quantilica install bcb-microdados --extra analysis"
        ) from exc
    return lake.converter.convert(input_dir, lake_dir, datasets=dataset, force=force)


fetcher.command_convert(convert)
fetcher.command_pipeline(convert)


app = fetcher.app
