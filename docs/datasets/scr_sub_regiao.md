---
dataset:
  id: scr_sub_regiao
  fonte: bcb-microdados
  titulo: SCR por sub-região
  resumo: Carteira de crédito do SCR por mês, UF, sub-região (dois primeiros dígitos do CEP), tipo de cliente, modalidade e classe de risco.
  orgao: Banco Central do Brasil (BCB)
  pagina_oficial: https://dadosabertos.bcb.gov.br/dataset/scr-por-sub-regiao
  licenca: "Open Data Commons Open Database License (ODbL), conforme o conjunto scr-por-sub-regiao no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl"
  periodicidade: mensal
  cobertura: {inicio: 2006-01, fim: em-curso}
  unidade: carteira de um recorte (sub-região, tipo de cliente, modalidade e classe de risco) em um mês
  granularidade: {espacial: sub-região (dois primeiros dígitos do CEP de residência do cliente), temporal: mês}
  formato_bruto: JSON da API OData Olinda (scr_sub_regiao, função scr_sub_regiao), um arquivo por mês
  lake: {estado: convertido, particoes: [ano, mes], chave: [ano, mes, estado, sub_regiao, cliente, modalidade, risco], colunas: 14}
  unidades_de_medida:
    operacoes: operações
    carteira: R$ mil
    a_vencer_ate_90_dias: R$ mil
    a_vencer_de_91_a_360_dias: R$ mil
    a_vencer_de_361_a_1080_dias: R$ mil
    a_vencer_de_1081_a_1800_dias: R$ mil
    a_vencer_de_1801_a_5400_dias: R$ mil
    a_vencer_acima_de_5400_dias: R$ mil
    vencido_acima_de_15_dias: R$ mil
  dados_pessoais: nenhum
  eras:
    - {desde: 2016-06, mudanca: "o limite de identificação das operações do SCR cai de R$ 1.000 para R$ 200"}
    - {desde: 2025-01, mudanca: "a classe de risco deixa de ser publicada (coluna risco vazia)"}
    - {desde: 2026-01, mudanca: "a classe de risco volta preenchida com N/D"}
  revisado_em: 2026-11-07
  versao_fetcher: 0.3.3
---

# SCR por sub-região

## Resumo

Publicação do BCB com a carteira de crédito do Sistema de Informações de Créditos (SCR) aberta por sub-região, isto é, pelos dois primeiros dígitos do CEP de residência do cliente, além de UF, tipo de cliente, modalidade e classe de risco. Começa em 2006, seis anos antes do [SCR.data](scr.md), e tem um recorte geográfico mais fino que a UF.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `bcb-microdados/scr_sub_regiao` |
| Órgão | Banco Central do Brasil (BCB) |
| Página oficial | https://dadosabertos.bcb.gov.br/dataset/scr-por-sub-regiao |
| Licença | Open Data Commons Open Database License (ODbL), conforme o conjunto scr-por-sub-regiao no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl |
| Periodicidade | mensal |
| Cobertura | 2006-01 a em-curso |
| Unidade (uma linha) | carteira de um recorte (sub-região, tipo de cliente, modalidade e classe de risco) em um mês |
| Granularidade | espacial: sub-região (dois primeiros dígitos do CEP de residência do cliente); temporal: mês |
| Formato bruto | JSON da API OData Olinda (scr_sub_regiao, função scr_sub_regiao), um arquivo por mês |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `ano`, `mes`, `estado`, `sub_regiao`, `cliente`, `modalidade`, `risco` |
| Colunas | 14 |
| Unidades de medida | `operacoes`: operações; `carteira`: R$ mil; `a_vencer_ate_90_dias`: R$ mil; `a_vencer_de_91_a_360_dias`: R$ mil; `a_vencer_de_361_a_1080_dias`: R$ mil; `a_vencer_de_1081_a_1800_dias`: R$ mil; `a_vencer_de_1801_a_5400_dias`: R$ mil; `a_vencer_acima_de_5400_dias`: R$ mil; `vencido_acima_de_15_dias`: R$ mil |
| Dados pessoais | nenhum |
| Eras | 2016-06: o limite de identificação das operações do SCR cai de R$ 1.000 para R$ 200; 2025-01: a classe de risco deixa de ser publicada (coluna risco vazia); 2026-01: a classe de risco volta preenchida com N/D |
| Revisado em | 2026-11-07 |
| Versão do fetcher | 0.3.3 |

## Origem e coleta

- O fetcher consulta a função OData `scr_sub_regiao(DataBase=@DataBase)` do serviço Olinda `scr_sub_regiao` v1, um mês por vez, desde 2006-01 (2005-01 vem vazio). Antes de baixar, tira do fim os meses que a API ainda devolve vazios.
- No bruto, cada mês é `scr_sub_regiao_<AAAA-MM>.json`.

## Conteúdo

- Uma linha por recorte em um mês: de 1,6 mil a 4,7 mil linhas por mês nas amostras conferidas.
- Cobertura no lake: 249 meses, de 2006-01 a 2026-09 (conferido em 2026-11-07).
- 100 sub-regiões (dois dígitos) e 14 modalidades. Parte das modalidades só existe para PF ou para PJ.
- Segundo o BCB, a base é o documento 3040, com as operações acima de R$ 200 (o limite era R$ 1.000 até 2016-05). Quando o número de operações de uma modalidade numa sub-região é muito baixo, ela é agrupada em `Não Identificado`.

## Variáveis

As descrições vêm da especificação Swagger do serviço Olinda `scr_sub_regiao`.

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `cliente` | `CLIENTE` | texto | Pessoa física ou jurídica | `PF`, `PJ` | todo |
| `estado` | `ESTADO` | texto | Unidade da federação | sigla | todo |
| `sub_regiao` | `SUB_REGIAO` | texto | Os dois primeiros dígitos do CEP de residência do cliente | `00` a `99` | todo |
| `modalidade` | `MODALIDADE` | texto | Modalidade de crédito | 14 valores, entre eles `Cartão de Crédito`, `Habitacional`, `Veículos`, `Capital de Giro`, `Não Identificado` | todo |
| `risco` | `RISCO` | texto | Classificação de risco da operação (Resolução nº 2.682/1999) | `AA-C`, `D-H` até 2024-12; vazio em 2025; `N/D` desde 2026-01 | todo |
| `operacoes` | `OPERACOES` | inteiro | Quantidade total de operações | operações | todo |
| `carteira` | `CARTEIRA` | decimal(20,2) | Valor da carteira ativa | R$ mil | todo |
| `a_vencer_ate_90_dias` | `A_VENCER_ATE_90_DIAS` | decimal(20,2) | Créditos a vencer em até 90 dias | R$ mil | todo |
| `a_vencer_de_91_a_360_dias` | `A_VENCER_DE_91_A_360_DIAS` | decimal(20,2) | Créditos a vencer de 91 a 360 dias | R$ mil | todo |
| `a_vencer_de_361_a_1080_dias` | `A_VENCER_DE_361_A_1080_DIAS` | decimal(20,2) | Créditos a vencer de 361 a 1.080 dias | R$ mil | todo |
| `a_vencer_de_1081_a_1800_dias` | `A_VENCER_DE_1081_A_1800_DIAS` | decimal(20,2) | Créditos a vencer de 1.081 a 1.800 dias | R$ mil | todo |
| `a_vencer_de_1801_a_5400_dias` | `A_VENCER_DE_1801_A_5400_DIAS` | decimal(20,2) | Créditos a vencer de 1.801 a 5.400 dias | R$ mil | todo |
| `a_vencer_acima_de_5400_dias` | `A_VENCER_ACIMA_DE_5400_DIAS` | decimal(20,2) | Créditos a vencer acima de 5.400 dias | R$ mil | todo |
| `vencido_acima_de_15_dias` | `VENCIDO_ACIMA_DE_15_DIAS` | decimal(20,2) | Créditos vencidos há mais de 15 dias | R$ mil | todo |
| `ano` | `DATA_BASE` (ano) | inteiro | Ano da data-base | — | todo |
| `mes` | `DATA_BASE` (mês) | inteiro | Mês da data-base | 1 a 12 | todo |

## No lake

- Dataset `bcb-microdados/scr_sub_regiao`, particionado por `ano` e `mes`; um Parquet por mês.
- `DATA_BASE` vira as partições `ano` e `mes` e sai das colunas; o arquivo precisa ter um único mês.
- `SUB_REGIAO` vira texto (preserva o zero à esquerda); valores viram decimal com 2 casas; `OPERACOES`, inteiro.
- Nos meses de 2025, em que a fonte não traz classe de risco, a coluna `risco` é toda nula e o Parquet desses meses a grava com tipo nulo; leitores que unem os arquivos precisam aceitar texto e nulo na mesma coluna.

## Cuidados de uso

- **Valores em milhares de reais.** O SCR.data está em reais; este dataset está em R$ mil. Dividindo os valores daqui por 1 milhão chega-se a R$ bilhões, e os totais por tipo de cliente ficam entre 0,89 e 1,01 do SCR.data no mesmo mês (conferido em 2026-11-07, em 2012-07 e 2026-07/08).
- **Vencido acima de 15 dias**, não de 90: não é a mesma medida da inadimplência do SCR.data.
- **Classe de risco com quebra.** `AA-C` e `D-H` existem até 2024-12; em 2025 a coluna vem vazia; desde 2026-01 vem `N/D`. Séries por risco terminam em 2024.
- **`Não Identificado`** agrupa as modalidades com poucas operações numa sub-região; a soma por modalidade não é o total da modalidade no sistema financeiro.
- **Sub-região não é município.** São os dois primeiros dígitos do CEP de residência do cliente; uma sub-região pode atravessar fronteiras de município e, em alguns casos, de UF.
- **Divergência com outras publicações.** O BCB avisa que estes dados podem divergir dos de outras publicações e dos demonstrativos contábeis.

## Exemplos

Carteira de pessoa física por sub-região em um mês, em R$ bilhões:

```python
import polars as pl

sub = pl.scan_parquet("lake/bcb-microdados/scr_sub_regiao/**/*.parquet", hive_partitioning=True)
pf = (
    sub.filter((pl.col("ano") == 2026) & (pl.col("mes") == 6) & (pl.col("cliente") == "PF"))
    .group_by("sub_regiao")
    .agg((pl.col("carteira").cast(pl.Float64).sum() / 1e6).alias("carteira_bi"))  # R$ mil -> R$ bi
    .sort("carteira_bi", descending=True)
    .collect()
)
```

## Referências

- Conjunto "SCR por sub-região" no portal de dados abertos do BCB: https://dadosabertos.bcb.gov.br/dataset/scr-por-sub-regiao
- Especificação do serviço Olinda `scr_sub_regiao` v1: https://olinda.bcb.gov.br/olinda/servico/scr_sub_regiao/versao/v1/documentacao
- Metodologia do SCR.data (limite de identificação): https://www.bcb.gov.br/pda/desig/metodologia_versao2.pdf
