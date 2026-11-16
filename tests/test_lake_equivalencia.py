"""Prova de equivalência: o cosif tem o mesmo conteúdo antes e depois do agrupamento.

``golden/lake_antes_do_agrupamento.json`` foi gerado pelo conversor de um Parquet
por membro de ZIP (commit anterior à mudança). Aqui o conversor atual lê os mesmos
brutos e o retrato do lake, por segmento e mês, e dentro do mês por esquema (linhas,
colunas e tipos, hash do conteúdo ordenado), tem de ser idêntico.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")

from bcb_microdados_fetcher.lake import converter  # noqa: E402

from .lake_fixtures import (  # noqa: E402
    GOLDEN,
    build_raw,
    contagem_de_arquivos,
    snapshot,
)


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _viaje_json(obj: dict) -> dict:
    return json.loads(json.dumps(obj, ensure_ascii=False))


def test_conteudo_do_lake_igual_ao_do_conversor_anterior(tmp_path: Path) -> None:
    build_raw(tmp_path / "raw")
    res = converter.convert(tmp_path / "raw", tmp_path / "lake")
    assert not res.errors
    assert res.converted == _golden()["convertidos"]

    atual = _viaje_json(snapshot(tmp_path / "lake"))
    golden = _golden()["lake"]

    assert sorted(atual) == sorted(golden)
    for periodo, esperado in golden.items():
        obtido = atual[periodo]
        assert sorted(obtido) == sorted(esperado), periodo
        for assinatura, dados in esperado.items():
            assert obtido[assinatura] == {
                **dados,
                "amostra": obtido[assinatura]["amostra"],
            }, (periodo, assinatura)
            assert obtido[assinatura]["amostra"] == dados["amostra"], periodo


def test_um_parquet_por_segmento_mes_e_esquema(tmp_path: Path) -> None:
    build_raw(tmp_path / "raw")
    converter.convert(tmp_path / "raw", tmp_path / "lake")

    depois = contagem_de_arquivos(tmp_path / "lake")
    antes = _golden()["contagem_de_arquivos"]

    assert sorted(depois) == sorted(antes)
    # Antes: um Parquet por membro (10 nas fixtures). Depois: um por segmento, mês e
    # esquema (8): o ZIP de três membros iguais vira um arquivo, e os dois esquemas
    # de cooperativas no mesmo mês continuam em dois.
    assert sum(antes.values()) == 10
    assert sum(depois.values()) == 8
    assert antes["bancos/202412"] == 3 and depois["bancos/202412"] == 1
    assert antes["cooperativas/202412"] == depois["cooperativas/202412"] == 2
    lake = tmp_path / "lake" / "bcb-microdados" / "cosif"
    nomes = sorted(str(p.relative_to(lake)) for p in lake.rglob("*.parquet"))
    assert "segmento=bancos/ano=2024/mes=12/cosif_bancos_202412.parquet" in nomes
    assert (
        "segmento=cooperativas/ano=2024/mes=12/cosif_cooperativas_202412.parquet"
        in nomes
    )
    assert (
        "segmento=cooperativas/ano=2024/mes=12/cosif_cooperativas_202412-v2.parquet"
        in nomes
    )


def test_lake_profile_devolve_periodo_mensal_do_cosif(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    from quantilica.core.lake_profile import profile_from_lake

    build_raw(tmp_path / "raw")
    converter.convert(tmp_path / "raw", tmp_path / "lake")

    perfil = profile_from_lake(tmp_path / "lake", "bcb-microdados", "cosif").perfil

    assert perfil["granularidade"] == "mensal"
    assert perfil["periodos"] == [
        "1995-01",
        "2009-01",
        "2024-11",
        "2024-12",
        "2025-01",
        "2026-06",
    ]
    assert perfil["linhas"] == [6, 2, 5, 17, 4, 5201]
    assert "saldo" in perfil["colunas"]
