"""Tests for BcbMicrodadosClient."""

from __future__ import annotations

from unittest.mock import patch

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


def test_cliente_padrao_e_o_do_host(monkeypatch) -> None:
    """Sem ``client=``, vale o ``default_client()`` do host (``QUANTILICA_HTTP_*``)."""
    monkeypatch.setenv("QUANTILICA_HTTP_ATTEMPTS", "2")
    monkeypatch.setenv("QUANTILICA_HTTP_TIMEOUT", "7")
    client = BcbMicrodadosClient()
    assert client.client.attempts == 2
    assert client.client.timeout == 7


def test_cliente_padrao_sem_host_respeita_ssl_do_ambiente(monkeypatch) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "quantilica.cli.sdk", None)  # host ausente
    monkeypatch.setenv("QUANTILICA_SSL_VERIFY", "0")
    assert BcbMicrodadosClient().client.verify is False
