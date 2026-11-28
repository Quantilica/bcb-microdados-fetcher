"""Descoberta ESTBAN/COSIF/SCR por listagem JSON gravada (03/11/2026)."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest
from quantilica.core.http import HttpStatusError

from bcb_microdados_fetcher import catalog
from bcb_microdados_fetcher.client import BcbMicrodadosClient
from bcb_microdados_fetcher.constants import ESTBAN_IDENTIFICADOR

FIX = Path(__file__).parent / "fixtures" / "listagens"


class FakeHttp:
    """Serve as respostas JSON gravadas e simula HEAD dos ZIPs do SCR."""

    def __init__(
        self,
        *,
        scr_years: set[int] | None = None,
        head_fail: bool = False,
        no_conteudo: set[str] | None = None,
        olinda_last: int | None = None,
        olinda_fail: bool = False,
    ) -> None:
        # último mês (AAAAMM) com linhas nas funções do Olinda; padrão: mês anterior
        today = dt.date.today()
        prev = dt.date(today.year, today.month, 1) - dt.timedelta(days=1)
        self.olinda_last = olinda_last or prev.year * 100 + prev.month
        self.olinda_fail = olinda_fail
        self.olinda_calls: list[str] = []
        self.scr_years = scr_years if scr_years is not None else set(range(2012, 2027))
        self.head_fail = head_fail
        self.no_conteudo = no_conteudo or set()
        self.heads: list[str] = []

    def get_json(self, url: str, params: dict | None = None):
        params = params or {}
        if "olinda.bcb.gov.br" in url:
            self.olinda_calls.append(url)
            if self.olinda_fail:
                raise HttpStatusError(url, 500)
            ym = int(re.search(r"@DataBase=(?:%27)?(\d{6})", url).group(1))
            return {"value": [{"AnoMes": ym}] if ym <= self.olinda_last else []}
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
    assert {e["group"] for e in catalog.list_datasets()} == {
        "scr",
        "estban",
        "cosif",
        "pix_municipio_transacoes",
        "scr_sub_regiao",
    }
    monkeypatch.setattr(catalog, "_REPORT", None)
    assert catalog.list_datasets("estban") == []  # BCB_DISCOVER=0: sem rede
    assert catalog.list_datasets("scr")  # aritmética de fallback


def test_olinda_meses_nao_publicados_saem_do_fim() -> None:
    today = dt.date.today()
    fake_last = 202509
    rep = catalog.discover(_api(olinda_last=fake_last))
    pix = rep.entries["pix_municipio_transacoes"]
    assert (pix[0].year, pix[0].month) == (2020, 11)
    # só olha os 4 últimos meses; o resto do intervalo fica pela aritmética
    months_to_today = (today.year - 2025) * 12 + today.month - 9
    if months_to_today <= 4:
        assert (pix[-1].year, pix[-1].month) == (2025, 9)
    assert all(e.url.startswith("https://olinda.bcb.gov.br/") for e in pix)
    assert rep.olinda_inconclusive == []


def test_olinda_sondagem_usa_top_1() -> None:
    api = _api()
    catalog.discover(api)
    probes = api.client.olinda_calls  # type: ignore[attr-defined]
    assert probes and all("$top=1&" in u for u in probes)


def test_olinda_inconclusivo_mantem_o_mes_e_conta() -> None:
    rep = catalog.discover(_api(olinda_fail=True))
    assert rep.entries["scr_sub_regiao"][-1].month == dt.date.today().month
    assert sorted(set(i.rsplit("_", 2)[0] for i in rep.olinda_inconclusive)) == [
        "pix_municipio_transacoes",
        "scr_sub_regiao",
    ]


# --------------------------------------------------------------------------- #
# Falha de listagem x fonte sem arquivo (ESTBAN e COSIF)
# --------------------------------------------------------------------------- #


class _FakeListagem(FakeHttp):
    """FakeHttp com as respostas da listagem trocáveis pelo teste."""

    def __init__(
        self,
        *,
        vazias: set[str] | None = None,
        todas_vazias: bool = False,
        docs: dict[str, list[dict]] | None = None,
        conteudo: dict | None = None,
        **kw,
    ) -> None:
        super().__init__(**kw)
        self.vazias = vazias or set()
        self.todas_vazias = todas_vazias
        self.docs = docs or {}
        self.conteudo = conteudo

    def get_json(self, url: str, params: dict | None = None):
        params = params or {}
        if url.endswith("conteudosite") and self.conteudo is not None:
            return self.conteudo
        if "olinda.bcb.gov.br" not in url and not url.endswith("conteudosite"):
            pasta = params["pasta"]
            if pasta in self.docs:
                return {"conteudo": self.docs[pasta]}
            if self.todas_vazias or pasta in self.vazias:
                return {"conteudo": []}
            if not (FIX / f"docs_{pasta}.json").exists():
                return {"conteudo": []}  # pasta sem fixture: a fonte não tem arquivo
        return super().get_json(url, params)


def _api_listagem(**kw) -> BcbMicrodadosClient:
    return BcbMicrodadosClient(client=_FakeListagem(**kw))  # type: ignore[arg-type]


def test_listagem_saudavel_nao_tem_falha() -> None:
    rep = catalog.discover(_api_listagem())
    assert rep.failures == []
    assert rep.group_failures("estban") == rep.group_failures("cosif") == []


def test_pasta_vazia_valida_nao_e_falha() -> None:
    """Resposta válida sem item: a fonte não tem arquivo ali; aviso, não erro."""
    rep = catalog.discover(_api_listagem())
    # 6 das 8 pastas do COSIF não têm fixture e respondem lista vazia
    assert "cosif/Cooperativas-de-credito" in rep.empty_folders
    assert len(rep.empty_folders) == 6
    assert "cosif/Cooperativas-de-credito" not in rep.listing_errors
    assert rep.group_failures("cosif") == []
    assert rep.entries["cosif"]  # as pastas com arquivo seguem


def test_conteudosite_fora_do_ar_e_falha_com_a_causa() -> None:
    rep = catalog.discover(_api_listagem(no_conteudo={ESTBAN_IDENTIFICADOR}))
    assert rep.entries["estban"] == []
    (falha,) = rep.group_failures("estban")
    assert falha.startswith(f"conteudosite:{ESTBAN_IDENTIFICADOR}: ")
    assert "503" in falha
    assert rep.group_failures("cosif") == []  # o outro grupo não é afetado


def test_identificador_mudado_e_falha() -> None:
    """A resposta é JSON válido, mas sem ``tronco``/``guidLista``."""
    rep = catalog.discover(_api_listagem(conteudo={"conteudo": []}))
    for grupo, ident in (("estban", ESTBAN_IDENTIFICADOR), ("cosif", "cosif")):
        (falha,) = rep.group_failures(grupo)
        assert falha.startswith(f"conteudosite:{ident}: KeyError")
        assert rep.entries[grupo] == []


def test_listagem_de_pasta_com_erro_http_e_falha() -> None:
    rep = catalog.discover(_api())  # sem fixture de 6 pastas do COSIF: 404
    falhas = rep.group_failures("cosif")
    assert len(falhas) == 6
    assert any(f.startswith("cosif/Cooperativas-de-credito: ") for f in falhas)
    assert "404" in falhas[0]
    assert rep.group_failures("estban") == []


def test_formato_novo_sem_periodo_identificavel_e_falha() -> None:
    itens = [
        {"Nome": "relatorio-final.csv", "Url": "https://bcb/x.csv"},
        {"Nome": "outro.csv", "Url": "https://bcb/y.csv", "DataDocumento": "?"},
    ]
    rep = catalog.discover(_api_listagem(docs={"municipio": itens}))
    (falha,) = rep.group_failures("estban")
    assert falha.startswith("estban/municipio: 2 item(ns) sem período identificável")
    assert rep.entries["estban"]  # a pasta "agencia" segue
    assert rep.unparsed == [
        "estban_municipio:relatorio-final.csv",
        "estban_municipio:outro.csv",
    ]


def test_grupo_inteiro_sem_arquivo_e_falha() -> None:
    """Todas as pastas respondem vazio: o grupo não pode sumir sem erro."""
    rep = catalog.discover(_api_listagem(todas_vazias=True))
    for grupo in ("estban", "cosif"):
        (falha,) = rep.group_failures(grupo)
        assert falha.startswith(f"{grupo}: a listagem respondeu, mas nenhuma das ")
        assert rep.entries[grupo] == []


def test_group_failures_sem_descoberta_so_vale_para_estban_e_cosif(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(catalog, "_REPORT", None)  # BCB_DISCOVER=0 nos testes
    for grupo in ("estban", "cosif", "estatistica_bancaria", "bancos"):
        (falha,) = catalog.group_failures(grupo)
        assert "descoberta desligada" in falha
    assert catalog.group_failures("scr") == []
    assert catalog.group_failures("pix") == []


def test_group_failures_serve_a_descoberta_com_apelido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        catalog, "_REPORT", catalog.discover(_api_listagem(no_conteudo={"cosif"}))
    )
    assert catalog.group_failures("cosif") == catalog.group_failures("balancetes")
    assert catalog.group_failures("cosif")
    assert catalog.group_failures("estban") == []
