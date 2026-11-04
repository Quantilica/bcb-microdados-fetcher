"""Constants and definitions for bcb-microdados-fetcher."""

from __future__ import annotations

from typing import Any

BCB_BASE_URL = "https://www.bcb.gov.br"
BCB_CONTEUDO_URL = "https://www.bcb.gov.br/api/servico/sitebcb/conteudosite"
BCB_DOCUMENTOS_URL = "https://www.bcb.gov.br/api/servico/sitebcb/Documentos/byListGuid"
COSIF_IDENTIFICADOR = "cosif"
ESTBAN_IDENTIFICADOR = "estatistica_bancaria_estban"
SCR_URL_TEMPLATE = "https://www.bcb.gov.br/pda/desig/scrdata_{year}.zip"

# COSIF pastas / segmentos
COSIF_SEGMENTOS: dict[str, dict[str, Any]] = {
    "bancos": {
        "pasta": "Bancos",
        "sufixo": "BANCOS",
        "start_year": 1988,
        "end_year": None,
        "name": "Bancos e Caixas Econômicas",
    },
    "cooperativas": {
        "pasta": "Cooperativas-de-credito",
        "sufixo": "COOPERATIVAS",
        "start_year": 1988,
        "end_year": None,
        "name": "Cooperativas de Crédito",
    },
    "consorcios": {
        "pasta": "Administradoras-de-consorcios",
        "sufixo": "CONSORCIOS",
        "start_year": 1988,
        "end_year": None,
        "name": "Administradoras de Consórcios",
    },
    "sociedades": {
        "pasta": "Sociedades",
        "sufixo": "SOCIEDADES",
        "start_year": 1988,
        "end_year": None,
        "name": "Sociedades de Crédito, Financiamento e Investimento",
    },
    "conglomerados": {
        "pasta": "Conglomerados-financeiros",
        "sufixo": "CONGLOMERADOS",
        "start_year": 1988,
        "end_year": 2021,  # Descontinuado em 2021-12
        "name": "Conglomerados Financeiros (Descontinuado)",
    },
    "prudencial": {
        "pasta": "Conglomerados-prudenciais",
        "sufixo": "BLOPRUDENCIAL",
        "start_year": 2014,
        "end_year": None,
        "name": "Conglomerados Prudenciais",
    },
    "combinados": {
        "pasta": "Combinados-cooperativos",
        "sufixo": "COMBINADOS",
        "start_year": 2013,
        "end_year": None,
        "name": "Combinados Cooperativos",
    },
    "liquidacao": {
        "pasta": "Instituicoes-em-regime-especial",
        "sufixo": "LIQUIDACAO",
        "start_year": 1988,
        "end_year": None,
        "name": "Instituições em Regime Especial / Liquidação",
    },
}

ESTBAN_PASTAS: dict[str, dict[str, Any]] = {
    "municipio": {
        "pasta": "municipio",
        "prefixo": "ESTBAN",
        "start_year": 1988,
        "name": "Estatística Bancária por Município (Documento 4500)",
    },
    "agencia": {
        "pasta": "agencia",
        "prefixo": "ESTBAN_AG",
        "start_year": 1988,
        "name": "Estatística Bancária por Agência (Documento 4500)",
    },
}

SCR_START_YEAR = 2012


def moeda_for_date(year: int, month: int) -> str:
    """Return official currency standard for a given date in Brazil."""
    key = (year, month)
    if key <= (1988, 12):
        return "Cz$"
    if key <= (1990, 2):
        return "NCz$"
    if key <= (1993, 7):
        return "Cr$"
    if key <= (1994, 6):
        return "CR$"
    return "R$"
