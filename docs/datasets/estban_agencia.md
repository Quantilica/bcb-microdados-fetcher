---
dataset:
  id: estban_agencia
  fonte: bcb-microdados
  titulo: ESTBAN por agência
  resumo: Estatística Bancária Mensal, saldos de cada verbete por agência bancária, em formato longo.
  orgao: Banco Central do Brasil (BCB)
  pagina_oficial: https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios
  licenca: "Não declarada na página da ESTBAN. Os conjuntos do BCB no portal de dados abertos (dadosabertos.bcb.gov.br) usam a Open Data Commons Open Database License (ODbL): http://www.opendefinition.org/licenses/odc-odbl"
  periodicidade: mensal; publicação trimestral desde o Comunicado 44.132/2025, e cada publicação reabrange os últimos seis meses
  cobertura: {inicio: 1988-07, fim: em-curso}
  unidade: saldo de um verbete da ESTBAN de uma agência bancária, numa data-base
  granularidade: {espacial: agência (com município e UF), temporal: mês}
  formato_bruto: ZIP com um CSV por mês (documento 4500), separado por ponto e vírgula, latin-1, duas linhas de preâmbulo e uma coluna por verbete (formato largo)
  lake: {estado: convertido, particoes: [ano, mes], chave: [data_base, agencia, verbete_codigo], colunas: 12}
  unidades_de_medida:
    valor: moeda da data-base (coluna moeda), sem centavos
    data_base: AAAAMM
    codmun: código de município do BCB
    codmun_ibge: código IBGE de município (7 dígitos)
  dados_pessoais: nenhum
  eras:
    - {desde: 1989-01, mudanca: "valores em cruzado novo (NCz$); antes, cruzado (Cz$)"}
    - {desde: 1990-03, mudanca: "valores em cruzeiro (Cr$)"}
    - {desde: 1993-08, mudanca: "valores em cruzeiro real (CR$)"}
    - {desde: 1994-07, mudanca: "valores em real (R$)"}
    - {desde: 2022-07, mudanca: "12 verbetes deixam de ser publicados; 167+168 passa a 167 e 461+462+463+467+468 passa a 461+467+468"}
  revisado_em: 2026-11-07
  versao_fetcher: 0.4.0
---

# ESTBAN por agência

## Resumo

A versão por agência da Estatística Bancária Mensal (ESTBAN) traz os mesmos verbetes da [ESTBAN por município](estban_municipio.md), mas abertos por agência: cada linha é o saldo de um verbete em uma agência, identificada pelo CNPJ completo. Serve para estudar a rede de agências, a concentração bancária local e a distribuição do crédito e da captação dentro dos municípios.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `bcb-microdados/estban_agencia` |
| Órgão | Banco Central do Brasil (BCB) |
| Página oficial | https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios |
| Licença | Não declarada na página da ESTBAN. Os conjuntos do BCB no portal de dados abertos (dadosabertos.bcb.gov.br) usam a Open Data Commons Open Database License (ODbL): http://www.opendefinition.org/licenses/odc-odbl |
| Periodicidade | mensal; publicação trimestral desde o Comunicado 44.132/2025, e cada publicação reabrange os últimos seis meses |
| Cobertura | 1988-07 a em-curso |
| Unidade (uma linha) | saldo de um verbete da ESTBAN de uma agência bancária, numa data-base |
| Granularidade | espacial: agência (com município e UF); temporal: mês |
| Formato bruto | ZIP com um CSV por mês (documento 4500), separado por ponto e vírgula, latin-1, duas linhas de preâmbulo e uma coluna por verbete (formato largo) |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `data_base`, `agencia`, `verbete_codigo` |
| Colunas | 12 |
| Unidades de medida | `valor`: moeda da data-base (coluna moeda), sem centavos; `data_base`: AAAAMM; `codmun`: código de município do BCB; `codmun_ibge`: código IBGE de município (7 dígitos) |
| Dados pessoais | nenhum |
| Eras | 1989-01: valores em cruzado novo (NCz$); antes, cruzado (Cz$); 1990-03: valores em cruzeiro (Cr$); 1993-08: valores em cruzeiro real (CR$); 1994-07: valores em real (R$); 2022-07: 12 verbetes deixam de ser publicados; 167+168 passa a 167 e 461+462+463+467+468 passa a 461+467+468 |
| Revisado em | 2026-11-07 |
| Versão do fetcher | 0.4.0 |

## Origem e coleta

- O fetcher lista os arquivos pela API de conteúdo do site do BCB (identificador `estatistica_bancaria_estban`, pasta `agencia`) e baixa a `Url` informada.
- Na fonte, cada mês é um ZIP com um CSV de preâmbulo de duas linhas e cabeçalho `#DATA_BASE`; a coluna `AGENCIA` vem com um apóstrofo na frente (`'00000000517569`). No bruto, o fetcher grava `estban_agencia_<AAAA-MM>@<AAAAMMDD>.zip`.
- Cada publicação reabrange os últimos seis meses; o lake converte a versão mais recente de cada mês.
- Em 2026-11-06, o fetcher tinha coletado 456 arquivos por agência; o mais recente é de 2026-06.

## Conteúdo

- Uma linha por agência, data-base e verbete. Em 2026-06 são 13.119 agências e 45 verbetes (conferido em 2026-11-07).
- Os verbetes e suas mudanças são os mesmos da ESTBAN por município; a tabela completa está em [estban_municipio](estban_municipio.md#conteúdo).
- Diferente do arquivo por município, não há contagem de agências (`AGEN_ESPERADAS`, `AGEN_PROCESSADAS`), e o verbete `153` tem valores até 2022-06.

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `data_base` | `#DATA_BASE` | inteiro | Data-base | AAAAMM | todo |
| `uf` | `UF` | texto | Unidade da federação da agência | sigla | todo |
| `codmun` | `CODMUN` | inteiro | Código do município no BCB (não é o do IBGE) | — | todo |
| `municipio` | `MUNICIPIO` | texto | Nome do município da agência | — | todo |
| `cnpj` | `CNPJ` | texto | Raiz do CNPJ da instituição | 8 dígitos | todo |
| `nome_instituicao` | `NOME_INSTITUICAO` | texto | Nome da instituição | — | todo |
| `agencia` | `AGENCIA` | texto | CNPJ completo da agência, sem o apóstrofo da fonte | 14 dígitos | todo |
| `codmun_ibge` | `CODMUN_IBGE` | inteiro | Código IBGE do município | 7 dígitos | todo |
| `verbete_codigo` | cabeçalho `VERBETE_<código>_<nome>` | texto | Código do verbete; soma de verbetes com `+` | ver [tabela de verbetes](estban_municipio.md#conteúdo) | todo |
| `verbete_nome` | cabeçalho `VERBETE_<código>_<nome>` | texto | Nome do verbete, normalizado; somas com `+` | — | todo |
| `valor` | coluna de cada verbete | inteiro | Saldo do verbete | moeda da data-base, sem centavos | todo |
| `moeda` | — (gerada) | texto | Padrão monetário da data-base | `Cz$`, `NCz$`, `Cr$`, `CR$`, `R$` | todo |
| `ano` | — (partição) | inteiro | Ano da data-base | — | todo |
| `mes` | — (partição) | inteiro | Mês da data-base | 1 a 12 | todo |

## No lake

- Dataset `bcb-microdados/estban_agencia`, particionado por `ano` e `mes`; um Parquet por mês.
- O formato largo da fonte vira formato longo (`verbete_codigo`, `verbete_nome`, `valor`).
- `agencia` perde o apóstrofo inicial e fica como texto de 14 dígitos; `cnpj` é texto.
- Textos perdem os espaços de preenchimento, e `moeda` é acrescentada a partir da data-base (desde a versão 0.4.0).

## Cuidados de uso

- **Não some todos os verbetes.** Há verbetes de total (`399`, `899`) e de grupo (`160`, com subitens como `161`, `162` e `169`).
- **Composição muda em 2022-07**, como na ESTBAN por município: `167+168` passa a `167`, `461+462+463+467+468` passa a `461+467+468` e 12 verbetes deixam de existir.
- **Moeda da época e sem centavos.** Até 1994-06 os valores estão em Cz$, NCz$, Cr$ ou CR$, sem conversão; a coluna `moeda` diz qual.
- **Contar agências pelo `agencia`, não pelas linhas.** Cada agência aparece uma vez por verbete; filtre um verbete (por exemplo `399`) antes de contar.
- **Revisões.** Cada publicação reabrange os seis meses anteriores; números de meses recentes podem mudar.

## Exemplos

Número de agências por instituição em um mês:

```python
import polars as pl

ag = pl.scan_parquet("lake/bcb-microdados/estban_agencia/**/*.parquet", hive_partitioning=True)
agencias = (
    ag.filter((pl.col("data_base") == 202506) & (pl.col("verbete_codigo") == "399"))
    .group_by("cnpj", "nome_instituicao")
    .agg(pl.col("agencia").n_unique().alias("agencias"))
    .sort("agencias", descending=True)
    .collect()
)
```

## Referências

- Estatística Bancária Mensal (BCB), com a descrição das colunas dos arquivos por município e por agência: https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios
- Cosif, capítulo 3, documento nº 13: https://www.bcb.gov.br/?COSIF
