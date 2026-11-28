"""HTTP and discovery client for Banco Central do Brasil microdata."""

from __future__ import annotations

import logging
import re
from typing import Any

from quantilica.core.http import HttpClient, HttpStatusError, resolve_verify_from_env
from quantilica.core.logging import get_logger

from .constants import (
    BCB_CONTEUDO_URL,
    BCB_DOCUMENTOS_URL,
)

logger = get_logger(__name__)


def _default_http_client() -> HttpClient:
    """Cliente padrão do host (``QUANTILICA_HTTP_*``, SSL, CA), com plano B do core."""
    try:
        from quantilica.cli.sdk import default_client
    except ImportError:  # CLI autônoma, sem o host instalado
        return HttpClient(verify=resolve_verify_from_env(), emulate_browser=True)
    return default_client()


class BcbMicrodadosClient:
    """Client for discovering BCB microdata files (o download é do ``sync`` do host)."""

    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client or _default_http_client()
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
        """List documents inside a pasta using Documentos/byListGuid.

        Levanta a exceção do cliente HTTP se a listagem falhar (quem chama decide
        entre contar o erro e seguir), e ``ValueError`` se a resposta não tiver o
        formato ``{"conteudo": [...]}``.
        """
        params = {
            "tronco": tronco,
            "guidLista": guid_lista,
            "pasta": pasta,
            "ordem": "DataDocumento desc",
            "qtditens": qtd_itens,
        }
        data = self.client.get_json(BCB_DOCUMENTOS_URL, params=params)
        items = data.get("conteudo") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError(f"Resposta inesperada da listagem de {pasta!r}")
        return items

    def url_exists(self, url: str) -> bool | None:
        """HEAD (ou GET só de cabeçalhos): ``True``/``False``, ``None`` se incerto.

        ``False`` só para 404 real; qualquer outra falha devolve ``None`` para que o
        chamador não trate indisponibilidade transitória como arquivo inexistente.
        """
        try:
            self.client.head_or_get(url)
            return True
        except HttpStatusError as exc:
            return False if exc.status_code == 404 else None
        except Exception as exc:
            self.logger.warning("HEAD %s falhou: %s", url, exc)
            return None

    def has_rows(self, url: str) -> bool | None:
        """Consulta OData com ``$top=1``: ``True`` se vier ao menos uma linha.

        ``False`` só para resposta válida com ``value`` vazio (mês ainda não
        publicado); falha de rede/HTTP devolve ``None`` (inconclusivo).
        """
        probe = re.sub(r"\$top=\d+", "$top=1", url)
        try:
            data = self.client.get_json(probe)
        except Exception as exc:
            self.logger.warning("consulta OData %s falhou: %s", probe, exc)
            return None
        value = data.get("value") if isinstance(data, dict) else None
        if not isinstance(value, list):
            return None
        return bool(value)
