"""Tests for bcb-microdados-fetcher catalog."""

import pytest

from bcb_microdados_fetcher.catalog import GROUP_ALIASES, GROUPS, list_datasets


def test_list_datasets_all() -> None:
    """Test listing all datasets."""
    datasets = list_datasets()
    assert isinstance(datasets, list)


def test_list_datasets_by_group() -> None:
    """Test listing datasets by valid and invalid group."""
    for group in GROUPS:
        entries = list_datasets(group)
        assert isinstance(entries, list)

    for alias in GROUP_ALIASES:
        entries = list_datasets(alias)
        assert isinstance(entries, list)

    with pytest.raises(ValueError, match="Grupo desconhecido"):
        list_datasets("grupo_inexistente_xyz")


def test_olinda_groups_entries_are_monthly_functions() -> None:
    pix = list_datasets("pix")
    assert pix[0]["id"] == "pix_municipio_transacoes_2020_11"
    assert pix[0]["url"] == (
        "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
        "TransacoesPixPorMunicipio(DataBase=@DataBase)?@DataBase=%27202011%27"
        "&$filter=AnoMes%20eq%20202011&$top=10000&$format=json"
    )
    assert pix[0]["ext"] == "json" and pix[0]["extra"]["stable_name"]
    # nada de entity set (_TransacoesPixPorMunicipio responde 500)
    assert all("/_" not in e["url"] for e in pix)

    scr = list_datasets("scr_sub_regiao")
    assert (scr[0]["year"], scr[0]["month"]) == (2006, 1)
    assert scr[0]["url"].endswith(
        "scr_sub_regiao(DataBase=@DataBase)?@DataBase=200601&$top=100000&$format=json"
    )
