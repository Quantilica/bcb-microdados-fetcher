"""O build sem mudança decide por sidecars e rodapés, sem transcodificar o bruto."""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")

import polars as pl  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import quantilica.analytics.lake as analytics_lake  # noqa: E402
import quantilica.core.manifests as manifests  # noqa: E402
from quantilica.analytics.lake import LakeWriter  # noqa: E402
from quantilica.core.lake import DatasetDescriptor, composite_file_key  # noqa: E402

import bcb_microdados_fetcher.lake as lake_mod  # noqa: E402
from bcb_microdados_fetcher.lake import converter  # noqa: E402

from .lake_fixtures import build_raw  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "olinda"
N_COSIF = 10  # membros com dados em lake_fixtures.PLANO (o marcador não conta)
SCR_HEAD = (
    "data_base;uf;segmento;cliente;cnae_ocupacao;porte;modalidade;"
    "submodalidade;origem;indexador;numero_de_operacoes;carteira_ativa\n"
)


def _scr_csv(mes: int, valor: str = "1500,50") -> bytes:
    return (
        SCR_HEAD
        + f"2024-{mes:02d}-01;SP;Bancos;PF;Assalariado;PF;Cartao;Rotativo;Livre;Pos;"
        + f"3;{valor}\n"
    ).encode("utf-8-sig")


def _sidecar(arquivo: Path) -> None:
    dados = arquivo.read_bytes()
    arquivo.with_name(arquivo.name + ".manifest.json").write_text(
        json.dumps(
            {"sha256": hashlib.sha256(dados).hexdigest(), "size_bytes": len(dados)}
        ),
        encoding="utf-8",
    )


def _sidecars(raw: Path) -> None:
    for f in raw.rglob("*"):
        if f.is_file() and not f.name.endswith(".manifest.json"):
            _sidecar(f)


@pytest.fixture
def leituras(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Transcodificações, leituras de início e do JSON do Olinda."""
    vistas: list[str] = []
    for nome in ("_member_as_utf8", "_cosif_peek", "_olinda_vazio", "_read_olinda"):
        original = getattr(lake_mod, nome)

        def espia(*args, _o=original, _n=nome, **kwargs):  # noqa: ANN002, ANN003
            vistas.append(f"{_n}:{Path(args[0]).name}")
            return _o(*args, **kwargs)

        monkeypatch.setattr(lake_mod, nome, espia)
    return vistas


@pytest.fixture
def sem_hash_por_leitura(monkeypatch: pytest.MonkeyPatch) -> None:
    def falha(path):  # noqa: ANN001, ANN202
        raise AssertionError(f"bruto lido para o sha256: {path}")

    monkeypatch.setattr(manifests, "sha256_file", falha)


def _scr_bruto(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    pasta = raw / "scr"
    pasta.mkdir(parents=True)
    with zipfile.ZipFile(pasta / "scrdata_2024@20261101.zip", "w") as zf:
        zf.writestr("scrdata_202401.csv", _scr_csv(1))
        zf.writestr("scrdata_202402.csv", _scr_csv(2))
    (pasta / "scrdata_202403@20261101.csv").write_bytes(_scr_csv(3))
    _sidecars(raw)
    return raw


def test_scr_em_dia_nao_transcodifica_zip_nem_csv(
    tmp_path: Path, leituras: list[str], sem_hash_por_leitura: None
) -> None:
    raw, lake = _scr_bruto(tmp_path), tmp_path / "lake"
    res = converter.convert(raw, lake, datasets=["scr"])
    assert not res.errors, res.errors
    assert res.converted == 3 and res.skipped == 0
    assert leituras

    leituras.clear()
    res2 = converter.convert(raw, lake, datasets=["scr"])
    assert not res2.errors, res2.errors
    assert (res2.converted, res2.skipped) == (0, 3)
    assert leituras == []


def test_scr_csv_novo_e_zip_alterado_convertem(
    tmp_path: Path, leituras: list[str]
) -> None:
    raw, lake = _scr_bruto(tmp_path), tmp_path / "lake"
    converter.convert(raw, lake, datasets=["scr"])
    (raw / "scr" / "scrdata_202403@20261201.csv").write_bytes(_scr_csv(3, "9,99"))
    (raw / "scr" / "scrdata_202404@20261201.csv").write_bytes(_scr_csv(4))

    leituras.clear()
    res = converter.convert(raw, lake, datasets=["scr"])

    assert not res.errors, res.errors
    assert res.converted == 2 and res.skipped == 2
    assert sorted(v for v in leituras if v.startswith("_member")) == [
        "_member_as_utf8:scrdata_202403@20261201.csv",
        "_member_as_utf8:scrdata_202404@20261201.csv",
    ]


def test_force_reconverte_scr_em_dia(tmp_path: Path) -> None:
    raw, lake = _scr_bruto(tmp_path), tmp_path / "lake"
    converter.convert(raw, lake, datasets=["scr"])
    res = converter.convert(raw, lake, datasets=["scr"], force=True)
    assert not res.errors, res.errors
    assert res.converted == 3 and res.skipped == 0


ESTBAN_MUN = (
    "ESTBAN (Documento 4500) por municipio\n"
    "Data de geracao dos dados: 2024-08-31\n"
    "#DATA_BASE;CNPJ;NOME_INSTITUICAO;CODMUN;MUNICIPIO;UF;CODMUN_IBGE;"
    "AGEN_ESPERADAS;AGEN_PROCESSADAS;VERBETE_110_DISPONIBILIDADES\n"
    "202406;00000000;BANCO DO BRASIL;7388;SAO PAULO   ;SP;3550308;12;11;50000\n"
)
ESTBAN_AG = (
    "ESTBAN (Documento 4500) por agencia\n"
    "Data de geracao dos dados: 2024-08-31\n"
    "#DATA_BASE;CNPJ;NOME_INSTITUICAO;AGENCIA;CODMUN;MUNICIPIO;UF;CODMUN_IBGE;"
    "VERBETE_110_DISPONIBILIDADES\n"
    "202406;00000000;BANCO DO BRASIL;'00000000517569;7388;SAO PAULO;SP;3550308;25000\n"
)


def _estban_bruto(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    pasta = raw / "estban"
    pasta.mkdir(parents=True)
    for nome, texto in (("202406_ESTBAN", ESTBAN_MUN), ("202406_ESTBAN_AG", ESTBAN_AG)):
        with zipfile.ZipFile(pasta / f"{nome}@20261101.zip", "w") as zf:
            zf.writestr(f"{nome}.csv", texto.encode("latin-1"))
    _sidecars(raw)
    return raw


def test_estban_em_dia_nao_transcodifica_e_cada_tarefa_conta_o_seu(
    tmp_path: Path, leituras: list[str], sem_hash_por_leitura: None
) -> None:
    raw, lake = _estban_bruto(tmp_path), tmp_path / "lake"
    res = converter.convert(raw, lake)
    assert not res.errors, res.errors
    assert res.converted == 2

    leituras.clear()
    for alvo, esperado in (
        (["estban_municipio"], 1),
        (["estban_agencia"], 1),
        (["estban_municipio", "estban_agencia"], 2),
    ):
        res2 = converter.convert(raw, lake, datasets=alvo)
        assert not res2.errors, res2.errors
        assert (res2.converted, res2.skipped) == (0, esperado), alvo
    assert leituras == []


def test_estban_nao_e_lido_numa_tarefa_de_outro_dataset(
    tmp_path: Path, leituras: list[str]
) -> None:
    raw, lake = _estban_bruto(tmp_path), tmp_path / "lake"
    res = converter.convert(raw, lake, datasets=["scr"])
    assert (res.converted, res.skipped, res.errors) == (0, 0, [])
    assert leituras == []


def test_olinda_em_dia_nao_le_o_json(
    tmp_path: Path, leituras: list[str], sem_hash_por_leitura: None
) -> None:
    raw = tmp_path / "raw"
    pasta = raw / "pix_municipio_transacoes"
    pasta.mkdir(parents=True)
    (pasta / "pix_municipio_transacoes_2025-09.json").write_bytes(
        (FIX / "pix_municipio_202509.json").read_bytes()
    )
    _sidecars(raw)
    lake = tmp_path / "lake"
    res = converter.convert(raw, lake, datasets=["pix_municipio_transacoes"])
    assert (res.converted, res.errors) == (1, [])

    leituras.clear()
    res2 = converter.convert(raw, lake, datasets=["pix_municipio_transacoes"])
    assert (res2.converted, res2.skipped, res2.errors) == (0, 1, [])
    assert leituras == []


def test_cosif_em_dia_so_olha_o_mes_sem_dados(
    tmp_path: Path, leituras: list[str], sem_hash_por_leitura: None
) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    build_raw(raw)
    _sidecars(raw)
    res = converter.convert(raw, lake, datasets=["cosif"])
    assert not res.errors, res.errors
    assert res.converted == N_COSIF

    leituras.clear()
    res2 = converter.convert(raw, lake, datasets=["cosif"])
    assert not res2.errors, res2.errors
    assert (res2.converted, res2.skipped) == (0, N_COSIF)
    # só o ZIP do mês sem dados (marcador) não deixa registro e é espiado de novo
    assert leituras == ["_cosif_peek:cosif_consorcios_2009-01@20261101.zip"]


def test_cosif_conta_igual_ao_caminho_completo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    build_raw(raw)
    converter.convert(raw, lake, datasets=["cosif"])
    rapido = converter.convert(raw, lake, datasets=["cosif"])
    with monkeypatch.context() as m:
        m.setattr(lake_mod, "_cosif_do_lake", lambda *a, **k: False)
        completo = converter.convert(raw, lake, datasets=["cosif"])
    assert (rapido.converted, rapido.skipped, rapido.errors) == (
        completo.converted,
        completo.skipped,
        completo.errors,
    )


def test_cosif_zip_novo_cai_no_caminho_completo(tmp_path: Path) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    build_raw(raw)
    converter.convert(raw, lake, datasets=["cosif"])
    zip_novo = raw / "cosif" / "cosif_bancos_2025-02@20261101.zip"
    zf_conteudo = "\n".join(
        [
            "DATA;CNPJ;NOME INSTITUICAO;ATRIBUTO;DOCUMENTO;CONTA;NOME CONTA;SALDO",
            "202502;1;BANCO;D;4010;1;CONTA;1,00",
        ]
    )
    with zipfile.ZipFile(zip_novo, "w") as zf:
        zf.writestr("202502BANCOS.csv", zf_conteudo.encode("cp1252"))

    res = converter.convert(raw, lake, datasets=["cosif"])

    assert not res.errors, res.errors
    assert res.converted == 1 and res.skipped == N_COSIF


def _olinda_bruto(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    pasta = raw / "pix_municipio_transacoes"
    pasta.mkdir(parents=True)
    (pasta / "pix_municipio_transacoes_2025-09.json").write_bytes(
        (FIX / "pix_municipio_202509.json").read_bytes()
    )
    _sidecars(raw)
    return raw


@pytest.fixture
def sem_abrir_csv_nem_json(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    """Devolve ``armar()``: depois dela, CSV/TXT/JSON do bruto não podem ser abertos.

    Vigia ``builtins.open``, ``io.open`` e ``Path.open``. ZIP e sidecar podem (o
    índice do ZIP é lido para saber os membros).
    """

    def vigia(original):  # noqa: ANN001, ANN202
        def aberto(file, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
            nome = str(file).lower() if isinstance(file, str | Path) else ""
            if "/raw/" in nome and nome.endswith((".csv", ".txt", ".json")):
                if not nome.endswith(".manifest.json"):
                    raise AssertionError(f"bruto aberto: {file}")
            return original(file, *args, **kwargs)

        return aberto

    def armar() -> None:
        monkeypatch.setattr(builtins, "open", vigia(builtins.open))
        monkeypatch.setattr(io, "open", vigia(io.open))
        original_path_open = Path.open

        def path_open(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
            return vigia(lambda f, *a, **k: original_path_open(Path(f), *a, **k))(
                self, *args, **kwargs
            )

        monkeypatch.setattr(Path, "open", path_open)

    return armar


def test_em_dia_nao_abre_csv_nem_json_do_bruto(
    tmp_path: Path, sem_abrir_csv_nem_json, sem_hash_por_leitura: None
) -> None:
    raw = _scr_bruto(tmp_path)
    (raw / "pix_municipio_transacoes").mkdir()
    (
        raw / "pix_municipio_transacoes" / "pix_municipio_transacoes_2025-09.json"
    ).write_bytes((FIX / "pix_municipio_202509.json").read_bytes())
    _sidecars(raw)
    lake = tmp_path / "lake"
    alvos = ["scr", "pix_municipio_transacoes"]
    assert not converter.convert(raw, lake, datasets=alvos).errors

    sem_abrir_csv_nem_json()
    res = converter.convert(raw, lake, datasets=alvos)
    assert (res.converted, res.skipped, res.errors) == (0, 4, [])


def test_parquet_com_a_chave_do_zip_nao_da_o_zip_por_convertido(
    tmp_path: Path,
) -> None:
    """Layout antigo: um Parquet com a chave do ZIP e o sha256 dele não pula o ZIP."""
    raw, lake = _scr_bruto(tmp_path), tmp_path / "lake"
    zip_ = raw / "scr" / "scrdata_2024@20261101.zip"
    writer = LakeWriter(
        lake / "bcb-microdados" / "scr",
        DatasetDescriptor(
            source_id="bcb-microdados",
            dataset_id="scr",
            alias="scr",
            partition_keys=["ano", "mes"],
            partition_types={"ano": "int", "mes": "int"},
        ),
    )
    writer.write_polars(
        pl.DataFrame({"x": [1]}),
        src=zip_,
        partitions={"ano": 2024, "mes": 1},
        file_key_name=composite_file_key(zip_, None).lower(),
    )

    res = converter.convert(raw, lake, datasets=["scr"])

    assert not res.errors, res.errors
    assert res.converted == 3  # os dois membros do ZIP e o CSV solto


def test_sha256_com_erro_de_es_no_csv_solto_vira_erro_da_tarefa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, lake = _scr_bruto(tmp_path), tmp_path / "lake"
    converter.convert(raw, lake, datasets=["scr"])
    original = lake_mod.sha256_file

    def sha(path):  # noqa: ANN001, ANN202
        if str(path).endswith(".csv"):
            raise OSError(5, "Input/output error")
        return original(path)

    monkeypatch.setattr(lake_mod, "sha256_file", sha)
    monkeypatch.setattr(analytics_lake, "sha256_file", sha)

    res = converter.convert(raw, lake, datasets=["scr"])  # não levanta

    assert any("scrdata_202403" in e for e in res.errors)
    assert res.skipped == 2  # os membros do ZIP seguem pulados


def test_conversao_interrompida_no_membro_de_um_zip_e_completada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, lake = _scr_bruto(tmp_path), tmp_path / "lake"
    original = LakeWriter.write_polars

    def cai_no_segundo_membro(self, data, src, **kw):  # noqa: ANN001, ANN003, ANN202
        if str(kw.get("file_key_name", "")).endswith("scrdata_202402"):
            raise RuntimeError("sem espaço em disco")
        return original(self, data, src, **kw)

    with monkeypatch.context() as m:
        m.setattr(LakeWriter, "write_polars", cai_no_segundo_membro)
        r1 = converter.convert(raw, lake, datasets=["scr"])
    assert (r1.converted, len(r1.errors)) == (2, 1)

    r2 = converter.convert(raw, lake, datasets=["scr"])
    assert (r2.converted, r2.skipped, r2.errors) == (1, 2, [])
    r3 = converter.convert(raw, lake, datasets=["scr"])
    assert (r3.converted, r3.skipped, r3.errors) == (0, 3, [])


def test_cosif_interrompido_num_grupo_e_completado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    build_raw(raw)
    _sidecars(raw)
    original = LakeWriter.write_group
    chamadas: list[str] = []

    def cai_no_terceiro(self, group_key, members, **kw):  # noqa: ANN001, ANN003, ANN202
        chamadas.append(group_key)
        if len(chamadas) == 3:
            raise RuntimeError("kill")
        return original(self, group_key, members, **kw)

    with monkeypatch.context() as m:
        m.setattr(LakeWriter, "write_group", cai_no_terceiro)
        r1 = converter.convert(raw, lake, datasets=["cosif"])
    assert len(r1.errors) == 1 and r1.converted < N_COSIF

    r2 = converter.convert(raw, lake, datasets=["cosif"])
    assert not r2.errors, r2.errors
    assert r2.converted + r2.skipped == N_COSIF and r2.converted >= 1
    r3 = converter.convert(raw, lake, datasets=["cosif"])
    assert (r3.converted, r3.skipped, r3.errors) == (0, N_COSIF, [])


def test_cosif_converter_version_nova_reconverte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    build_raw(raw)
    converter.convert(raw, lake, datasets=["cosif"])
    monkeypatch.setattr(lake_mod, "COSIF_CONVERTER_VERSION", "2")

    r2 = converter.convert(raw, lake, datasets=["cosif"])
    assert (r2.converted, r2.errors) == (N_COSIF, [])
    r3 = converter.convert(raw, lake, datasets=["cosif"])
    assert (r3.converted, r3.skipped) == (0, N_COSIF)


def _versao_de_contrato(lake: Path, dataset: str) -> set[str | None]:
    versoes = set()
    for arq in (lake / "bcb-microdados" / dataset).rglob("*.parquet"):
        meta = pq.ParquetFile(arq).metadata.metadata or {}
        versoes.add(meta.get(b"quantilica.contract.version", b"").decode() or None)
    return versoes


@pytest.mark.parametrize(
    ("bruto", "alvos", "esperado"),
    [
        (_scr_bruto, ["scr"], 3),
        (_estban_bruto, ["estban_municipio", "estban_agencia"], 2),
        (_olinda_bruto, ["pix_municipio_transacoes"], 1),
    ],
)
def test_revisao_de_layout_nova_reconverte_uma_vez(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    leituras: list[str],
    bruto,  # noqa: ANN001
    alvos: list[str],
    esperado: int,
) -> None:
    raw, lake = bruto(tmp_path), tmp_path / "lake"
    r1 = converter.convert(raw, lake, datasets=alvos)
    assert (r1.converted, r1.errors) == (esperado, [])
    assert _versao_de_contrato(lake, alvos[0]) == {None}  # revisão 1: nada novo

    monkeypatch.setattr(lake_mod, "LAYOUT_REVISION", 2)
    r2 = converter.convert(raw, lake, datasets=alvos)
    assert (r2.converted, r2.errors) == (esperado, [])
    assert _versao_de_contrato(lake, alvos[0]) == {"2"}

    leituras.clear()
    r3 = converter.convert(raw, lake, datasets=alvos)
    assert (r3.converted, r3.skipped, r3.errors) == (0, esperado, [])
    assert leituras == []
