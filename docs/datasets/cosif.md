---
dataset:
  id: cosif
  fonte: bcb-microdados
  titulo: Balancetes e balanços do Cosif
  resumo: Saldos contábeis, conta a conta, de instituições financeiras e conglomerados, por documento e data-base.
  orgao: Banco Central do Brasil (BCB)
  pagina_oficial: https://www.bcb.gov.br/estabilidadefinanceira/balancetesbalancospatrimoniais
  licenca: "Open Data Commons Open Database License (ODbL), conforme o conjunto ifs-balancetes no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl"
  periodicidade: mensal (balancetes) e semestral (balanços de junho e dezembro); publicação trimestral desde o Comunicado 44.132/2025
  cobertura: {inicio: 1988-07, fim: em-curso}
  unidade: saldo de uma conta Cosif de uma instituição (ou conglomerado) em um documento e data-base
  granularidade: {espacial: instituição ou conglomerado (sem recorte geográfico), temporal: mês}
  formato_bruto: ZIP com um CSV por segmento e mês, separado por ponto e vírgula, codificação cp1252, vírgula decimal; layout de largura fixa em parte dos conglomerados (2007 a 2010)
  lake: {estado: convertido, particoes: [segmento, ano], chave: [data_base, documento, cnpj, cod_congl, conta], colunas: 16}
  unidades_de_medida:
    saldo: moeda da data-base (coluna moeda), com centavos
    realizavel_ate_3m: moeda da data-base (coluna moeda), com centavos
    realizavel_apos_3m: moeda da data-base (coluna moeda), com centavos
    data_base: AAAAMM
    documento: código do documento no Catálogo de Documentos (Cadoc)
  dados_pessoais: nenhum
  eras:
    - {desde: 1989-01, mudanca: "saldos em cruzado novo (NCz$); antes, cruzado (Cz$)"}
    - {desde: 1990-03, mudanca: "saldos em cruzeiro (Cr$)"}
    - {desde: 1993-08, mudanca: "saldos em cruzeiro real (CR$)"}
    - {desde: 1994-07, mudanca: "saldos em real (R$)"}
    - {desde: 1994-08, mudanca: "aparece a coluna ATRIBUTO (tipo de instituição no Unicad), publicada até 2010-09"}
    - {desde: 2013-06, mudanca: "começa o segmento combinados (combinados cooperativos)"}
    - {desde: 2014-01, mudanca: "começa o segmento prudencial (conglomerados prudenciais, documentos 4060 e 4066)"}
    - {desde: 2017-01, mudanca: "colunas de realizável até e após 3 meses, publicadas só de 2017-01 a 2017-03"}
    - {desde: 2017-06, mudanca: "TAXONOMIA passa a trazer também códigos numéricos (5.007, 5.002.014)"}
    - {desde: 2017-10, mudanca: "o segmento sociedades deixa de ser publicado (último mês: 2017-09)"}
    - {desde: 2022-01, mudanca: "o segmento conglomerados (documentos 4040 e 4046) deixa de ser publicado (último mês: 2021-12)"}
    - {desde: 2025-01, mudanca: "novo plano de contas Cosif: contas de 10 dígitos (coluna plano = cosif_2025)"}
    - {desde: 2025-03, mudanca: "consórcios passam a publicar também o documento 4110"}
  revisado_em: 2026-11-07
  versao_fetcher: 0.3.3
---

# Balancetes e balanços do Cosif

## Resumo

O Cosif é o plano contábil das instituições do Sistema Financeiro Nacional. Mensalmente, cada instituição autorizada pelo BCB entrega o balancete patrimonial, e semestralmente (junho e dezembro) o balanço. O BCB publica esses documentos com os saldos de todas as contas até o nível 4, por instituição ou por conglomerado.

Este dataset reúne os oito segmentos publicados (bancos, cooperativas, consórcios, sociedades, conglomerados, conglomerados prudenciais, combinados cooperativos e instituições em regime especial) em uma tabela só, com uma linha por saldo de conta. É a base para medir ativo, crédito, captação e patrimônio de cada instituição ao longo de quase quatro décadas.

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `bcb-microdados/cosif` |
| Órgão | Banco Central do Brasil (BCB) |
| Página oficial | https://www.bcb.gov.br/estabilidadefinanceira/balancetesbalancospatrimoniais |
| Licença | Open Data Commons Open Database License (ODbL), conforme o conjunto ifs-balancetes no portal de dados abertos do BCB: http://www.opendefinition.org/licenses/odc-odbl |
| Periodicidade | mensal (balancetes) e semestral (balanços de junho e dezembro); publicação trimestral desde o Comunicado 44.132/2025 |
| Cobertura | 1988-07 a em-curso |
| Unidade (uma linha) | saldo de uma conta Cosif de uma instituição (ou conglomerado) em um documento e data-base |
| Granularidade | espacial: instituição ou conglomerado (sem recorte geográfico); temporal: mês |
| Formato bruto | ZIP com um CSV por segmento e mês, separado por ponto e vírgula, codificação cp1252, vírgula decimal; layout de largura fixa em parte dos conglomerados (2007 a 2010) |
| Estado no lake | convertido |
| Partições | `segmento`, `ano` |
| Chave | `data_base`, `documento`, `cnpj`, `cod_congl`, `conta` |
| Colunas | 16 |
| Unidades de medida | `saldo`: moeda da data-base (coluna moeda), com centavos; `realizavel_ate_3m`: moeda da data-base (coluna moeda), com centavos; `realizavel_apos_3m`: moeda da data-base (coluna moeda), com centavos; `data_base`: AAAAMM; `documento`: código do documento no Catálogo de Documentos (Cadoc) |
| Dados pessoais | nenhum |
| Eras | 1989-01: saldos em cruzado novo (NCz$); antes, cruzado (Cz$); 1990-03: saldos em cruzeiro (Cr$); 1993-08: saldos em cruzeiro real (CR$); 1994-07: saldos em real (R$); 1994-08: aparece a coluna ATRIBUTO (tipo de instituição no Unicad), publicada até 2010-09; 2013-06: começa o segmento combinados (combinados cooperativos); 2014-01: começa o segmento prudencial (conglomerados prudenciais, documentos 4060 e 4066); 2017-01: colunas de realizável até e após 3 meses, publicadas só de 2017-01 a 2017-03; 2017-06: TAXONOMIA passa a trazer também códigos numéricos (5.007, 5.002.014); 2017-10: o segmento sociedades deixa de ser publicado (último mês: 2017-09); 2022-01: o segmento conglomerados (documentos 4040 e 4046) deixa de ser publicado (último mês: 2021-12); 2025-01: novo plano de contas Cosif: contas de 10 dígitos (coluna plano = cosif_2025); 2025-03: consórcios passam a publicar também o documento 4110 |
| Revisado em | 2026-11-07 |
| Versão do fetcher | 0.3.3 |

## Origem e coleta

- O fetcher lista os arquivos pela API de conteúdo do site do BCB (`conteudosite` e `Documentos/byListGuid`), uma pasta por segmento, e baixa a `Url` que a listagem informa. Os endereços antigos `/cosif/...` passaram a devolver a página do site em HTML, por isso o nome do arquivo nunca é montado à mão.
- Na fonte, os arquivos se chamam `<AAAAMM><SEGMENTO>.csv.zip` (por exemplo `202601BANCOS.csv.zip`). No bruto, o fetcher grava `cosif_<segmento>_<AAAA-MM>@<AAAAMMDD>.zip`, em que o sufixo é a data da coleta.
- Quando a listagem traz mais de um arquivo para o mesmo mês (em 2025-12 há `X.csv.zip` e `X.zip.csv.zip`), o fetcher fica com o canônico e o mais recente.
- Meses de consórcios de 2009 e 2010 vêm com uma linha só, `NAO EXISTE DADOS PARA ESTE SEGMENTO`; esses arquivos não geram partição.

## Conteúdo

Documentos (coluna `documento`) por segmento, como estão no lake:

| Segmento | Documento | O que é | Período |
|---|---|---|---|
| `bancos` | 4010 | Balancete mensal | 1988-07 a 2026-06 |
| `bancos` | 4016 | Balanço semestral | 1988-12 a 2026-06 |
| `bancos` | 4020 | Documento 4020 (ver Cadoc) | 1994-01 a 2021-12 |
| `bancos` | 4026 | Documento 4026 (ver Cadoc), só em junho e dezembro | 1994-06 a 2021-12 |
| `cooperativas` | 4010 / 4016 | Balancete / balanço | 1988-12 a 2026-06 |
| `consorcios` | 4010 / 4016 | Balancete / balanço | 1991-09 a 2026-06 |
| `consorcios` | 4110 | Documento 4110 (ver Cadoc) | 2025-03 a 2026-06 |
| `sociedades` | 4010 / 4016 | Balancete / balanço | 1988-07 a 2017-09 |
| `conglomerados` | 4040 / 4046 | Balancete / balanço do conglomerado financeiro | 1988-12 a 2021-12 |
| `prudencial` | 4060 / 4066 | Balancete / balanço do conglomerado prudencial | 2014-01 a 2026-06 |
| `combinados` | 4413 / 4423 / 4433 | Documentos dos combinados cooperativos (ver Cadoc) | 2013-06 a 2026-06 |
| `liquidacao` | 4010 / 4016 | Instituições em regime especial | 1992-12 a 2026-06 |

A descrição de cada documento está no Catálogo de Documentos (Cadoc) e no capítulo 3 do Cosif. O lake tem 77,1 milhões de linhas (conferido em 2026-11-07).

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `data_base` | `DATA` / `#DATA_BASE` | inteiro | Data-base da informação | AAAAMM | todo |
| `documento` | `DOCUMENTO` | inteiro | Documento do Cadoc a que o saldo se refere | 4010, 4016, 4020, 4026, 4040, 4046, 4060, 4066, 4110, 4413, 4423, 4433 | todo |
| `cnpj` | `CNPJ` | texto | Raiz do CNPJ (8 dígitos) da instituição. Em parte das linhas do segmento prudencial traz o código do conglomerado (`C0085111`) | 8 caracteres | todo |
| `agencia` | `AGENCIA` | texto | Coluna presente no cabeçalho da fonte, sempre vazia | — | parte dos arquivos |
| `nome_instituicao` | `NOME_INSTITUICAO` (e variantes antigas do cabeçalho) | texto | Nome da instituição no Unicad | — | todo |
| `cod_congl` | `COD_CONGL` / `COD.CONGLOMERADO` | texto | Código do conglomerado (`C` + 7 dígitos), preenchido nos segmentos conglomerados e prudencial | — | parte dos arquivos |
| `nome_congl` | `NOME_CONGL` (e variantes antigas do cabeçalho) | texto | Nome do conglomerado | — | parte dos arquivos |
| `taxonomia` | `TAXONOMIA` | texto | Tipo de instituição ou conglomerado (`BANCOS MULTIPLOS`, `COOPERATIVAS DE CREDITO`, `CONGLOMERADO PRUDENCIAL`...); desde 2017-06 também códigos numéricos | 31 valores distintos | parte dos arquivos |
| `conta` | `CONTA` | texto | Código da conta no Cosif | 8 dígitos (plano de 1988) ou 10 dígitos (plano de 2025) | todo |
| `nome_conta` | `NOME_CONTA` (e variantes antigas do cabeçalho) | texto | Nome da conta | — | todo |
| `saldo` | `SALDO` | real (float64) | Saldo da conta informado pela instituição | moeda da data-base, com centavos | todo |
| `moeda` | — (gerada) | texto | Padrão monetário da data-base | `Cz$`, `NCz$`, `Cr$`, `CR$`, `R$` | todo |
| `plano` | — (gerada) | texto | Plano de contas da data-base | `cosif_1988` (até 2024-12), `cosif_2025` (desde 2025-01) | todo |
| `atributo` | `ATRIBUTO` | texto | Tipo de instituição no Unicad, uma letra | `A`–`W` | 1994-08 a 2010-09 |
| `realizavel_ate_3m` | coluna de realizável até 3 meses | real (float64) | Parcela do saldo realizável em até 3 meses | moeda da data-base | 2017-01 a 2017-03 |
| `realizavel_apos_3m` | coluna de realizável após 3 meses | real (float64) | Parcela do saldo realizável após 3 meses | moeda da data-base | 2017-01 a 2017-03 |
| `segmento` | — (partição) | texto | Segmento do arquivo de origem | `bancos`, `cooperativas`, `consorcios`, `sociedades`, `conglomerados`, `prudencial`, `combinados`, `liquidacao` | todo |
| `ano` | — (partição) | inteiro | Ano da data-base | — | todo |

## No lake

- Dataset `bcb-microdados/cosif`, particionado por `segmento` e `ano`; um Parquet por arquivo de origem.
- Os nomes de coluna são normalizados (minúsculas, sem acento). Variantes antigas do cabeçalho são unificadas: `DATA` vira `data_base` e `COD.CONGLOMERADO` vira `cod_congl`, entre outras.
- `cnpj`, `agencia`, `cod_congl`, `taxonomia` e `conta` são sempre texto: preservam zeros à esquerda (o Banco do Brasil é `00000000`) e os códigos de conglomerado.
- No plano de 1988, conta com 10 dígitos começando por `00` perde os dois zeros iniciais, para ficar com os 8 dígitos do plano.
- Textos perdem os espaços de preenchimento; no layout de largura fixa, o saldo com espaço no lugar do sinal é convertido para número.
- São acrescentadas `moeda`, `plano`, `segmento` e `ano`.
- Ficam de fora os arquivos de mês sem dados de consórcios (2009 e 2010).

## Cuidados de uso

- **Balancete e balanço se repetem em junho e dezembro.** Nesses meses a mesma instituição aparece no balancete (4010, 4040, 4060) e no balanço (4016, 4046, 4066). Filtre um documento só antes de somar ou montar séries.
- **Não some todas as contas.** Os arquivos trazem as contas até o nível 4 do plano, então contas-mãe e contas-filhas aparecem juntas. Use as contas de total. Por exemplo, o ativo total é a soma das classes 1 e 2: `10000007` + `20000004` no plano de 1988 e `1000000009` + `2000000008` no plano de 2025.
- **Contas de resultado zeram em junho e dezembro.** Segundo o BCB, as contas de resultado são encerradas na apuração dos balanços semestrais; saldos de resultado não são cumulativos entre semestres.
- **O plano de contas mudou em 2025-01.** Os códigos de conta do plano de 2025 têm 10 dígitos e não correspondem um a um aos de 1988. Séries que atravessam 2025 precisam de uma correspondência entre os planos; a coluna `plano` diz qual vale em cada linha.
- **Moeda da época.** Até 1994-06 os saldos estão em Cz$, NCz$, Cr$ ou CR$, sem conversão nem correção monetária. A coluna `moeda` indica o padrão de cada linha.
- **Prudencial com código no lugar do CNPJ.** No segmento prudencial, parte das linhas traz o código do conglomerado (por exemplo `C0085111`) na coluna `cnpj`. Para agregar por conglomerado use `cod_congl`.
- **Segmentos que acabaram.** `sociedades` vai até 2017-09 e `conglomerados` até 2021-12; o prudencial começa em 2014-01. Séries por segmento têm esses cortes.
- **`agencia` está sempre vazia** em todas as 40,6 milhões de linhas em que a coluna existe (conferido em 2026-11-07).
- **Publicação trimestral.** Desde o Comunicado 44.132/2025 os meses de cada trimestre só saem dois a três meses depois do fim do trimestre.

## Exemplos

Ativo total dos conglomerados prudenciais por mês, sem dupla contagem (só o balancete 4060) e atravessando a troca de plano:

```python
import polars as pl

ATIVO = ["10000007", "20000004", "1000000009", "2000000008"]  # classes 1 e 2, nos dois planos

cosif = pl.scan_parquet("lake/bcb-microdados/cosif/**/*.parquet", hive_partitioning=True)
ativo = (
    cosif.filter(
        (pl.col("segmento") == "prudencial")
        & (pl.col("documento") == 4060)
        & pl.col("conta").is_in(ATIVO)
    )
    .group_by("data_base", "plano", "moeda")
    .agg((pl.col("saldo").sum() / 1e9).alias("ativo_bi"))
    .sort("data_base")
    .collect()
)
```

## Referências

- Balancetes e balanços patrimoniais (BCB): https://www.bcb.gov.br/estabilidadefinanceira/balancetesbalancospatrimoniais
- Conjunto "Balancetes (IFs e Conglomerados)" no portal de dados abertos do BCB, com a descrição dos campos: https://dadosabertos.bcb.gov.br/dataset/ifs-balancetes
- Cosif, capítulo 2 (elenco de contas) e capítulo 3 (documentos): https://www.bcb.gov.br/?COSIF
