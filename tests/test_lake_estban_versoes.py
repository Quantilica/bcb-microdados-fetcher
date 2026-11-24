"""ESTBAN: troca de formato do bruto entre versões e membro sem linhas.

O BCB republicou meses antigos do ESTBAN: o CSV solto (``x@2023.csv``) virou ZIP
(``x@2026.zip``) com o mesmo conteúdo, e um mês veio só com o cabeçalho. A chave do
Parquet muda com o formato (``x`` -> ``x__x_csv``), e o Parquet da versão anterior
ficava ao lado do novo (``versao_duplicada``, ``origem_superada``).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import duckdb
import polars as pl
import pytest
from quantilica.analytics.lake import check_dataset
from quantilica.analytics.lake_audit import lake_audit

import bcb_microdados_fetcher.lake as lake_mod
from bcb_microdados_fetcher.lake import converter

SOURCE = "bcb-microdados"

_CAB_AG = (
    "ESTBAN (Documento 4500) por agencia\n"
    "Data de geracao dos dados: 2023-10-16\n"
    "#DATA_BASE;UF;CODMUN;MUNICIPIO;CNPJ;NOME_INSTITUICAO;AGENCIA;CODMUN_IBGE;"
    "VERBETE_110_DISPONIBILIDADES;VERBETE_111_CAIXA\n"
)
_LINHA_AG = "202212;SP;7388;SAO PAULO;00000000;BANCO DO BRASIL;'0001;3550308;50;7\n"
_CAB_MUN = (
    "ESTBAN (Documento 4500) por municipio\n"
    "Data de geracao dos dados: 2023-10-16\n"
    "#DATA_BASE;UF;CODMUN;MUNICIPIO;CNPJ;NOME_INSTITUICAO;AGEN_ESPERADAS;"
    "AGEN_PROCESSADAS;VERBETE_110_DISPONIBILIDADES;VERBETE_111_CAIXA\n"
)
_LINHA_MUN = "202212;SP;7388;SAO PAULO;00000000;BANCO DO BRASIL;3;2;50;7\n"


def _csv(com_linhas: bool = True, *, municipio: bool = False) -> bytes:
    cab, linha = (_CAB_MUN, _LINHA_MUN) if municipio else (_CAB_AG, _LINHA_AG)
    return (cab + (linha if com_linhas else "")).encode("latin-1")


def _fontes(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(raiz do bruto, pasta estban, lake)``: ``raw/bcb-microdados/estban``.

    A auditoria lê ``<fonte>/<pasta>/arquivo``: com o bruto fora de
    ``bcb-microdados`` ela não vê nada e o teste passaria à toa.
    """
    raiz = tmp_path / "raw"
    estban = raiz / SOURCE / "estban"
    estban.mkdir(parents=True)
    lake = tmp_path / "lake"
    lake.mkdir()
    return raiz, estban, lake


def _csv_solto(raw: Path, carimbo: str, **kw) -> Path:
    path = raw / f"estban_agencia_2022-12@{carimbo}.csv"
    path.write_bytes(_csv(**kw))
    return path


def _zip(
    raw: Path,
    carimbo: str,
    *,
    nome: str = "estban_agencia_2022-12",
    membro: str = "202212_ESTBAN_AG.CSV",
    **kw,
) -> Path:
    path = raw / f"{nome}@{carimbo}.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(membro, _csv(**kw))
    return path


def _parquets(lake: Path, dataset: str = "estban_agencia") -> list[str]:
    ds = lake / SOURCE / dataset
    return sorted(p.name for p in ds.rglob("*.parquet"))


def _achados(lake: Path, raiz: Path) -> dict[str, int]:
    report = lake_audit(
        lake,
        input_dir=raiz,
        sources=[SOURCE],
        readers=False,
        integrity=False,
        converters={SOURCE: converter},
    )
    assert report.counts["expected_files"] > 0, "a auditoria não viu o bruto"
    # Sem _build.json o relatório traz também os achados de manifesto; só interessam
    # os de procedência, duplicidade e cobertura.
    return {
        k: v
        for k, v in report.by_category().items()
        if k in {"origem_superada", "versao_duplicada", "sem_parquet"}
    }


def test_csv_solto_que_vira_zip_substitui_o_parquet_antigo(tmp_path: Path) -> None:
    raiz, estban, lake = _fontes(tmp_path)
    _csv_solto(estban, "20230807")
    res = converter.convert(raiz, lake)
    assert (res.converted, res.errors) == (1, [])
    assert _parquets(lake) == ["estban_agencia_2022-12.parquet"]
    assert _achados(lake, raiz) == {}

    # O BCB republica o mesmo mês como ZIP: o CSV antigo deixa de ser o vigente.
    _zip(estban, "20261123")
    res = converter.convert(raiz, lake)
    assert (res.converted, res.errors) == (1, [])
    assert _parquets(lake) == ["estban_agencia_2022-12__202212_estban_ag.parquet"]
    ds = lake / SOURCE / "estban_agencia"
    assert not check_dataset(ds)
    assert pl.read_parquet(next(ds.rglob("*.parquet"))).height == 2
    assert _achados(lake, raiz) == {}

    # Reexecutar não muda nada nem recria o antigo.
    res = converter.convert(raiz, lake)
    assert (res.converted, res.skipped) == (0, 1)
    assert _parquets(lake) == ["estban_agencia_2022-12__202212_estban_ag.parquet"]


def test_a_auditoria_do_teste_acusa_a_duplicata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova de que ``_achados`` enxerga o defeito: sem a limpeza, acusa."""
    raiz, estban, lake = _fontes(tmp_path)
    _csv_solto(estban, "20230807")
    converter.convert(raiz, lake)
    monkeypatch.setattr(lake_mod, "_drop_superseded", lambda *a, **k: [])
    _zip(estban, "20261123")
    converter.convert(raiz, lake)
    assert len(_parquets(lake)) == 2
    achados = _achados(lake, raiz)
    assert achados.get("versao_duplicada") == 1
    assert achados.get("origem_superada") == 1


def test_reexecucao_limpa_o_que_a_execucao_anterior_deixou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CSV convertido, ZIP convertido sem limpeza, reexecução limpa."""
    raiz, estban, lake = _fontes(tmp_path)
    _csv_solto(estban, "20230807")
    converter.convert(raiz, lake)
    with monkeypatch.context() as mp:
        mp.setattr(lake_mod, "_drop_superseded", lambda *a, **k: [])
        _zip(estban, "20261123")
        converter.convert(raiz, lake)
    assert len(_parquets(lake)) == 2  # a execução interrompida deixou os dois

    res = converter.convert(raiz, lake)
    assert (res.converted, res.skipped, res.errors) == (0, 1, [])
    assert _parquets(lake) == ["estban_agencia_2022-12__202212_estban_ag.parquet"]
    assert _achados(lake, raiz) == {}


def test_membro_com_erro_impede_a_limpeza_do_bruto(tmp_path: Path) -> None:
    """Só depois de todos os membros do bruto no lake, sem erro."""
    raiz, estban, lake = _fontes(tmp_path)
    _csv_solto(estban, "20230807")
    converter.convert(raiz, lake)
    antigo = _parquets(lake)

    path = estban / "estban_agencia_2022-12@20261123.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("202212_ESTBAN_AG.CSV", _csv())
        zf.writestr("202212_ESTBAN_AG_2.CSV", b"")  # membro ilegível: erro
    res = converter.convert(raiz, lake)
    assert len(res.errors) == 1
    assert set(antigo) <= set(_parquets(lake))  # o Parquet anterior não foi apagado

    # Corrigido o bruto, a limpeza acontece.
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("202212_ESTBAN_AG.CSV", _csv())
    res = converter.convert(raiz, lake)
    assert res.errors == []
    assert _parquets(lake) == ["estban_agencia_2022-12__202212_estban_ag.parquet"]


def test_limpeza_nao_toca_outros_meses_nem_outro_dataset(tmp_path: Path) -> None:
    raiz, estban, lake = _fontes(tmp_path)
    _csv_solto(estban, "20230807")
    outro = estban / "estban_agencia_2023-01@20231004.csv"
    outro.write_bytes(_csv().replace(b"202212", b"202301"))
    converter.convert(raiz, lake)
    assert len(_parquets(lake)) == 2

    _zip(estban, "20261123")
    converter.convert(raiz, lake)
    assert _parquets(lake) == [
        "estban_agencia_2022-12__202212_estban_ag.parquet",
        "estban_agencia_2023-01.parquet",
    ]


def test_formatos_gemeos_da_mesma_publicacao_ficam_os_dois(tmp_path: Path) -> None:
    """x@D.csv e x@D.zip são a mesma publicação: um não substitui o outro."""
    raiz, estban, lake = _fontes(tmp_path)
    _csv_solto(estban, "20261123")
    _zip(estban, "20261123")
    res = converter.convert(raiz, lake)
    assert res.errors == []
    assert _parquets(lake) == [
        "estban_agencia_2022-12.parquet",
        "estban_agencia_2022-12__202212_estban_ag.parquet",
    ]
    res = converter.convert(raiz, lake)
    assert (res.converted, res.skipped) == (0, 2)
    assert len(_parquets(lake)) == 2


def test_membro_so_com_cabecalho_vira_parquet_vazio_e_cobre_o_bruto(
    tmp_path: Path,
) -> None:
    """O bruto vigente sem linhas (cabeçalho só) tem Parquet vazio, com o esquema."""
    raiz, estban, lake = _fontes(tmp_path)
    _zip(estban, "20240322")
    converter.convert(raiz, lake)
    ds = lake / SOURCE / "estban_agencia"
    (cheio,) = ds.rglob("*.parquet")
    assert pl.read_parquet(cheio).height == 2

    # A versão nova do mês chega sem dados: a partição é a do nome do membro.
    _zip(estban, "20261123", com_linhas=False)
    res = converter.convert(raiz, lake)
    assert (res.converted, res.errors) == (1, [])
    (vazio,) = ds.rglob("*.parquet")
    assert vazio.parent == ds / "ano=2022" / "mes=12"
    assert pl.read_parquet(vazio).height == 0
    assert not check_dataset(ds)
    assert _achados(lake, raiz) == {}


@pytest.mark.parametrize("municipio", [False, True])
def test_parquet_vazio_tem_o_esquema_do_cheio(tmp_path: Path, municipio: bool) -> None:
    """Mesmos nomes e tipos com e sem linhas: Polars e DuckDB leem a pasta junta."""
    raiz, estban, lake = _fontes(tmp_path)
    dataset = "estban_municipio" if municipio else "estban_agencia"
    prefixo = "estban_municipio" if municipio else "estban_agencia"
    membro = "202212_ESTBAN.CSV" if municipio else "202212_ESTBAN_AG.CSV"
    # Um mês com linhas e outro (mesma pasta de dataset) só com o cabeçalho.
    for nome, mes, linhas in (
        (f"{prefixo}_2022-12", "202212", True),
        (f"{prefixo}_2023-01", "202301", False),
    ):
        path = estban / f"{nome}@20261123.zip"
        csv = _csv(linhas, municipio=municipio).replace(b"202212", mes.encode())
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(membro.replace("202212", mes), csv)
    res = converter.convert(raiz, lake)
    assert res.errors == []

    ds = lake / SOURCE / dataset
    cheio = next(ds.glob("ano=2022/mes=12/*.parquet"))
    vazio = next(ds.glob("ano=2023/mes=1/*.parquet"))
    sc, sv = pl.read_parquet(cheio).schema, pl.read_parquet(vazio).schema
    assert pl.read_parquet(cheio).height > 0 and pl.read_parquet(vazio).height == 0
    assert sv == sc, {c: (sc[c], sv[c]) for c in sc if sc[c] != sv.get(c)}

    # Polars lê a pasta com os dois (esquemas diferentes quebram aqui).
    total = pl.scan_parquet([cheio, vazio], extra_columns="ignore").collect()
    assert total.height == pl.read_parquet(cheio).height
    # DuckDB com union_by_name: um tipo por coluna.
    tipos = duckdb.sql(
        f"DESCRIBE SELECT * FROM read_parquet(['{cheio}', '{vazio}'], "
        "union_by_name=true)"
    ).fetchall()
    assert {n: t for n, t, *_ in tipos}["data_base"] == "BIGINT"
    assert not check_dataset(ds)


def test_membro_vazio_usa_o_nome_do_bruto_quando_o_membro_nao_tem_data(
    tmp_path: Path,
) -> None:
    raiz, estban, lake = _fontes(tmp_path)
    _zip(estban, "20261123", membro="ESTBAN_AG.CSV", com_linhas=False)
    res = converter.convert(raiz, lake)
    assert res.errors == []
    ds = lake / SOURCE / "estban_agencia"
    (vazio,) = ds.rglob("*.parquet")
    assert vazio.parent == ds / "ano=2022" / "mes=12"  # do nome do bruto


def test_membro_vazio_sem_data_em_lugar_nenhum_e_erro(tmp_path: Path) -> None:
    raiz, estban, lake = _fontes(tmp_path)
    _zip(
        estban,
        "20261123",
        nome="estban_agencia_historico",
        membro="ESTBAN_AG.CSV",
        com_linhas=False,
    )
    res = converter.convert(raiz, lake)
    assert len(res.errors) == 1 and "partição não inferida" in res.errors[0]
    assert not list((lake / SOURCE).rglob("*.parquet"))
