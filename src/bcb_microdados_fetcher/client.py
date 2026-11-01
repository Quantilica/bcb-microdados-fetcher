"""HTTP and discovery client for Banco Central do Brasil microdata."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from quantilica.core.http import HttpClient
from quantilica.core.logging import get_logger
from quantilica.core.manifests import DownloadManifest

from .constants import (
    BCB_CONTEUDO_URL,
    BCB_DOCUMENTOS_URL,
)

logger = get_logger(__name__)


class BcbMicrodadosClient:
    """Client for discovering and downloading BCB microdata files."""

    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client or HttpClient()
        self.logger = logger or get_logger(__name__)

    def get_conteudo_site(self, identificador: str) -> dict[str, Any]:
        """Fetch list metadata (tronco and guidLista) for an identifier."""
        params = {"identificador": identificador}
        data = self.client.get_json(BCB_CONTEUDO_URL, params=params)
        if isinstance(data, dict):
            # Might be {"conteudo": [{"tronco": ..., "guidLista": ...}]} or direct
            items = data.get("conteudo")
            if isinstance(items, list) and items:
                return items[0]
            return data
        return {}

    def list_documentos(
        self,
        *,
        tronco: str,
        guid_lista: str,
        pasta: str,
        qtd_itens: int = 9999,
    ) -> list[dict[str, Any]]:
        """List documents inside a pasta using Documentos/byListGuid."""
        params = {
            "tronco": tronco,
            "guidLista": guid_lista,
            "pasta": pasta,
            "ordem": "DataDocumento desc",
            "qtditens": qtd_itens,
        }
        try:
            data = self.client.get_json(BCB_DOCUMENTOS_URL, params=params)
            if isinstance(data, dict):
                items = data.get("conteudo", [])
                if isinstance(items, list):
                    return items
        except Exception as exc:
            self.logger.warning("Erro ao listar documentos da pasta %s: %s", pasta, exc)
        return []

    def download_file(
        self,
        url: str,
        dest: Path,
        *,
        manifest_path: Path | None = None,
    ) -> DownloadManifest:
        """Download file with SHA-256 manifest sidecar."""
        return self.client.download_with_manifest(
            url,
            dest,
            manifest_path=manifest_path,
        )
