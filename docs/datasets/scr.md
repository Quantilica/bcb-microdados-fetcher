---
dataset:
  id: scr
  fonte: bcb-microdados
  titulo: SCR.data — carteira de crédito
  resumo: Carteira de crédito agregada do SCR por mês, UF, segmento, tipo de cliente, ocupação ou CNAE, porte, modalidade, origem e indexador.
  orgao: Banco Central do Brasil (BCB)
  pagina_oficial: https://www.bcb.gov.br/estabilidadefinanceira/scrdata
  licenca: "Open Data Commons Open Database License (ODbL), conforme o conjunto scr_data no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl"
  periodicidade: mensal, atualizado no último dia útil do mês com os dados de cerca de 30 dias antes
  cobertura: {inicio: 2012-07, fim: em-curso}
  unidade: soma das operações de crédito de um recorte (data-base, UF, segmento, cliente, ocupação/CNAE, porte, modalidade, submodalidade, origem e indexador)
  granularidade: {espacial: UF, temporal: mês}
  formato_bruto: um ZIP por ano (scrdata_<ano>.zip) com um CSV por mês, separado por ponto e vírgula, UTF-8, vírgula decimal
  lake: {estado: convertido, particoes: [ano, mes], chave: [data_base, uf, segmento, cliente, cnae_ocupacao, porte, modalidade, submodalidade, origem, indexador], colunas: 25}
  unidades_de_medida:
    numero_de_operacoes: operações
    a_vencer_ate_90_dias: R$
    a_vencer_de_91_ate_360_dias: R$
    a_vencer_de_361_ate_1080_dias: R$
    a_vencer_de_1081_ate_1800_dias: R$
    a_vencer_de_1801_ate_5400_dias: R$
    a_vencer_acima_de_5400_dias: R$
    carteira_a_vencer: R$
    vencido_de_15_ate_90_dias: R$
    vencido_acima_de_90_dias: R$
    carteira_vencida: R$
    carteira_ativa: R$
    carteira_inadimplencia: R$
    ativo_problematico: R$
  dados_pessoais: nenhum
  eras:
    - {desde: 2016-06, mudanca: "o limite de identificação das operações cai de R$ 1.000 para R$ 200"}
    - {desde: 2025-01, mudanca: "ativo problemático passa a considerar só operações marcadas pelas instituições (característica especial 19)"}
  revisado_em: 2026-11-07
  versao_fetcher: 0.3.3
---

# SCR.data — carteira de crédito

## Resumo

O Sistema de Informações de Créditos (SCR) recebe das instituições financeiras, pelo documento 3040, as operações de crédito acima do limite de identificação. O SCR.data é a publicação mensal do BCB com essa carteira agregada: carteira ativa, carteira vencida, inadimplência e ativo problemático, abertos por UF, segmento da instituição, tipo de cliente, ocupação (pessoa física) ou CNAE (pessoa jurídica), porte, modalidade, submodalidade, origem dos recursos e indexador.

É a base para medir crédito e inadimplência por perfil de tomador e por região. Este dataset segue a versão 2 da publicação (com segmento e submodalidade).

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `bcb-microdados/scr` |
| Órgão | Banco Central do Brasil (BCB) |
| Página oficial | https://www.bcb.gov.br/estabilidadefinanceira/scrdata |
| Licença | Open Data Commons Open Database License (ODbL), conforme o conjunto scr_data no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl |
| Periodicidade | mensal, atualizado no último dia útil do mês com os dados de cerca de 30 dias antes |
| Cobertura | 2012-07 a em-curso |
| Unidade (uma linha) | soma das operações de crédito de um recorte (data-base, UF, segmento, cliente, ocupação/CNAE, porte, modalidade, submodalidade, origem e indexador) |
| Granularidade | espacial: UF; temporal: mês |
| Formato bruto | um ZIP por ano (scrdata_<ano>.zip) com um CSV por mês, separado por ponto e vírgula, UTF-8, vírgula decimal |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `data_base`, `uf`, `segmento`, `cliente`, `cnae_ocupacao`, `porte`, `modalidade`, `submodalidade`, `origem`, `indexador` |
| Colunas | 25 |
| Unidades de medida | `numero_de_operacoes`: operações; `a_vencer_ate_90_dias`: R$; `a_vencer_de_91_ate_360_dias`: R$; `a_vencer_de_361_ate_1080_dias`: R$; `a_vencer_de_1081_ate_1800_dias`: R$; `a_vencer_de_1801_ate_5400_dias`: R$; `a_vencer_acima_de_5400_dias`: R$; `carteira_a_vencer`: R$; `vencido_de_15_ate_90_dias`: R$; `vencido_acima_de_90_dias`: R$; `carteira_vencida`: R$; `carteira_ativa`: R$; `carteira_inadimplencia`: R$; `ativo_problematico`: R$ |
| Dados pessoais | nenhum |
| Eras | 2016-06: o limite de identificação das operações cai de R$ 1.000 para R$ 200; 2025-01: ativo problemático passa a considerar só operações marcadas pelas instituições (característica especial 19) |
| Revisado em | 2026-11-07 |
| Versão do fetcher | 0.3.3 |

## Origem e coleta

- Não há listagem dos arquivos: o fetcher testa, ano a ano desde 2012, se `https://www.bcb.gov.br/pda/desig/scrdata_<ano>.zip` existe, incluindo o ano seguinte (que passa a existir quando o BCB publica o primeiro mês).
- Cada ZIP anual traz um CSV por mês. O ZIP do ano corrente é republicado a cada mês, e o fetcher guarda cada versão com a data da coleta (`scrdata_<ano>@<AAAAMMDD>.zip`). O lake converte a versão mais recente.

## Conteúdo

- Uma linha por combinação de recortes em um mês, com o número de operações e os valores por faixa de vencimento.
- Cobertura no lake: 170 meses contínuos, de 2012-07 a 2026-08 (conferido em 2026-11-07); 43,4 milhões de linhas. A metodologia do BCB fala em dados desde 2012-06, mas os arquivos começam em 2012-07.
- Segundo a metodologia, entram as operações cursadas no país acima do limite de identificação do SCR, informadas por todas as entidades sujeitas ao documento 3040. Não entram saldos de dependências ou controladas no exterior.

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `data_base` | `data_base` | texto | Data-base, último dia do mês | AAAA-MM-DD | todo |
| `uf` | `uf` | texto | UF do CEP de residência (PF) ou da sede (PJ) do cliente | sigla | todo |
| `segmento` | `segmento` | texto | Segmento da instituição financeira | `Banco`, `Cooperativa`, `Financeira`, `Fintech`, `Desenvolvimento/Fomento`, `Instituição de pagamento`, `Arrendamento`, `Outros` | todo |
| `cliente` | `cliente` | texto | Tipo de cliente | `PF`, `PJ` | todo |
| `cnae_ocupacao` | `cnae_ocupacao` | texto | Para PF, natureza da ocupação; para PJ, seção (1º nível) da CNAE | 8 ocupações e as seções da CNAE | todo |
| `porte` | `porte` | texto | Faixa de rendimento (PF) ou porte da empresa (PJ) | PF: `Sem rendimento` a `Acima de 20 salários mínimos`, `Indisponível`; PJ: `Micro`, `Pequeno`, `Médio`, `Grande`, `Indisponível` | todo |
| `modalidade` | `modalidade` | texto | Modalidade da operação (anexo 3 do leiaute do SCR) | 13 modalidades | todo |
| `submodalidade` | `submodalidade` | texto | Submodalidade da operação (anexo 3 do leiaute do SCR) | 59 valores | todo |
| `origem` | `origem` | texto | Origem dos recursos | `Sem destinação específica`, `Com destinação específica` | todo |
| `indexador` | `indexador` | texto | Indexador da operação | `Prefixado`, `Pós-fixado`, `Flutuantes`, `Índices de preços`, `TCR/TRFC`, `Outros indexadores` | todo |
| `numero_de_operacoes` | `numero_de_operacoes` | real (float64) | Número de operações do recorte; nulo quando a fonte traz `-1` | operações | todo |
| `a_vencer_ate_90_dias` | `a_vencer_ate_90_dias` | real (float64) | Créditos a vencer em até 90 dias | R$ | todo |
| `a_vencer_de_91_ate_360_dias` | `a_vencer_de_91_ate_360_dias` | real (float64) | Créditos a vencer de 91 a 360 dias | R$ | todo |
| `a_vencer_de_361_ate_1080_dias` | `a_vencer_de_361_ate_1080_dias` | real (float64) | Créditos a vencer de 361 a 1.080 dias | R$ | todo |
| `a_vencer_de_1081_ate_1800_dias` | `a_vencer_de_1081_ate_1800_dias` | real (float64) | Créditos a vencer de 1.081 a 1.800 dias | R$ | todo |
| `a_vencer_de_1801_ate_5400_dias` | `a_vencer_de_1801_ate_5400_dias` | real (float64) | Créditos a vencer de 1.801 a 5.400 dias | R$ | todo |
| `a_vencer_acima_de_5400_dias` | `a_vencer_acima_de_5400_dias` | real (float64) | Créditos a vencer acima de 5.400 dias | R$ | todo |
| `carteira_a_vencer` | `carteira_a_vencer` | real (float64) | Soma das faixas a vencer | R$ | todo |
| `vencido_de_15_ate_90_dias` | `vencido_de_15_ate_90_dias` | real (float64) | Créditos vencidos de 15 a 90 dias | R$ | todo |
| `vencido_acima_de_90_dias` | `vencido_acima_de_90_dias` | real (float64) | Créditos vencidos há mais de 90 dias | R$ | todo |
| `carteira_vencida` | `carteira_vencida` | real (float64) | Soma das faixas vencidas | R$ | todo |
| `carteira_ativa` | `carteira_ativa` | real (float64) | Carteira a vencer mais carteira vencida | R$ | todo |
| `carteira_inadimplencia` | `carteira_inadimplencia` | real (float64) | Saldo das operações com alguma parcela vencida há mais de 90 dias | R$ | todo |
| `ativo_problematico` | `ativo_problematico` | real (float64) | Saldo das operações classificadas como ativo problemático | R$ | todo |
| `sigilo` | — (gerada) | booleano | Verdadeiro quando a fonte trouxe `-1` em `numero_de_operacoes` | — | todo |
| `ano` | — (partição) | inteiro | Ano da data-base | — | todo |
| `mes` | — (partição) | inteiro | Mês da data-base | 1 a 12 | todo |

## No lake

- Dataset `bcb-microdados/scr`, particionado por `ano` e `mes`; um Parquet por CSV mensal.
- Valores com vírgula decimal viram número.
- `numero_de_operacoes = -1` vira nulo, e a coluna `sigilo` marca essas linhas.
- `data_base` fica como texto, como na fonte. Os outros datasets da fonte usam inteiro AAAAMM; para cruzar, use as partições `ano` e `mes`.

## Cuidados de uso

- **Taxas, não somas de taxas.** Inadimplência e ativo problemático são saldos; a taxa é `carteira_inadimplencia / carteira_ativa` calculada depois de somar os recortes. Não faça média de taxas por linha.
- **Ativo problemático muda em 2025-01.** Até 2024-12 inclui as reestruturações estimadas pelo BCB; desde 2025-01 só as operações marcadas pelas instituições. A série tem quebra.
- **Limite de identificação.** Até 2016-05 entram operações acima de R$ 1.000; desde 2016-06, acima de R$ 200.
- **Número de operações omitido.** Em cerca de 27% das linhas de uma amostra (conferido em 2026-11-07) a fonte traz `-1` no número de operações; no lake ele fica nulo e `sigilo` é verdadeiro. Somas de `numero_de_operacoes` subestimam o total.
- **Não é a estatística oficial de crédito.** O BCB avisa que o SCR.data pode divergir de outras publicações, que usam documentos agregados. Para totais consolidados, o BCB indica a Nota para a Imprensa de estatísticas monetárias e de crédito e o SGS.
- **`cnae_ocupacao` mistura duas classificações**: ocupação para PF e seção da CNAE para PJ. Filtre `cliente` antes de agrupar.
- **Valores nominais**, sem correção monetária.

## Exemplos

Taxa de inadimplência por tipo de cliente, mês a mês:

```python
import polars as pl

scr = pl.scan_parquet("lake/bcb-microdados/scr/**/*.parquet", hive_partitioning=True)
inad = (
    scr.group_by("ano", "mes", "cliente")
    .agg(pl.col("carteira_ativa").sum(), pl.col("carteira_inadimplencia").sum())
    .with_columns((pl.col("carteira_inadimplencia") / pl.col("carteira_ativa")).alias("taxa"))
    .sort("ano", "mes", "cliente")
    .collect()
)
```

## Referências

- SCR.data (BCB): https://www.bcb.gov.br/estabilidadefinanceira/scrdata
- Metodologia do SCR.data, versão 2: https://www.bcb.gov.br/pda/desig/metodologia_versao2.pdf
- Conjunto "SCR.data" no portal de dados abertos do BCB: https://dadosabertos.bcb.gov.br/dataset/scr_data
- Leiaute do documento 3040 (anexos de modalidade, cliente, porte, origem e indexador): https://www.bcb.gov.br/estabilidadefinanceira/scrdoc3040
