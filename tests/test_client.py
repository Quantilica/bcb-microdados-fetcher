"""Tests for BcbMicrodadosClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quantilica.core.manifests import DownloadManifest

from bcb_microdados_fetcher.client import BcbMicrodadosClient


def test_client_init() -> None:
    client = BcbMicrodadosClient()
    assert client.client is not None


def test_get_conteudo_site() -> None:
    client = BcbMicrodadosClient()
    fake_payload = {"conteudo": [{"tronco": "estban_tronco", "guidLista": "guid-1234"}]}
    with patch.object(client.client, "get_json", return_value=fake_payload):
        res = client.get_conteudo_site("estatistica_bancaria_estban")
        assert res["tronco"] == "estban_tronco"
        assert res["guidLista"] == "guid-1234"


def test_list_documentos() -> None:
    client = BcbMicrodadosClient()
    fake_payload = {
        "conteudo": [
            {
                "Nome": "202606BANCOS.csv.zip",
                "Url": "https://bcb/202606BANCOS.csv.zip",
                "Tamanho": 123456,
            }
        ]
    }
    with patch.object(client.client, "get_json", return_value=fake_payload):
        docs = client.list_documentos(tronco="t", guid_lista="g", pasta="Bancos")
        assert len(docs) == 1
        assert docs[0]["Nome"] == "202606BANCOS.csv.zip"


def test_download_file(tmp_path) -> None:
    client = BcbMicrodadosClient()
    target = tmp_path / "test.zip"
    mock_manifest = MagicMock(spec=DownloadManifest)
    with patch.object(
        client.client, "download_with_manifest", return_value=mock_manifest
    ):
        res = client.download_file("https://bcb/test.zip", target)
        assert res == mock_manifest
