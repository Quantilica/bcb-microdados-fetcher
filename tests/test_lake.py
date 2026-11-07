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
        "AGEN_ESPERADAS;AGEN_PROCESSADAS;"
        "VERBETE_110_DISPONIBILIDADES;461+467+468_OUTRAS;"
        "VERBETE_141_CORRESPONDENTES_NO_EXTERIOR + VERBETE_142_CORRESPONDENTES_NO_PAIS;"
        "VERBETE_144_COBRANCA_EM_TRANSITO + VERBETE_145_ORDENS_DE_PAGAMENTO\t"
        "+ VERBETE_146_VAL_LIGADAS_E_TERC_EM_TRANSITO\n"
        "202406;00000000;BANCO DO BRASIL;7388;SAO PAULO   ;SP;3550308;12;11;"
        "50000;12000;7;9\n"
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
    assert df_mun.height == 4
    assert df_mun["verbete_codigo"].to_list() == [
        "110",
        "461+467+468",
        "141+142",
        "144+145+146",
    ]
    assert df_mun["verbete_nome"][2] == (
        "correspondentes_no_exterior+correspondentes_no_pais"
    )
    assert df_mun["valor"].to_list() == [50000, 12000, 7, 9]
    # contagem de agencias e atributo da linha, nao verbete
    assert df_mun["agen_esperadas"].to_list() == [12] * 4
    assert df_mun["agen_processadas"].to_list() == [11] * 4
    assert df_mun["municipio"][0] == "SAO PAULO"
    assert df_mun["moeda"].to_list() == ["R$"] * 4
    assert df_mun.schema["cnpj"] == pl.String
    assert df_mun["cnpj"][0] == "00000000"

    # Verify agência
    ds_ag = lake_dir / "bcb-microdados" / "estban_agencia"
    errors_ag = check_dataset(ds_ag)
    assert not errors_ag, f"check_dataset errors ag: {errors_ag}"
    (part_ag,) = list((ds_ag / "ano=2024" / "mes=6").glob("*.parquet"))
    df_ag = pl.read_parquet(part_ag)
    assert df_ag["agencia"][0] == "00000000517569"
    assert df_ag["cnpj"][0] == "00000000"


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


# --- Regressao A1: ZIP multi-membro, streaming e encoding estrito ---------------


def _rows(ds: Path) -> pl.DataFrame:
    return pl.concat(
        [pl.read_parquet(p) for p in sorted(ds.rglob("*.parquet"))], how="diagonal"
    )


def _scr_csv(mes: int, n: int = 2, extra: str = "") -> bytes:
    head = "data_base;uf;numero_de_operacoes;carteira_ativa\n"
    body = "".join(f"2024-{mes:02d}-01;SP{extra};{i + 1};10,00\n" for i in range(n))
    return (head + body).encode("utf-8-sig")


def test_scr_zip_tres_membros_preserva_todas_as_linhas(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "scr"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "scrdata_2024@20261101.zip", "w") as zf:
        for mes in (1, 2, 3):
            zf.writestr(f"scrdata_2024{mes:02d}.csv", _scr_csv(mes))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors
    assert (res.converted, res.skipped) == (3, 0)
    ds = lake / "bcb-microdados" / "scr"
    assert not check_dataset(ds)
    assert _rows(ds).height == 6
    res2 = converter.convert(tmp_path / "raw", lake)
    assert (res2.converted, res2.skipped) == (0, 3)
    assert _rows(ds).height == 6


def test_scr_membros_na_mesma_particao_nao_se_pulam(tmp_path: Path) -> None:
    """Dois membros do mesmo ano/mes (mesma particao) precisam coexistir."""
    raw = tmp_path / "raw" / "scr"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "scrdata_2024@20261101.zip", "w") as zf:
        zf.writestr("parte_a.csv", _scr_csv(1, 2, "a"))
        zf.writestr("parte_b.csv", _scr_csv(1, 3, "b"))
        zf.writestr("parte_c.csv", _scr_csv(1, 4, "c"))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors
    assert res.converted == 3
    assert _rows(lake / "bcb-microdados" / "scr").height == 9


def test_estban_zip_tres_membros(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "estban"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "2024_ESTBAN@20261101.zip", "w") as zf:
        for mes in (1, 2, 3):
            csv = (
                "ESTBAN\nData: x\n"
                "#DATA_BASE;CNPJ;NOME_INSTITUICAO;CODMUN;MUNICIPIO;UF;CODMUN_IBGE;"
                "VERBETE_110_DISPONIBILIDADES\n"
                f"2024{mes:02d};1;BANCO S\xc3O;7388;SAO PAULO;SP;3550308;{mes}\n"
            )
            zf.writestr(f"2024{mes:02d}_ESTBAN.csv", csv.encode("latin-1"))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors
    assert res.converted == 3
    df = _rows(lake / "bcb-microdados" / "estban_municipio")
    assert sorted(df["valor"].to_list()) == [1, 2, 3]
    assert "BANCO S\xc3O" in df["nome_instituicao"].to_list()


def test_cosif_zip_tres_membros_mesma_particao(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "cosif"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "2024BANCOS@20261101.zip", "w") as zf:
        for i in (1, 2, 3):
            csv = (
                "Balancete\nx\ny\n"
                "#DATA_BASE;DOCUMENTO;CNPJ;AGENCIA;NOME_INSTITUICAO;COD_CONGL;"
                "NOME_CONGL;TAXONOMIA;CONTA;NOME_CONTA;SALDO\n"
                f"202412;4010;{i};0001;BANCO A\xc7\xc3O;0;N;0;1111222{i};CAIXA;1,50\n"
            )
            zf.writestr(f"202412BANCOS_{i}.csv", csv.encode("cp1252"))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors
    assert res.converted == 3
    df = _rows(lake / "bcb-microdados" / "cosif")
    assert df.height == 3
    assert "BANCO A\xc7\xc3O" in df["nome_instituicao"].to_list()


def test_cosif_prudencial_cnpj_alfanumerico_apos_inferencia(tmp_path: Path) -> None:
    """CNPJ com codigo de conglomerado depois das 5.000 linhas da inferencia."""
    raw = tmp_path / "raw" / "cosif"
    raw.mkdir(parents=True)
    linha = (
        "202606;4060;{cnpj};;{nome};{congl};X - PRUDENCIAL;"
        "CONGLOMERADO PRUDENCIAL;1000000009;Ativo;1,50\n"
    )
    csv = (
        "Balancete/Balanco Geral Consolidado Prudencial\nx\ny\n"
        "#DATA_BASE;DOCUMENTO;CNPJ;AGENCIA;NOME_INSTITUICAO;COD_CONGL;NOME_CONGL;"
        "TAXONOMIA;CONTA;NOME_CONTA;SALDO\n"
        + linha.format(cnpj="00000000", nome="BCO DO BRASIL S.A.", congl="C0080329")
        * 6000
        + linha.format(cnpj="C0085111", nome="", congl="C0085111")
    )
    with zipfile.ZipFile(raw / "cosif_prudencial_2026-06@20261103.zip", "w") as zf:
        zf.writestr("202606BLOPRUDENCIAL.CSV", csv.encode("cp1252"))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors
    assert res.converted == 1
    df = _rows(lake / "bcb-microdados" / "cosif" / "segmento=prudencial")
    assert df.height == 6001
    assert df.schema["cnpj"] == pl.String
    assert df.schema["cod_congl"] == pl.String
    assert set(df["cnpj"].unique().to_list()) == {"00000000", "C0085111"}


def test_cosif_conglomerados_largura_fixa(tmp_path: Path) -> None:
    """Layout 2007-2010: COD.CONGLOMERADO, campos com espacos e saldo com sinal."""
    raw = tmp_path / "raw" / "cosif"
    raw.mkdir(parents=True)
    csv = (
        "Consolidado Financeiro (doc 4040)\nx\ny\n"
        "DATA;COD.CONGLOMERADO;NOME CONGLOMERADO;ATRIBUTO;DOCUMENTO;CONTA;"
        "NOME CONTA;SALDO\n"
        "200901;00010045;BRADESCO     ;G;4040;0010000007;CIRCULANTE     ;"
        " 0000363577595065,18\n"
        "200901;00010045;BRADESCO     ;G;4040;0090900000;CONTROLE       ;"
        "-0000000005840912,56\n"
    )
    with zipfile.ZipFile(raw / "cosif_conglomerados_2009-01@20230509.zip", "w") as zf:
        zf.writestr("200901CONGLOMERADOS.CSV", csv.encode("cp1252"))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors
    df = _rows(lake / "bcb-microdados" / "cosif")
    assert df.schema["cod_congl"] == pl.String
    assert df.schema["saldo"] == pl.Float64
    assert df["cod_congl"].to_list() == ["00010045", "00010045"]
    assert df["nome_congl"][0] == "BRADESCO"
    assert df["conta"].to_list() == ["10000007", "90900000"]
    assert df["saldo"].to_list() == [363577595065.18, -5840912.56]


def test_cosif_marcador_sem_dados_nao_vira_linha(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "cosif"
    raw.mkdir(parents=True)
    csv = (
        "Balancete Patrimonial\nx\ny\n"
        "DATA;CNPJ;NOME INSTITUICAO;ATRIBUTO;DOCUMENTO;CONTA;NOME CONTA;SALDO\n"
        "200901 ******** NAO EXISTE DADOS PARA ESTE SEGMENTO DATA"
        "******************** H      \r\n"
    )
    with zipfile.ZipFile(raw / "cosif_consorcios_2009-01@20230509.zip", "w") as zf:
        zf.writestr("200901CONSORCIOS.CSV", csv.encode("cp1252"))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors
    assert res.converted == 0
    assert not list((lake / "bcb-microdados" / "cosif").rglob("*.parquet"))


def test_scr_byte_invalido_vira_erro_e_nao_substitui(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "scr"
    raw.mkdir(parents=True)
    ruim = b"data_base;uf;numero_de_operacoes\n2024-02-01;S\xc3;1\n"
    with zipfile.ZipFile(raw / "scrdata_2024@20261101.zip", "w") as zf:
        zf.writestr("scrdata_202401.csv", _scr_csv(1))
        zf.writestr("scrdata_202402.csv", ruim)
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert res.converted == 1
    assert len(res.errors) == 1 and "202402" in res.errors[0]
    assert "�" not in "".join(_rows(lake / "bcb-microdados" / "scr")["uf"].to_list())


def test_leitura_nao_carrega_o_membro_inteiro(tmp_path: Path, monkeypatch) -> None:
    def _proibido(self, *args, **kwargs):
        raise AssertionError("ZipFile.read carrega o membro inteiro na memoria")

    monkeypatch.setattr(zipfile.ZipFile, "read", _proibido)
    raw = tmp_path / "raw" / "scr"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "scrdata_2024@20261101.zip", "w") as zf:
        zf.writestr("scrdata_202401.csv", _scr_csv(1))
    lake = tmp_path / "lake"
    lake.mkdir()
    res = converter.convert(tmp_path / "raw", lake)
    assert not res.errors and res.converted == 1


FIX = Path(__file__).parent / "fixtures" / "olinda"


def _stage(tmp_path: Path, group: str, name: str, fixture: str) -> Path:
    raw = tmp_path / "raw"
    (raw / group).mkdir(parents=True)
    (raw / group / name).write_bytes((FIX / fixture).read_bytes())
    return raw


def test_pix_municipio_transacoes_lake(tmp_path: Path) -> None:
    raw = _stage(
        tmp_path,
        "pix_municipio_transacoes",
        "pix_municipio_transacoes_2025-09.json",
        "pix_municipio_202509.json",
    )
    lake = tmp_path / "lake"
    res = converter.convert(raw, lake)
    assert (res.converted, res.errors) == (1, [])

    dataset_dir = lake / "bcb-microdados" / "pix_municipio_transacoes"
    assert check_dataset(dataset_dir) == []
    assert (dataset_dir / "ano=2025" / "mes=9").exists() or (
        dataset_dir / "ano=2025" / "mes=09"
    ).exists()
    df = pl.read_parquet(next(dataset_dir.rglob("*.parquet")))
    assert df.schema["codigo_ibge"] == pl.String
    assert df["codigo_ibge"][0] == "1200450"
    assert all(len(v) == 7 for v in df["codigo_ibge"])
    assert df.schema["uf_ibge"] == pl.String and df["uf_ibge"][0] == "12"
    assert isinstance(df.schema["vl_pagador_pf"], pl.Decimal)
    assert str(df["vl_pagador_pf"][0]) == "87211594.48"
    assert df["qt_pagador_pf"][0] == 647985
    assert "ano_mes" not in df.columns

    again = converter.convert(raw, lake)
    assert (again.converted, again.skipped, again.errors) == (0, 1, [])


def test_scr_sub_regiao_is_not_taken_by_scr_converter(tmp_path: Path) -> None:
    raw = _stage(
        tmp_path,
        "scr_sub_regiao",
        "scr_sub_regiao_2020-12.json",
        "scr_sub_regiao_202012.json",
    )
    lake = tmp_path / "lake"
    res = converter.convert(raw, lake)
    assert (res.converted, res.errors) == (1, [])
    assert not (lake / "bcb-microdados" / "scr").exists()

    dataset_dir = lake / "bcb-microdados" / "scr_sub_regiao"
    assert check_dataset(dataset_dir) == []
    df = pl.read_parquet(next(dataset_dir.rglob("*.parquet")))
    assert df.schema["sub_regiao"] == pl.String
    assert set(df["risco"].to_list()) <= {"AA-C", "D-H"}
    assert df.schema["operacoes"] == pl.Int64
    assert isinstance(df.schema["carteira"], pl.Decimal)


def test_scr_sub_regiao_risco_descontinuado_fica_nulo_ou_nd(tmp_path: Path) -> None:
    raw = _stage(
        tmp_path,
        "scr_sub_regiao",
        "scr_sub_regiao_2026-09.json",
        "scr_sub_regiao_202609.json",
    )
    res = converter.convert(raw, tmp_path / "lake")
    assert (res.converted, res.errors) == (1, [])
    df = pl.read_parquet(
        next(
            (tmp_path / "lake" / "bcb-microdados" / "scr_sub_regiao").rglob("*.parquet")
        )
    )
    assert set(df["risco"].to_list()) == {"N/D"}


def test_olinda_json_empty_or_multi_month_is_counted_error(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "pix_municipio_transacoes"
    raw.mkdir(parents=True)
    (raw / "pix_municipio_transacoes_2025-09.json").write_text('{"value": []}')
    res = converter.convert(tmp_path / "raw", tmp_path / "lake")
    assert res.converted == 0 and len(res.errors) == 1
    assert "sem linhas" in res.errors[0]

    multi = (FIX / "pix_municipio_202509.json").read_text()
    rows = __import__("json").loads(multi)
    rows["value"][0]["AnoMes"] = 202510
    (raw / "pix_municipio_transacoes_2025-09.json").write_text(
        __import__("json").dumps(rows)
    )
    res = converter.convert(tmp_path / "raw", tmp_path / "lake", force=True)
    assert len(res.errors) == 1 and "períodos" in res.errors[0]
