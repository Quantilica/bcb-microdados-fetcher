# Banco Central do Brasil — microdados (`bcb-microdados`)

O `bcb-microdados-fetcher` coleta seis conjuntos de dados abertos do Banco Central do Brasil (BCB) sobre o sistema financeiro e os converte para o lake em Parquet particionado. Os conjuntos vêm de três sistemas do BCB: o plano contábil das instituições financeiras (Cosif), o Sistema de Informações de Créditos (SCR) e o Pix.

| Dataset | O que é | Origem | Período | Página |
|---|---|---|---|---|
| `cosif` | Balancetes e balanços patrimoniais das instituições e conglomerados, conta a conta | Arquivos do Cosif no site do BCB | 1988-07 em diante | [cosif](datasets/cosif.md) |
| `estban_municipio` | Estatística Bancária Mensal (ESTBAN): saldos por verbete, instituição e município | Arquivos da ESTBAN no site do BCB | 1988-07 em diante | [estban_municipio](datasets/estban_municipio.md) |
| `estban_agencia` | ESTBAN por agência | Arquivos da ESTBAN no site do BCB | 1988-07 em diante | [estban_agencia](datasets/estban_agencia.md) |
| `scr` | SCR.data: carteira de crédito agregada por UF, segmento, cliente, modalidade e outros recortes | ZIP anual do SCR.data | 2012-07 em diante | [scr](datasets/scr.md) |
| `scr_sub_regiao` | Carteira de crédito do SCR por sub-região (dois primeiros dígitos do CEP) e classe de risco | API Olinda | 2006-01 em diante | [scr_sub_regiao](datasets/scr_sub_regiao.md) |
| `pix_municipio_transacoes` | Transações Pix liquidadas por município, do lado do pagador e do recebedor | API Olinda | 2020-11 em diante | [pix_municipio_transacoes](datasets/pix_municipio_transacoes.md) |

## Como o BCB publica

- **Cosif e ESTBAN** saem como arquivos ZIP com CSV, listados por uma API interna do site do BCB. Desde o Comunicado 44.132/2025, as datas-base de cada trimestre são publicadas de uma vez: janeiro a março em 31 de maio, abril a junho em 31 de agosto, julho a setembro em 30 de novembro e outubro a dezembro em 31 de março do ano seguinte. Cada publicação da ESTBAN reabrange os últimos seis meses.
- **SCR.data** sai como um ZIP por ano (`scrdata_<ano>.zip`) com um CSV por mês, atualizado no último dia útil de cada mês, com os dados do mês encerrado há cerca de 30 dias.
- **SCR por sub-região e Pix** saem pela API OData Olinda, um mês por consulta. O Pix publica também o mês corrente, ainda incompleto.

O fetcher guarda cada versão baixada com a data de coleta no nome (`<arquivo>@AAAAMMDD`). O lake converte a versão mais recente de cada arquivo.

## Como os conjuntos se relacionam

- **Cosif × ESTBAN.** A ESTBAN é um subsistema do Cosif: cada verbete agrega contas do balancete 4010, aberto por município (ou agência). Os totais por instituição deveriam se aproximar, mas não coincidem; veja os cuidados de uso da [ESTBAN por município](datasets/estban_municipio.md).
- **SCR.data × SCR por sub-região.** As duas bases vêm do documento 3040 (SCR). O SCR.data detalha mais recortes e está em reais; o SCR por sub-região está em **milhares de reais** e abre por CEP e classe de risco. Os totais por tipo de cliente ficam entre 0,89 e 1,01 um do outro.
- **SCR × Cosif.** O SCR conta operações acima do limite de identificação (R$ 1.000 até maio de 2016, R$ 200 depois); o Cosif traz o saldo contábil inteiro. O BCB avisa que os totais podem divergir.

## Quebras que valem para mais de um conjunto

| Desde | Mudança | Afeta |
|---|---|---|
| até 1988-12 | Valores em cruzado (Cz$) | `cosif`, `estban_*` |
| 1989-01 | Cruzado novo (NCz$) | `cosif`, `estban_*` |
| 1990-03 | Cruzeiro (Cr$) | `cosif`, `estban_*` |
| 1993-08 | Cruzeiro real (CR$) | `cosif`, `estban_*` |
| 1994-07 | Real (R$) | `cosif`, `estban_*` |
| 2016-06 | Limite de identificação do SCR cai de R$ 1.000 para R$ 200 | `scr`, `scr_sub_regiao` |
| 2025-01 | Novo plano de contas Cosif (contas de 10 dígitos) | `cosif` |
| 2025-01 | Ativo problemático passa a considerar só operações marcadas pelas instituições (característica especial 19) | `scr` |

Os valores do Cosif e da ESTBAN estão sempre na moeda da data-base, sem conversão nem correção monetária; a coluna `moeda` de cada linha diz qual é.
