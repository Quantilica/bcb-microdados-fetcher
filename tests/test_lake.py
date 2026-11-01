"""Tests for bcb-microdados-fetcher lake converter."""

from __future__ import annotations

import zipfile
from pathlib import Path

import polars as pl
from quantilica.analytics.lake import check_dataset

from bcb_microdados_fetcher.lake import converter


def test_converter_metadata() -> None:
    assert converter.source_id == "bcb-microdados"
    datasets = converter.datasets()
    assert "scr" in datasets
    assert "estban_municipio" in datasets
    assert "estban_agencia" in datasets
    assert "cosif" in datasets


def test_converter_empty_dir(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lake_dir = tmp_path / "lake"
    lake_dir.mkdir()

    res = converter.convert(raw_dir, lake_dir)
    assert res.converted == 0
    assert not res.errors


def test_convert_scr_secrecy(tmp_path: Path) -> None:
    """Test SCR conversion with statistical secrecy handling (-1 -> None)."""
    raw_dir = tmp_path / "raw" / "scr"
    raw_dir.mkdir(parents=True)
    lake_dir = tmp_path / "lake"
    lake_dir.mkdir()

    csv_text = (
        "data_base;uf;segmento;cliente;cnae_ocupacao;porte;modalidade;"
        "submodalidade;origem;indexador;numero_de_operacoes;carteira_ativa\n"
        "2024-01-01;SP;Bancos;PF;Assalariado;PF;Cartao;Rotativo;Livre;Pos;-1;1500,50\n"
        "2024-01-01;RJ;Bancos;PJ;Comercio;Medio;Capital Giro;Normal;Livre;"
        "Pos;12;25000,00\n"
    )
    zip_path = raw_dir / "scrdata_2024@20261101.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("scrdata_202401.csv", csv_text.encode("utf-8-sig"))

    res = converter.convert(raw_dir.parent, lake_dir)
    assert res.converted == 1
    assert not res.errors

    ds_dir = lake_dir / "bcb-microdados" / "scr"
    errors = check_dataset(ds_dir)
    assert not errors, f"check_dataset errors: {errors}"

    (part_file,) = list((ds_dir / "ano=2024" / "mes=1").glob("*.parquet"))
    assert part_file.exists()
    df = pl.read_parquet(part_file)
    assert df["sigilo"].to_list() == [True, False]
    assert df["numero_de_operacoes"].to_list() == [None, 12.0]


def test_convert_estban_long_format(tmp_path: Path) -> None:
    """Test ESTBAN conversion to long format and agency apostrophe stripping."""
    raw_dir = tmp_path / "raw" / "estban"
    raw_dir.mkdir(parents=True)
    lake_dir = tmp_path / "lake"
    lake_dir.mkdir()

    # 1. Município
    csv_mun = (
        "ESTBAN (Documento 4500) por municipio\n"
        "Data de geracao dos dados: 2024-08-31\n"
        "#DATA_BASE;CNPJ;NOME_INSTITUICAO;CODMUN;MUNICIPIO;UF;CODMUN_IBGE;"
        "VERBETE_110_DISPONIBILIDADES;461+467+468_OUTRAS\n"
        "202406;00000000;BANCO DO BRASIL;7388;SAO PAULO;SP;3550308;50000;12000\n"
    )
    zip_mun = raw_dir / "202406_ESTBAN@20261101.zip"
    with zipfile.ZipFile(zip_mun, "w") as zf:
        zf.writestr("202406_ESTBAN.csv", csv_mun.encode("latin-1"))

    # 2. Agência
    csv_ag = (
        "ESTBAN (Documento 4500) por agencia\n"
        "Data de geracao dos dados: 2024-08-31\n"
        "#DATA_BASE;CNPJ;NOME_INSTITUICAO;AGENCIA;CODMUN;MUNICIPIO;UF;CODMUN_IBGE;"
        "VERBETE_110_DISPONIBILIDADES\n"
        "202406;00000000;BANCO DO BRASIL;'00000000517569;7388;SAO PAULO;SP;"
        "3550308;25000\n"
    )
    zip_ag = raw_dir / "202406_ESTBAN_AG@20261101.zip"
    with zipfile.ZipFile(zip_ag, "w") as zf:
        zf.writestr("202406_ESTBAN_AG.csv", csv_ag.encode("latin-1"))

    res = converter.convert(raw_dir.parent, lake_dir)
    assert res.converted == 2
    assert not res.errors

    # Verify município
    ds_mun = lake_dir / "bcb-microdados" / "estban_municipio"
    errors_mun = check_dataset(ds_mun)
    assert not errors_mun, f"check_dataset errors mun: {errors_mun}"
    (part_mun,) = list((ds_mun / "ano=2024" / "mes=6").glob("*.parquet"))
    df_mun = pl.read_parquet(part_mun)
    assert df_mun.height == 2
    assert set(df_mun["verbete_codigo"].to_list()) == {"110", "461+467+468"}
    assert df_mun["valor"].to_list() == [50000, 12000]

    # Verify agência
    ds_ag = lake_dir / "bcb-microdados" / "estban_agencia"
    errors_ag = check_dataset(ds_ag)
    assert not errors_ag, f"check_dataset errors ag: {errors_ag}"
    (part_ag,) = list((ds_ag / "ano=2024" / "mes=6").glob("*.parquet"))
    df_ag = pl.read_parquet(part_ag)
    assert df_ag["agencia"][0] == "00000000517569"


def test_convert_cosif_eras_and_plans(tmp_path: Path) -> None:
    """Test COSIF conversion across L11, L8, and 2025 10-digit account plan."""
    raw_dir = tmp_path / "raw" / "cosif"
    raw_dir.mkdir(parents=True)
    lake_dir = tmp_path / "lake"
    lake_dir.mkdir()

    # 1. 2024 L11 (plano antigo 8 dígitos, moeda R$)
    csv_2024 = (
        "Balancete Patrimonial COSIF\n"
        "Data de geracao dos dados: 2025-01-15\n"
        "Fonte: Banco Central do Brasil\n"
        "#DATA_BASE;DOCUMENTO;CNPJ;AGENCIA;NOME_INSTITUICAO;COD_CONGL;NOME_CONGL;"
        "TAXONOMIA;CONTA;NOME_CONTA;SALDO\n"
        "202412;4010;00000000;0001;BANCO DO BRASIL;0;NENHUM;0;11112222;CAIXA;"
        "123456,78\n"
    )
    zip_2024 = raw_dir / "202412BANCOS@20261101.zip"
    with zipfile.ZipFile(zip_2024, "w") as zf:
        zf.writestr("202412BANCOS.csv", csv_2024.encode("cp1252"))

    # 2. 1995 L8 (conta com '00' na frente, moeda R$)
    csv_1995 = (
        "Balancete Patrimonial COSIF\n"
        "Data de geracao dos dados: 1995-02-15\n"
        "Fonte: Banco Central do Brasil\n"
        "DATA;CNPJ;NOME INSTITUICAO;ATRIBUTO;DOCUMENTO;CONTA;NOME CONTA;SALDO\n"
        "199501;00000000;BANCO DO BRASIL;U;4010;0011112222;CAIXA; 000000005555,50\n"
    )
    zip_1995 = raw_dir / "199501BANCOS@20261101.zip"
    with zipfile.ZipFile(zip_1995, "w") as zf:
        zf.writestr("199501BANCOS.csv", csv_1995.encode("cp1252"))

    # 3. 2025 L11 (plano novo 10 dígitos)
    csv_2025 = (
        "Balancete Patrimonial COSIF\n"
        "Data de geracao dos dados: 2025-02-15\n"
        "Fonte: Banco Central do Brasil\n"
        "#DATA_BASE;DOCUMENTO;CNPJ;AGENCIA;NOME_INSTITUICAO;COD_CONGL;NOME_CONGL;"
        "TAXONOMIA;CONTA;NOME_CONTA;SALDO\n"
        "202501;4010;00000000;0001;BANCO DO BRASIL;0;NENHUM;0;1000000009;CAIXA;"
        "999999,99\n"
    )
    zip_2025 = raw_dir / "202501BANCOS@20261101.zip"
    with zipfile.ZipFile(zip_2025, "w") as zf:
        zf.writestr("202501BANCOS.csv", csv_2025.encode("cp1252"))

    res = converter.convert(raw_dir.parent, lake_dir)
    assert res.converted == 3
    assert not res.errors

    ds_cosif = lake_dir / "bcb-microdados" / "cosif"
    errors_cosif = check_dataset(ds_cosif)
    assert not errors_cosif, f"check_dataset errors cosif: {errors_cosif}"

    (part_2024,) = list((ds_cosif / "segmento=bancos" / "ano=2024").glob("*.parquet"))
    df_2024 = pl.read_parquet(part_2024)
    assert df_2024["plano"][0] == "cosif_1988"
    assert df_2024["moeda"][0] == "R$"
    assert df_2024["conta"][0] == "11112222"

    (part_1995,) = list((ds_cosif / "segmento=bancos" / "ano=1995").glob("*.parquet"))
    df_1995 = pl.read_parquet(part_1995)
    assert df_1995["plano"][0] == "cosif_1988"
    assert df_1995["conta"][0] == "11112222"

    (part_2025,) = list((ds_cosif / "segmento=bancos" / "ano=2025").glob("*.parquet"))
    df_2025 = pl.read_parquet(part_2025)
    assert df_2025["plano"][0] == "cosif_2025"
    assert df_2025["conta"][0] == "1000000009"
