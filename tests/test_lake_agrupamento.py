"""Agrupamento do cosif: segunda execução, migração, auditoria e limpeza."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from quantilica.analytics import lake_audit  # noqa: E402
from quantilica.analytics.lake import (  # noqa: E402
    META_MEMBERS,
    LakeWriter,
    check_dataset,
    scan_dataset,
)
from quantilica.core.lake import (  # noqa: E402
    DatasetDescriptor,
    composite_file_key,
    partition_types_for,
)

import bcb_microdados_fetcher.lake as lake_mod  # noqa: E402
from bcb_microdados_fetcher.lake import SOURCE_ID, converter  # noqa: E402

from .lake_fixtures import (  # noqa: E402
    GOLDEN,
    _l11,
    _sem_agencia,
    build_raw,
    contagem_de_arquivos,
    snapshot,
)

N_MEMBROS = 10


def _legacy_convert(raw: Path, lake: Path) -> None:
    """O conversor anterior: um Parquet por membro em ``segmento=/ano=``."""
    from quantilica.core.lake import select_current

    writer = LakeWriter(
        lake / SOURCE_ID / "cosif",
        DatasetDescriptor(
            source_id=SOURCE_ID,
            dataset_id="cosif",
            alias="cosif",
            partition_keys=["segmento", "ano"],
            partition_types=partition_types_for(["segmento", "ano"]),
        ),
    )
    for raw_file in sorted(select_current(list(raw.rglob("*.zip")))):
        for name in lake_mod._iter_members(raw_file):
            shown = name or raw_file.name
            with lake_mod._member_as_utf8(raw_file, name, "cp1252") as csv_path:
                built = lake_mod._cosif_build(csv_path, shown)
                if built is None:
                    continue
                lf, info = built
                writer.write_polars(
                    lf,
                    src=raw_file,
                    partitions={"segmento": info.segmento, "ano": info.ano},
                    file_key_name=composite_file_key(raw_file, name).lower(),
                )


def _dataset(lake: Path) -> Path:
    return lake / SOURCE_ID / "cosif"


def _parquets(lake: Path) -> list[Path]:
    return sorted(_dataset(lake).rglob("*.parquet"))


def _estado(lake: Path) -> dict[Path, tuple[int, int]]:
    return {p: (p.stat().st_mtime_ns, p.stat().st_ino) for p in _parquets(lake)}


def _members(path: Path) -> dict:
    return json.loads(pq.ParquetFile(path).metadata.metadata[META_MEMBERS.encode()])


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    build_raw(tmp_path / "raw")
    return tmp_path / "raw"


@pytest.fixture
def decodificacoes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Nomes dos membros decodificados por inteiro (não só o início do arquivo)."""
    vistas: list[str] = []
    original = lake_mod._cosif_build

    def espiar(csv_path, name):
        if csv_path.name == "membro.csv":
            vistas.append(name)
        return original(csv_path, name)

    monkeypatch.setattr(lake_mod, "_cosif_build", espiar)
    return vistas


def test_simulacao_do_conversor_antigo_bate_com_o_golden(
    raw: Path, tmp_path: Path
) -> None:
    """O auxiliar que recria o layout antigo é fiel: reproduz o golden commitado."""
    lake = tmp_path / "lake"
    _legacy_convert(raw, lake)

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(_parquets(lake)) == sum(golden["contagem_de_arquivos"].values())
    assert json.loads(json.dumps(snapshot(lake), ensure_ascii=False)) == golden["lake"]


def test_membros_do_grupo_no_rodape_e_origem_nas_linhas(
    raw: Path, tmp_path: Path
) -> None:
    lake = tmp_path / "lake"
    res = converter.convert(raw, lake)
    assert not res.errors and res.converted == N_MEMBROS and res.skipped == 0

    arquivo = _dataset(lake) / "segmento=bancos/ano=2024/mes=12"
    arquivo = arquivo / "cosif_bancos_202412.parquet"
    membros = _members(arquivo)
    assert sorted(membros) == [
        "cosif_bancos_2024-12__202412bancos_1",
        "cosif_bancos_2024-12__202412bancos_2",
        "cosif_bancos_2024-12__202412bancos_3",
    ]
    assert sorted(m["rows"] for m in membros.values()) == [2, 3, 4]
    assert all(
        m["origin_sha256"]
        and m["contract_version"] == 1
        and m["converter_version"] == "1"
        for m in membros.values()
    )
    df = scan_dataset(_dataset(lake) / "segmento=bancos").collect()
    assert df.filter(df["mes"] == "12").height == 9
    assert check_dataset(_dataset(lake)) == []


def test_segunda_execucao_pula_tudo_sem_reescrever_nem_decodificar(
    raw: Path, tmp_path: Path, decodificacoes: list[str]
) -> None:
    lake = tmp_path / "lake"
    assert converter.convert(raw, lake).converted == N_MEMBROS
    assert len(decodificacoes) == N_MEMBROS
    decodificacoes.clear()
    antes = _estado(lake)

    res = converter.convert(raw, lake)

    assert not res.errors
    assert (res.converted, res.skipped) == (0, N_MEMBROS)
    assert decodificacoes == []  # só o início de cada membro é lido
    assert _estado(lake) == antes  # nenhum arquivo reescrito
    assert not list(_dataset(lake).rglob(".tmp/*"))


def test_zip_alterado_reescreve_so_o_mes_e_decodifica_so_o_membro(
    raw: Path, tmp_path: Path, decodificacoes: list[str]
) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    decodificacoes.clear()
    antes = _estado(lake)

    # O membro B (esquema sem AGENCIA) de cooperativas de 2024-12 muda.
    zip_coop = raw / "cosif/cosif_cooperativas_2024-12@20261101.zip"
    with zipfile.ZipFile(zip_coop, "w") as zf:
        zf.writestr(
            "202412COOPERATIVAS_A.csv", _l11("202412", 5, cnpj0=500).encode("cp1252")
        )
        zf.writestr(
            "202412COOPERATIVAS_B.csv", _sem_agencia("202412", 4).encode("cp1252")
        )
    res = converter.convert(raw, lake)

    assert not res.errors
    # O ZIP inteiro mudou (o sha256 é do ZIP): os dois membros são reconvertidos,
    # e nenhum outro grupo é tocado.
    assert res.converted == 2 and res.skipped == N_MEMBROS - 2
    assert sorted(n for n in decodificacoes) == [
        "202412COOPERATIVAS_A.csv",
        "202412COOPERATIVAS_B.csv",
    ]
    depois = _estado(lake)
    mudou = {p.name for p in depois if depois[p] != antes.get(p)}
    assert mudou == {
        "cosif_cooperativas_202412.parquet",
        "cosif_cooperativas_202412-v2.parquet",
    }
    df = scan_dataset(_dataset(lake) / "segmento=cooperativas").collect()
    assert df.height == 5 + 4


def test_zip_que_sai_do_bruto_sai_do_arquivo_do_mes(raw: Path, tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    (raw / "cosif/cosif_bancos_2024-12@20261101.zip").unlink()
    zip_novo = raw / "cosif/cosif_bancos_2024-12@20261102.zip"
    with zipfile.ZipFile(zip_novo, "w") as zf:
        zf.writestr("202412BANCOS_1.csv", _l11("202412", 4, cnpj0=100).encode("cp1252"))

    res = converter.convert(raw, lake)

    assert not res.errors
    arquivo = _dataset(lake) / "segmento=bancos/ano=2024/mes=12"
    arquivo = arquivo / "cosif_bancos_202412.parquet"
    assert len(_members(arquivo)) == 1
    assert pq.ParquetFile(arquivo).metadata.num_rows == 4


def test_mudanca_de_esquema_nao_deixa_grupo_obsoleto(raw: Path, tmp_path: Path) -> None:
    """Se os dois membros passam a ter o mesmo esquema, o ``-v2`` antigo sai."""
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    mes = _dataset(lake) / "segmento=cooperativas/ano=2024/mes=12"
    assert sorted(p.name for p in mes.glob("*.parquet")) == [
        "cosif_cooperativas_202412-v2.parquet",
        "cosif_cooperativas_202412.parquet",
    ]
    zip_coop = raw / "cosif/cosif_cooperativas_2024-12@20261101.zip"
    with zipfile.ZipFile(zip_coop, "w") as zf:
        zf.writestr(
            "202412COOPERATIVAS_A.csv", _l11("202412", 5, cnpj0=500).encode("cp1252")
        )
        zf.writestr(
            "202412COOPERATIVAS_B.csv", _l11("202412", 3, cnpj0=900).encode("cp1252")
        )

    res = converter.convert(raw, lake)

    assert not res.errors
    assert [p.name for p in mes.glob("*.parquet")] == [
        "cosif_cooperativas_202412.parquet"
    ]
    assert scan_dataset(_dataset(lake) / "segmento=cooperativas").collect().height == 8


def test_migracao_do_layout_antigo_sem_duplicar_linhas(
    raw: Path, tmp_path: Path
) -> None:
    lake = tmp_path / "lake"
    _legacy_convert(raw, lake)
    antigos = _parquets(lake)
    assert len(antigos) == N_MEMBROS
    assert all("mes=" not in str(p) for p in antigos)
    linhas_antes = scan_dataset(_dataset(lake)).collect().height

    res = converter.convert(raw, lake)

    assert not res.errors
    assert (res.converted, res.skipped) == (N_MEMBROS, 0)
    novos = _parquets(lake)
    assert len(novos) == 8
    assert all("mes=" in str(p) for p in novos)  # nenhum Parquet antigo sobrou
    df = scan_dataset(_dataset(lake)).collect()
    assert df.height == linhas_antes  # nenhuma linha duplicada
    assert check_dataset(_dataset(lake)) == []
    # Idempotente: a passada seguinte não mexe em nada.
    antes = _estado(lake)
    assert converter.convert(raw, lake).skipped == N_MEMBROS
    assert _estado(lake) == antes
    # E o conteúdo é o do golden (migrado == convertido do zero).
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(snapshot(lake), ensure_ascii=False)) == golden["lake"]


def test_migracao_nao_apaga_o_que_o_grupo_nao_cobre(raw: Path, tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    _legacy_convert(raw, lake)
    pasta = _dataset(lake) / "segmento=bancos/ano=2024"
    # Parquet de um ZIP que não está mais no bruto: o grupo não tem as linhas dele.
    orfao = pasta / "cosif_bancos_2024-10__202410bancos.parquet"
    shutil.copy2(pasta / "cosif_bancos_2024-11__202411bancos.parquet", orfao)
    # Arquivo com o nome de um membro, mas que não é deste dataset (sem rodapé).
    alheio = pasta / "cosif_bancos_2024-11__202411bancos.parquet"
    pq.write_table(pa.table({"x": [1]}), alheio)

    res = converter.convert(raw, lake)

    assert not res.errors
    assert orfao.exists() and alheio.exists()  # a auditoria é quem acusa o resíduo
    # Os três membros de 2024-12 saíram.
    assert sorted(p.name for p in pasta.glob("*.parquet")) == sorted(
        [orfao.name, alheio.name]
    )


def test_zip_ilegivel_e_erro_e_nao_descarta_nada(raw: Path, tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    antes = {p.name: pq.ParquetFile(p).metadata.num_rows for p in _parquets(lake)}
    (raw / "cosif/cosif_bancos_2024-12@20261101.zip").write_bytes(b"PK\x03\x04quebrado")

    res = converter.convert(raw, lake)

    assert len(res.errors) == 1 and "cosif_bancos_2024-12" in res.errors[0]
    depois = {p.name: pq.ParquetFile(p).metadata.num_rows for p in _parquets(lake)}
    assert depois == antes  # o mês com ZIP quebrado continua como estava


def _tira_marcador(entrada: Path) -> None:
    """O ZIP de mês sem dados não gera Parquet (e a auditoria o acusaria)."""
    (entrada / SOURCE_ID / "cosif/cosif_consorcios_2009-01@20261101.zip").unlink()


def test_auditoria_do_lake_agrupado(raw: Path, tmp_path: Path) -> None:
    # O lake_audit espera <fonte>/<pasta>/<arquivo> sob o diretório de entrada.
    entrada = tmp_path / "entrada"
    shutil.copytree(raw, entrada / SOURCE_ID)
    _tira_marcador(entrada)
    lake = tmp_path / "lake"
    res = converter.convert(entrada / SOURCE_ID, lake)
    assert not res.errors

    report = lake_audit(lake, input_dir=entrada, converters={}, rehash=True)

    assert report.ok, report.to_text()
    assert [f for f in report.findings if f.category == "membros_divergentes"] == []


def test_auditoria_do_lake_migrado(raw: Path, tmp_path: Path) -> None:
    entrada = tmp_path / "entrada"
    shutil.copytree(raw, entrada / SOURCE_ID)
    _tira_marcador(entrada)
    lake = tmp_path / "lake"
    _legacy_convert(entrada / SOURCE_ID, lake)
    converter.convert(entrada / SOURCE_ID, lake)

    report = lake_audit(lake, input_dir=entrada, converters={}, rehash=True)

    assert report.ok, report.to_text()


def test_conversao_nao_deixa_temporarios(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("QUANTILICA_LAKE_SCRATCH", str(scratch))
    lake = tmp_path / "lake"

    res = converter.convert(raw, lake)

    assert not res.errors
    # Só o diretório de derramamento do Polars (removido ao fim do processo).
    assert [p.name for p in scratch.iterdir() if not p.name.startswith("polars-")] == []
    assert not list(lake.rglob(".tmp"))
    assert contagem_de_arquivos(lake)


def test_force_reescreve_tudo_sem_duplicar(raw: Path, tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    converter.convert(raw, lake)
    linhas = scan_dataset(_dataset(lake)).collect().height

    res = converter.convert(raw, lake, force=True)

    assert not res.errors and res.converted == N_MEMBROS and res.skipped == 0
    assert len(_parquets(lake)) == 8
    assert scan_dataset(_dataset(lake)).collect().height == linhas
