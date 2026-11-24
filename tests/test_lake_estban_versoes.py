"""ESTBAN: troca de formato do bruto entre versões e membro sem linhas.

O BCB republicou meses antigos do ESTBAN: o CSV solto (``x@2023.csv``) virou ZIP
(``x@2026.zip``) com o mesmo conteúdo, e um mês veio só com o cabeçalho. A chave do
Parquet muda com o formato (``x`` -> ``x__x_csv``), e o Parquet da versão anterior
ficava ao lado do novo (``versao_duplicada``, ``origem_superada``).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import polars as pl
from quantilica.analytics.lake import check_dataset
from quantilica.analytics.lake_audit import lake_audit

from bcb_microdados_fetcher.lake import converter

_CAB = (
    "ESTBAN (Documento 4500) por agencia\n"
    "Data de geracao dos dados: 2023-10-16\n"
    "#DATA_BASE;UF;CODMUN;MUNICIPIO;CNPJ;NOME_INSTITUICAO;AGENCIA;"
    "VERBETE_110_DISPONIBILIDADES;VERBETE_111_CAIXA\n"
)
_LINHA = "202212;SP;7388;SAO PAULO;00000000;BANCO DO BRASIL;'0001;50;7\n"
SOURCE = "bcb-microdados"


def _csv(com_linhas: bool = True) -> bytes:
    return (_CAB + (_LINHA if com_linhas else "")).encode("latin-1")


def _csv_solto(raw: Path, carimbo: str, **kw) -> Path:
    path = raw / f"estban_agencia_2022-12@{carimbo}.csv"
    path.write_bytes(_csv(**kw))
    return path


def _zip(raw: Path, carimbo: str, **kw) -> Path:
    path = raw / f"estban_agencia_2022-12@{carimbo}.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("202212_ESTBAN_AG.CSV", _csv(**kw))
    return path


def _parquets(lake: Path) -> list[str]:
    ds = lake / SOURCE / "estban_agencia"
    return sorted(p.name for p in ds.rglob("*.parquet"))


def _achados(lake: Path, raw: Path) -> dict[str, int]:
    report = lake_audit(
        lake,
        input_dir=raw,
        sources=[SOURCE],
        readers=False,
        integrity=False,
        converters={SOURCE: converter},
    )
    # Sem _build.json o relatório traz também os achados de manifesto; só interessam
    # os de procedência, duplicidade e cobertura.
    return {
        k: v
        for k, v in report.by_category().items()
        if k in {"origem_superada", "versao_duplicada", "sem_parquet"}
    }


def test_csv_solto_que_vira_zip_substitui_o_parquet_antigo(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "estban"
    raw.mkdir(parents=True)
    lake = tmp_path / "lake"
    lake.mkdir()
    _csv_solto(raw, "20230807")
    res = converter.convert(tmp_path / "raw", lake)
    assert (res.converted, res.errors) == (1, [])
    assert _parquets(lake) == ["estban_agencia_2022-12.parquet"]
    assert _achados(lake, tmp_path / "raw") == {}

    # O BCB republica o mesmo mês como ZIP: o CSV antigo deixa de ser o vigente.
    _zip(raw, "20261123")
    res = converter.convert(tmp_path / "raw", lake)
    assert (res.converted, res.errors) == (1, [])
    assert _parquets(lake) == ["estban_agencia_2022-12__202212_estban_ag.parquet"]
    ds = lake / SOURCE / "estban_agencia"
    assert not check_dataset(ds)
    assert pl.read_parquet(next(ds.rglob("*.parquet"))).height == 2
    assert _achados(lake, tmp_path / "raw") == {}

    # Reexecutar não muda nada nem recria o antigo.
    res = converter.convert(tmp_path / "raw", lake)
    assert (res.converted, res.skipped) == (0, 1)
    assert _parquets(lake) == ["estban_agencia_2022-12__202212_estban_ag.parquet"]


def test_limpeza_nao_toca_outros_meses_nem_outro_dataset(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "estban"
    raw.mkdir(parents=True)
    lake = tmp_path / "lake"
    lake.mkdir()
    _csv_solto(raw, "20230807")
    outro = raw / "estban_agencia_2023-01@20231004.csv"
    outro.write_bytes(_csv().replace(b"202212", b"202301"))
    converter.convert(tmp_path / "raw", lake)
    assert len(_parquets(lake)) == 2

    _zip(raw, "20261123")
    converter.convert(tmp_path / "raw", lake)
    assert _parquets(lake) == [
        "estban_agencia_2022-12__202212_estban_ag.parquet",
        "estban_agencia_2023-01.parquet",
    ]


def test_formatos_gemeos_da_mesma_publicacao_ficam_os_dois(tmp_path: Path) -> None:
    """x@D.csv e x@D.zip são a mesma publicação: um não substitui o outro."""
    raw = tmp_path / "raw" / "estban"
    raw.mkdir(parents=True)
    lake = tmp_path / "lake"
    lake.mkdir()
    _csv_solto(raw, "20261123")
    _zip(raw, "20261123")
    res = converter.convert(tmp_path / "raw", lake)
    assert res.errors == []
    assert _parquets(lake) == [
        "estban_agencia_2022-12.parquet",
        "estban_agencia_2022-12__202212_estban_ag.parquet",
    ]
    res = converter.convert(tmp_path / "raw", lake)
    assert (res.converted, res.skipped) == (0, 2)
    assert len(_parquets(lake)) == 2


def test_membro_so_com_cabecalho_vira_parquet_vazio_e_cobre_o_bruto(
    tmp_path: Path,
) -> None:
    """O bruto vigente sem linhas (cabeçalho só) tem Parquet vazio, com o esquema."""
    raw = tmp_path / "raw" / "estban"
    raw.mkdir(parents=True)
    lake = tmp_path / "lake"
    lake.mkdir()
    _zip(raw, "20240322")
    converter.convert(tmp_path / "raw", lake)
    ds = lake / SOURCE / "estban_agencia"
    (cheio,) = ds.rglob("*.parquet")
    assert pl.read_parquet(cheio).height == 2

    # A versão nova do mês chega sem dados: a partição é a do nome do membro.
    _zip(raw, "20261123", com_linhas=False)
    res = converter.convert(tmp_path / "raw", lake)
    assert (res.converted, res.errors) == (1, [])
    (vazio,) = ds.rglob("*.parquet")
    assert vazio.parent == ds / "ano=2022" / "mes=12"
    df = pl.read_parquet(vazio)
    assert df.height == 0
    assert df.schema["valor"] == pl.Int64
    assert {"verbete_codigo", "verbete_nome", "moeda", "agencia"} <= set(df.columns)
    assert not check_dataset(ds)
    assert _achados(lake, tmp_path / "raw") == {}
