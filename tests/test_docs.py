"""Documentação dos dados conforme a norma (normas/documentacao-dados no site)."""

from pathlib import Path

import pytest

docs = pytest.importorskip("quantilica.core.docs")
pytest.importorskip("yaml")

from bcb_microdados_fetcher.lake import converter  # noqa: E402


def test_documentacao_dos_dados() -> None:
    docs.assert_fetcher_docs(
        Path(__file__).parents[1] / "docs", converter.datasets(), converter.source_id
    )
