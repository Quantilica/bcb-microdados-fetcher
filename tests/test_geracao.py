"""Download com data de geração anterior à da versão vigente é descartado."""

from __future__ import annotations

import datetime as dt
import zipfile
from pathlib import Path
from typing import Any

import pytest
from quantilica.cli.sdk import FetcherApp

from bcb_microdados_fetcher.geracao import (
    data_geracao,
    manter_geracao_vigente,
    versao_vigente_anterior,
)
from bcb_microdados_fetcher.plugin import fetcher


def _arquivo(pasta: Path, nome: str, geracao: str | None, corpo: str = "x") -> Path:
    cab = f"ESTBAN (Documento 4500)\nData de geracao dos dados: {geracao}\n"
    texto = (cab if geracao else "ESTBAN\n") + "#DATA_BASE;UF\n" + corpo + "\n"
    path = pasta / nome
    if nome.endswith(".zip"):
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("202307_ESTBAN_AG.CSV", texto.encode("latin-1"))
    else:
        path.write_bytes(texto.encode("latin-1"))
    Path(f"{path}.manifest.json").write_text("{}")
    return path


def test_data_geracao_de_zip_csv_e_sem_data(tmp_path: Path) -> None:
    assert data_geracao(_arquivo(tmp_path, "a@20260101.zip", "2024-03-21")) == (
        dt.date(2024, 3, 21)
    )
    assert data_geracao(_arquivo(tmp_path, "b@20260101.csv", "2023-10-24")) == (
        dt.date(2023, 10, 24)
    )
    assert data_geracao(_arquivo(tmp_path, "c@20260101.zip", None)) is None
    (tmp_path / "d@20260101.zip").write_bytes(b"PK\x03\x04quebrado")
    assert data_geracao(tmp_path / "d@20260101.zip") is None


def test_versao_vigente_anterior_pega_o_carimbo_mais_novo_abaixo(
    tmp_path: Path,
) -> None:
    _arquivo(tmp_path, "estban_agencia_2023-07@20230101.zip", "2023-01-01")
    meio = _arquivo(tmp_path, "estban_agencia_2023-07@20240322.zip", "2024-03-21")
    _arquivo(tmp_path, "estban_agencia_2023-08@20250101.zip", "2025-01-01")  # outro mês
    novo = _arquivo(tmp_path, "estban_agencia_2023-07@20261123.zip", "2023-10-16")
    assert versao_vigente_anterior(novo) == meio
    primeiro = tmp_path / "estban_agencia_2023-07@20230101.zip"
    assert versao_vigente_anterior(primeiro) is None


def test_geracao_anterior_e_descartada_com_o_sidecar(tmp_path: Path) -> None:
    vigente = _arquivo(tmp_path, "estban_agencia_2023-06@20240201.zip", "2024-02-01")
    novo = _arquivo(tmp_path, "estban_agencia_2023-06@20261123.zip", "2023-10-16")
    assert manter_geracao_vigente(novo) == vigente
    assert not novo.exists()
    assert not Path(f"{novo}.manifest.json").exists()
    assert vigente.exists() and Path(f"{vigente}.manifest.json").exists()


@pytest.mark.parametrize(
    ("vigente", "novo"),
    [
        ("2024-02-01", "2024-02-01"),  # mesma geração (só mudou o formato)
        ("2024-02-01", "2024-03-01"),  # mais nova
        (None, "2023-10-16"),  # a vigente não tem data
        ("2024-02-01", None),  # a nova não tem data
    ],
)
def test_geracao_igual_nova_ou_sem_data_vale(
    tmp_path: Path, vigente: str | None, novo: str | None
) -> None:
    _arquivo(tmp_path, "estban_agencia_2023-06@20240201.csv", vigente)
    baixado = _arquivo(tmp_path, "estban_agencia_2023-06@20261123.zip", novo)
    assert manter_geracao_vigente(baixado) == baixado
    assert baixado.exists()


def test_primeiro_download_sem_versao_anterior_vale(tmp_path: Path) -> None:
    novo = _arquivo(tmp_path, "estban_agencia_2026-07@20261123.zip", "2026-11-03")
    assert manter_geracao_vigente(novo) == novo


def test_fetcher_descarta_o_download_regressivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ``_download_file`` do fetcher passa pelo descarte (HTTP trocado por stub)."""
    vigente = _arquivo(tmp_path, "estban_agencia_2023-06@20240201.zip", "2024-02-01")

    def baixa(self: Any, url: str, output: Path, *a: Any, **k: Any) -> Path:
        return _arquivo(output.parent, output.name, "2023-10-16")

    monkeypatch.setattr(FetcherApp, "_download_file", baixa)
    destino = tmp_path / "estban_agencia_2023-06@20261123.zip"
    assert fetcher._download_file("http://x/y.zip", destino) == vigente
    assert not destino.exists()

    saida = tmp_path / "estban_agencia_2023-05@20261123.zip"
    assert fetcher._download_file("http://x/z.zip", saida) == saida  # sem anterior
