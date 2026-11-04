"""Descoberta ESTBAN/COSIF/SCR por listagem JSON gravada (03/11/2026)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from quantilica.core.http import HttpStatusError

from bcb_microdados_fetcher import catalog
from bcb_microdados_fetcher.client import BcbMicrodadosClient

FIX = Path(__file__).parent / "fixtures" / "listagens"


class FakeHttp:
    """Serve as respostas JSON gravadas e simula HEAD dos ZIPs do SCR."""

    def __init__(
        self,
        *,
        scr_years: set[int] | None = None,
        head_fail: bool = False,
        no_conteudo: set[str] | None = None,
    ) -> None:
        self.scr_years = scr_years if scr_years is not None else set(range(2012, 2027))
        self.head_fail = head_fail
        self.no_conteudo = no_conteudo or set()
        self.heads: list[str] = []

    def get_json(self, url: str, params: dict | None = None):
        params = params or {}
        if url.endswith("conteudosite"):
            ident = params["identificador"]
            if ident in self.no_conteudo:
                raise HttpStatusError(url, 503)
            name = "conteudo_cosif" if ident == "cosif" else "conteudo_estban"
            return json.loads((FIX / f"{name}.json").read_text())
        f = FIX / f"docs_{params['pasta']}.json"
        if not f.exists():
            raise HttpStatusError(url, 404)
        return json.loads(f.read_text())

    def head_or_get(self, url: str):
        self.heads.append(url)
        if self.head_fail:
            raise RuntimeError("timeout")
        year = int(url.rsplit("_", 1)[1][:4])
        if year not in self.scr_years:
            raise HttpStatusError(url, 404)
        return object()


def _api(**kw) -> BcbMicrodadosClient:
    return BcbMicrodadosClient(client=FakeHttp(**kw))  # type: ignore[arg-type]


def test_estban_restaurado_pela_listagem() -> None:
    rep = catalog.discover(_api())
    by_id = {e.id: e for e in rep.entries["estban"]}
    e = by_id["estban_municipio_2026_06"]
    assert e.url == (
        "https://www.bcb.gov.br/content/estatisticas/estatistica_bancaria_estban/"
        "municipio/202606_ESTBAN.csv.zip"
    )
    assert (e.year, e.month, e.ext, e.group) == (2026, 6, "zip", "estban")
    assert e.extra and e.extra["tamanho"] == 883348
    # extensões irregulares: .csv puro em 2023-01, .ZIP em 2022-12
    assert by_id["estban_municipio_2023_01"].ext == "csv"
    assert by_id["estban_municipio_2022_12"].ext == "zip"
    assert "estban_agencia_1988_07" in by_id
    # a linha sem arquivo (pasta) é ignorada e não conta como erro
    assert rep.unparsed == []


def test_cosif_deduplica_2025_12() -> None:
    rep = catalog.discover(_api())
    by_id = {e.id: e for e in rep.entries["cosif"]}
    e = by_id["cosif_bancos_2025_12"]
    assert e.url.endswith("/cosif/Bancos/202512BANCOS.csv.zip")
    assert e.extra and e.extra["duplicatas"] == ["202512BANCOS.zip.csv.zip"]
    assert ("cosif_bancos", 2025, 12) in rep.duplicates
    assert "cosif_combinados_2013_06" in by_id


def test_pasta_ausente_e_erro_contado_sem_derrubar_o_resto() -> None:
    rep = catalog.discover(_api())
    # só Bancos e Combinados têm fixture; as outras 6 pastas contam erro
    assert "cosif/Cooperativas-de-credito" in rep.listing_errors
    assert rep.errors == len(rep.listing_errors) + len(rep.unparsed) >= 6
    assert rep.entries["cosif"] and rep.entries["estban"]


def test_conteudosite_indisponivel_zera_o_grupo_e_conta() -> None:
    rep = catalog.discover(_api(no_conteudo={"cosif"}))
    assert rep.entries["cosif"] == []
    assert "conteudosite:cosif" in rep.listing_errors
    assert rep.entries["estban"]


def test_scr_dirigido_por_head() -> None:
    rep = catalog.discover(_api(scr_years=set(range(2013, 2026))))
    anos = [e.year for e in rep.entries["scr"]]
    assert anos == list(range(2013, 2026))  # 2012 e 2026 (404) ficam de fora


def test_scr_inclui_ano_seguinte_quando_publicado() -> None:
    prox = dt.date.today().year + 1
    rep = catalog.discover(_api(scr_years=set(range(2012, prox + 1))))
    assert rep.entries["scr"][-1].year == prox


def test_scr_head_inconclusivo_mantem_anos_e_conta() -> None:
    rep = catalog.discover(_api(head_fail=True))
    anos = [e.year for e in rep.entries["scr"]]
    assert 2012 in anos and dt.date.today().year in anos
    assert rep.scr_inconclusive


def test_list_datasets_serve_descoberta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "_REPORT", catalog.discover(_api()))
    ids = {e["id"] for e in catalog.list_datasets("estban")}
    assert "estban_agencia_2026_06" in ids
    assert {e["group"] for e in catalog.list_datasets()} == {"scr", "estban", "cosif"}
    monkeypatch.setattr(catalog, "_REPORT", None)
    assert catalog.list_datasets("estban") == []  # BCB_DISCOVER=0: sem rede
    assert catalog.list_datasets("scr")  # aritmética de fallback
