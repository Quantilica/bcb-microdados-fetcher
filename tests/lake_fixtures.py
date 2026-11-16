"""Brutos sintéticos do Cosif e retrato do lake, para a prova de equivalência.

``build_raw`` monta ZIPs no formato real do bruto do fetcher
(``cosif_<segmento>_<AAAA-MM>@<AAAAMMDD>.zip`` com CSV em cp1252), cobrindo o que o
conversor trata: layouts de 1995 (``DATA;...;ATRIBUTO``), de 2024 e do plano de 2025,
largura fixa de 2009 (conglomerados), mês sem dados (consórcios), prudencial com
CNPJ alfanumérico depois da janela de inferência, ZIP com três membros do mesmo
esquema e ZIP com dois membros de esquemas diferentes no mesmo mês e segmento.

``snapshot`` descreve o lake, lendo cada Parquet direto (sem hive), por segmento e
mês da data-base e, dentro do mês, por esquema (colunas e tipos): número de linhas,
colunas, hash do conteúdo ordenado e uma amostra. Vale para as duas pastas
(``segmento=/ano=`` do conversor antigo, com um Parquet por membro, e
``segmento=/ano=/mes=``, com um por mês e esquema).
``golden/lake_antes_do_agrupamento.json`` foi gerado pelo conversor de um
Parquet por membro, antes da mudança:

    uv run --no-sync python -m tests.lake_fixtures --escrever-golden
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

GOLDEN = Path(__file__).parent / "golden" / "lake_antes_do_agrupamento.json"

_CAB_L11 = (
    "#DATA_BASE;DOCUMENTO;CNPJ;AGENCIA;NOME_INSTITUICAO;COD_CONGL;NOME_CONGL;"
    "TAXONOMIA;CONTA;NOME_CONTA;SALDO\n"
)
_CAB_L8 = "DATA;CNPJ;NOME INSTITUICAO;ATRIBUTO;DOCUMENTO;CONTA;NOME CONTA;SALDO\n"
_CAB_SEM_AGENCIA = (
    "#DATA_BASE;DOCUMENTO;CNPJ;NOME_INSTITUICAO;TAXONOMIA;CONTA;NOME_CONTA;SALDO\n"
)
_CAB_LARGURA = (
    "DATA;COD.CONGLOMERADO;NOME CONGLOMERADO;ATRIBUTO;DOCUMENTO;CONTA;"
    "NOME CONTA;SALDO\n"
)
_PREAMBULO = "Balancete Patrimonial COSIF\nData de geracao dos dados: x\nFonte: BCB\n"

_NOMES = ["BANCO AÇÃO S/A", "D'AGUA CRÉDITO", 'COOP "UNIÃO"', "CAIXA ECONÔMICA"]


def _l11(data: str, n: int, *, doc: str = "4010", cnpj0: int = 0) -> str:
    linhas = [
        f"{data};{doc};{cnpj0 + i:08d};0001;{_NOMES[i % 4]};0;NENHUM;0;"
        f"{(11112222 if data < '202501' else 1000000009) + i};CAIXA {i};"
        f"{1000 + i * 37},{i % 100:02d}\n"
        for i in range(n)
    ]
    return _PREAMBULO + _CAB_L11 + "".join(linhas)


def _l8(data: str, n: int) -> str:
    linhas = [
        f"{data};{i:08d};{_NOMES[i % 4]};U;4010;00{11112222 + i};CAIXA {i}; "
        f"{i:012d}{5555 + i},50\n"
        for i in range(n)
    ]
    return _PREAMBULO + _CAB_L8 + "".join(linhas)


def _sem_agencia(data: str, n: int) -> str:
    linhas = [
        f"{data};4010;{i:08d};{_NOMES[i % 4]};COOPERATIVAS DE CREDITO;"
        f"{11112222 + i};CAIXA {i};{200 + i},25\n"
        for i in range(n)
    ]
    return _PREAMBULO + _CAB_SEM_AGENCIA + "".join(linhas)


def _prudencial(data: str) -> str:
    linha = (
        "{d};4060;{cnpj};;{nome};{congl};X - PRUDENCIAL;CONGLOMERADO PRUDENCIAL;"
        "1000000009;Ativo;{v},50\n"
    )
    corpo = "".join(
        linha.format(
            d=data, cnpj="00000000", nome="BCO DO BRASIL S.A.", congl="C0080329", v=i
        )
        for i in range(5200)
    )
    corpo += linha.format(
        d=data, cnpj="C0085111", nome="", congl="C0085111", v=7
    )  # depois da janela de inferência
    return _PREAMBULO + _CAB_L11 + corpo


_LARGURA = (
    "Consolidado Financeiro (doc 4040)\nx\ny\n" + _CAB_LARGURA
    + "200901;00010045;BRADESCO     ;G;4040;0010000007;CIRCULANTE     ; "
    "0000363577595065,18\n"
    "200901;00010045;BRADESCO     ;G;4040;0090900000;CONTROLE       ;"
    "-0000000005840912,56\n"
)  # fmt: skip

_MARCADOR = (
    "Balancete Patrimonial\nx\ny\n"
    "DATA;CNPJ;NOME INSTITUICAO;ATRIBUTO;DOCUMENTO;CONTA;NOME CONTA;SALDO\n"
    "200901 ******** NAO EXISTE DADOS PARA ESTE SEGMENTO DATA"
    "******************** H      \r\n"
)

# (nome do ZIP sem carimbo, [(membro, conteúdo)])
PLANO: list[tuple[str, list[tuple[str, str]]]] = [
    ("cosif_bancos_1995-01", [("199501BANCOS.csv", _l8("199501", 6))]),
    ("cosif_bancos_2024-11", [("202411BANCOS.csv", _l11("202411", 5))]),
    (
        "cosif_bancos_2024-12",
        [
            ("202412BANCOS_1.csv", _l11("202412", 4, cnpj0=100)),
            ("202412BANCOS_2.csv", _l11("202412", 3, doc="4016", cnpj0=200)),
            ("202412BANCOS_3.csv", _l11("202412", 2, cnpj0=300)),
        ],
    ),
    ("cosif_bancos_2025-01", [("202501BANCOS.csv", _l11("202501", 4))]),
    (
        "cosif_cooperativas_2024-12",
        [
            ("202412COOPERATIVAS_A.csv", _l11("202412", 5, cnpj0=500)),
            ("202412COOPERATIVAS_B.csv", _sem_agencia("202412", 3)),
        ],
    ),
    ("cosif_prudencial_2026-06", [("202606BLOPRUDENCIAL.CSV", _prudencial("202606"))]),
    ("cosif_conglomerados_2009-01", [("200901CONGLOMERADOS.CSV", _LARGURA)]),
    ("cosif_consorcios_2009-01", [("200901CONSORCIOS.CSV", _MARCADOR)]),
]


def build_raw(root: Path) -> list[Path]:
    """Cria ``root/cosif/*.zip`` e devolve os caminhos."""
    pasta = root / "cosif"
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for nome, membros in PLANO:
        path = pasta / f"{nome}@20261101.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for membro, texto in membros:
                zf.writestr(membro, texto.encode("cp1252"))
        caminhos.append(path)
    return caminhos


def _sha(linhas: list[list[str]]) -> str:
    return hashlib.sha256(
        json.dumps(linhas, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def snapshot(lake_dir: Path) -> dict[str, Any]:
    """Retrato do cosif por segmento e mês, independente da pasta e dos arquivos."""
    import polars as pl

    base = lake_dir / "bcb-microdados" / "cosif"
    acumulado: dict[str, dict[str, dict[str, Any]]] = {}
    for arquivo in sorted(base.rglob("*.parquet")):
        chaves = dict(
            p.split("=", 1) for p in arquivo.relative_to(base).parts[:-1] if "=" in p
        )
        df = pl.read_parquet(arquivo, hive_partitioning=False)
        if "_origem" in df.columns:
            df = df.drop("_origem")
        meses = df["data_base"].cast(pl.String).str.slice(0, 6).unique().to_list()
        assert len(meses) == 1, (arquivo, meses)  # um mês por arquivo, nas fixtures
        comp = meses[0]
        assert comp[:4] == str(chaves["ano"]), (arquivo, comp)
        if "mes" in chaves:
            assert comp[4:] == f"{int(chaves['mes']):02d}", (arquivo, comp)
        df = df.select(sorted(df.columns))
        assinatura = "|".join(f"{c}:{t}" for c, t in df.schema.items())
        slot = acumulado.setdefault(f"{chaves['segmento']}/{comp}", {}).setdefault(
            assinatura,
            {"linhas": 0, "arquivos": 0, "conteudo": [], "colunas": df.schema},
        )
        slot["linhas"] += df.height
        slot["arquivos"] += 1
        slot["conteudo"].extend(
            ["" if v is None else str(v) for v in row] for row in df.rows()
        )
    saida: dict[str, Any] = {}
    for periodo, esquemas in sorted(acumulado.items()):
        saida[periodo] = {}
        for assinatura, dados in sorted(esquemas.items()):
            conteudo = sorted(dados["conteudo"])
            saida[periodo][assinatura] = {
                "linhas": dados["linhas"],
                "colunas": [[c, str(t)] for c, t in dados["colunas"].items()],
                "conteudo_sha256": _sha(conteudo),
                "amostra": conteudo[:3],
            }
    return saida


def contagem_de_arquivos(lake_dir: Path) -> dict[str, int]:
    """Parquets por segmento e mês da data-base (``segmento/AAAAMM``)."""
    import polars as pl

    base = lake_dir / "bcb-microdados" / "cosif"
    saida: dict[str, int] = {}
    for arquivo in sorted(base.rglob("*.parquet")):
        seg = next(
            p.split("=", 1)[1] for p in arquivo.relative_to(base).parts if "=" in p
        )
        comp = str(pl.read_parquet(arquivo, hive_partitioning=False)["data_base"][0])
        chave = f"{seg}/{comp[:6]}"
        saida[chave] = saida.get(chave, 0) + 1
    return dict(sorted(saida.items()))


def _escrever_golden() -> None:
    from bcb_microdados_fetcher.lake import converter

    with tempfile.TemporaryDirectory(prefix="cosif-golden-") as tmp:
        raiz = Path(tmp)
        build_raw(raiz / "raw")
        resultado = converter.convert(raiz / "raw", raiz / "lake")
        assert not resultado.errors, resultado.errors
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(
                {
                    "convertidos": resultado.converted,
                    "contagem_de_arquivos": contagem_de_arquivos(raiz / "lake"),
                    "lake": snapshot(raiz / "lake"),
                },
                ensure_ascii=False,
                indent=1,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"golden escrito em {GOLDEN}")


if __name__ == "__main__":
    if "--escrever-golden" not in sys.argv:
        raise SystemExit(__doc__)
    _escrever_golden()
