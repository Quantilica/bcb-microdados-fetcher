---
dataset:
  id: pix_municipio_transacoes
  fonte: bcb-microdados
  titulo: Transações Pix por município
  resumo: Transações Pix liquidadas por município e mês, do lado do pagador e do recebedor, separadas entre pessoas físicas e jurídicas.
  orgao: Banco Central do Brasil (BCB)
  pagina_oficial: https://dadosabertos.bcb.gov.br/dataset/pix
  licenca: "Open Data Commons Open Database License (ODbL), conforme o conjunto pix no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl"
  periodicidade: mensal; o mês corrente também é publicado, ainda incompleto
  cobertura: {inicio: 2020-11, fim: em-curso}
  unidade: um município em um mês
  granularidade: {espacial: município, temporal: mês}
  formato_bruto: JSON da API OData Olinda (Pix_DadosAbertos, função TransacoesPixPorMunicipio), um arquivo por mês
  lake: {estado: convertido, particoes: [ano, mes], chave: [ano, mes, codigo_ibge], colunas: 18}
  unidades_de_medida:
    vl_pagador_pf: R$
    vl_pagador_pj: R$
    vl_recebedor_pf: R$
    vl_recebedor_pj: R$
    qt_pagador_pf: transações
    qt_pagador_pj: transações
    qt_recebedor_pf: transações
    qt_recebedor_pj: transações
    qt_pes_pagador_pf: pessoas
    qt_pes_pagador_pj: pessoas
    qt_pes_recebedor_pf: pessoas
    qt_pes_recebedor_pj: pessoas
  dados_pessoais: nenhum
  eras: []
  revisado_em: 2026-11-07
  versao_fetcher: 0.3.3
---

# Transações Pix por município

## Resumo

Estatística do BCB sobre as transações Pix liquidadas, consolidadas por município. Para cada município e mês, traz o valor e a quantidade de transações e a quantidade de pessoas, separando pagadores e recebedores e pessoas físicas e jurídicas. Serve para medir a adoção e o volume do Pix no território.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `bcb-microdados/pix_municipio_transacoes` |
| Órgão | Banco Central do Brasil (BCB) |
| Página oficial | https://dadosabertos.bcb.gov.br/dataset/pix |
| Licença | Open Data Commons Open Database License (ODbL), conforme o conjunto pix no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl |
| Periodicidade | mensal; o mês corrente também é publicado, ainda incompleto |
| Cobertura | 2020-11 a em-curso |
| Unidade (uma linha) | um município em um mês |
| Granularidade | espacial: município; temporal: mês |
| Formato bruto | JSON da API OData Olinda (Pix_DadosAbertos, função TransacoesPixPorMunicipio), um arquivo por mês |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `ano`, `mes`, `codigo_ibge` |
| Colunas | 18 |
| Unidades de medida | `vl_pagador_pf`: R$; `vl_pagador_pj`: R$; `vl_recebedor_pf`: R$; `vl_recebedor_pj`: R$; `qt_pagador_pf`: transações; `qt_pagador_pj`: transações; `qt_recebedor_pf`: transações; `qt_recebedor_pj`: transações; `qt_pes_pagador_pf`: pessoas; `qt_pes_pagador_pj`: pessoas; `qt_pes_recebedor_pf`: pessoas; `qt_pes_recebedor_pj`: pessoas |
| Dados pessoais | nenhum |
| Eras | nenhuma |
| Revisado em | 2026-11-07 |
| Versão do fetcher | 0.3.3 |

## Origem e coleta

- O fetcher consulta a função OData `TransacoesPixPorMunicipio(DataBase=@DataBase)` do serviço Olinda `Pix_DadosAbertos` v1, um mês por vez, desde 2020-11 (2020-10 vem vazio). O conjunto de entidades sem a função devolve erro 500, por isso a consulta é sempre pela função.
- Antes de baixar, o fetcher tira do fim os meses que a API ainda devolve vazios.
- No bruto, cada mês é `pix_municipio_transacoes_<AAAA-MM>.json`, com a versão de cada coleta registrada à parte.

## Conteúdo

- Uma linha por município e mês: 5.569 a 5.572 linhas por mês, incluindo uma linha `N/D` (`NAO INFORMADO`) sem código de município.
- Cobertura no lake: 73 meses, de 2020-11 a 2026-11, este último ainda incompleto (conferido em 2026-11-07).
- A descrição oficial do recurso é "Transações Pix liquidadas por município e por pessoas físicas (PF) e jurídicas (PJ), considerando a perspectiva do pagador e do recebedor".

## Variáveis

As descrições vêm da especificação Swagger do serviço Olinda `Pix_DadosAbertos`.

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `codigo_ibge` | `Municipio_Ibge` | texto | Código IBGE do município; nulo na linha `N/D` | 7 dígitos | todo |
| `municipio` | `Municipio` | texto | Nome do município | — | todo |
| `uf_ibge` | `Estado_Ibge` | texto | Código IBGE do estado | 2 dígitos | todo |
| `estado` | `Estado` | texto | Nome do estado | — | todo |
| `sigla_regiao` | `Sigla_Regiao` | texto | Sigla da região | `NO`, `NE`, `SE`, `SU`, `CO` | todo |
| `regiao` | `Regiao` | texto | Região do país | `NORTE`, `NORDESTE`, `SUDESTE`, `SUL`, `CENTRO-OESTE`, `Nao informado` | todo |
| `vl_pagador_pf` | `VL_PagadorPF` | decimal(20,2) | Volume financeiro das transações cujo pagador é pessoa física | R$ | todo |
| `qt_pagador_pf` | `QT_PagadorPF` | inteiro | Quantidade de transações cujo pagador é pessoa física | transações | todo |
| `vl_pagador_pj` | `VL_PagadorPJ` | decimal(20,2) | Volume financeiro das transações cujo pagador é pessoa jurídica | R$ | todo |
| `qt_pagador_pj` | `QT_PagadorPJ` | inteiro | Quantidade de transações cujo pagador é pessoa jurídica | transações | todo |
| `vl_recebedor_pf` | `VL_RecebedorPF` | decimal(20,2) | Volume financeiro das transações cujo recebedor é pessoa física | R$ | todo |
| `qt_recebedor_pf` | `QT_RecebedorPF` | inteiro | Quantidade de transações cujo recebedor é pessoa física | transações | todo |
| `vl_recebedor_pj` | `VL_RecebedorPJ` | decimal(20,2) | Volume financeiro das transações cujo recebedor é pessoa jurídica | R$ | todo |
| `qt_recebedor_pj` | `QT_RecebedorPJ` | inteiro | Quantidade de transações cujo recebedor é pessoa jurídica | transações | todo |
| `qt_pes_pagador_pf` | `QT_PES_PagadorPF` | inteiro | Quantidade de pagadores pessoas físicas | pessoas | todo |
| `qt_pes_pagador_pj` | `QT_PES_PagadorPJ` | inteiro | Quantidade de pagadores pessoas jurídicas | pessoas | todo |
| `qt_pes_recebedor_pf` | `QT_PES_RecebedorPF` | inteiro | Quantidade de recebedores pessoas físicas | pessoas | todo |
| `qt_pes_recebedor_pj` | `QT_PES_RecebedorPJ` | inteiro | Quantidade de recebedores pessoas jurídicas | pessoas | todo |
| `ano` | `AnoMes` (ano) | inteiro | Ano da data-base | — | todo |
| `mes` | `AnoMes` (mês) | inteiro | Mês da data-base | 1 a 12 | todo |

## No lake

- Dataset `bcb-microdados/pix_municipio_transacoes`, particionado por `ano` e `mes`; um Parquet por mês.
- `AnoMes` vira as partições `ano` e `mes` e sai das colunas; o arquivo precisa ter um único mês.
- Códigos de município e de estado viram texto com zeros à esquerda (7 e 2 dígitos).
- Valores (`VL_*`) viram decimal com 2 casas; quantidades (`QT_*`), inteiro.
- Nomes de coluna em minúsculas, com `PF`/`PJ` separados por sublinhado (`VL_PagadorPF` vira `vl_pagador_pf`).

## Cuidados de uso

- **O último mês é parcial.** A API publica o mês corrente ainda em andamento. Para séries mensais, descarte o mês corrente ou marque-o como incompleto.
- **Pagador e recebedor são duas perspectivas das mesmas transações**, segundo a descrição oficial. Não some os dois lados como se fossem transações diferentes; para um total, use um lado só.
- **De quem é o município.** A fonte diz apenas que os dados são por município, "considerando a perspectiva do pagador e do recebedor"; ela não detalha, campo a campo, como o município é atribuído.
- **Quantidade de pessoas não se soma entre municípios ou meses.** A especificação não diz se `qt_pes_*` conta pessoas distintas; uma mesma pessoa pode aparecer em mais de um mês.
- **Linha `N/D`.** Em cada mês há uma linha sem código de município (`municipio = N/D`, `regiao = Nao informado`). Filtre `codigo_ibge` não nulo para análises municipais, ou mantenha-a para totais.

## Exemplos

Transações e valor por UF no último mês completo, pelo lado do pagador:

```python
import polars as pl
from datetime import date

pix = pl.scan_parquet("lake/bcb-microdados/pix_municipio_transacoes/**/*.parquet", hive_partitioning=True)
mes = pl.col("ano") * 100 + pl.col("mes")
hoje = date.today()
ultimo = pix.select(mes.filter(mes < hoje.year * 100 + hoje.month).max()).collect().item()
por_uf = (
    pix.filter((mes == ultimo) & pl.col("codigo_ibge").is_not_null())
    .group_by("estado")
    .agg(
        (pl.col("qt_pagador_pf") + pl.col("qt_pagador_pj")).sum().alias("transacoes"),
        (pl.col("vl_pagador_pf") + pl.col("vl_pagador_pj")).sum().alias("valor"),
    )
    .sort("transacoes", descending=True)
    .collect()
)
```

## Referências

- Conjunto "Estatísticas do Pix" no portal de dados abertos do BCB: https://dadosabertos.bcb.gov.br/dataset/pix
- Especificação do serviço Olinda `Pix_DadosAbertos` v1 (Swagger): https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/swagger-ui3#/
- Estatísticas do Pix (BCB): https://www.bcb.gov.br/estabilidadefinanceira/estatisticaspix
