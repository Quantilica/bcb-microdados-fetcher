"""O build sem mudança decide por sidecars e rodapés, sem transcodificar o bruto."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")

import quantilica.core.manifests as manifests  # noqa: E402

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
