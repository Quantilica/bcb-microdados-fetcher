---
dataset:
  id: estban_municipio
  fonte: bcb-microdados
  titulo: ESTBAN por município
  resumo: Estatística Bancária Mensal, saldos de cada verbete por instituição e município, em formato longo.
  orgao: Banco Central do Brasil (BCB)
  pagina_oficial: https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios
  licenca: "Não declarada na página da ESTBAN. Os conjuntos do BCB no portal de dados abertos (dadosabertos.bcb.gov.br) usam a Open Data Commons Open Database License (ODbL): http://www.opendefinition.org/licenses/odc-odbl"
  periodicidade: mensal; publicação trimestral desde o Comunicado 44.132/2025, e cada publicação reabrange os últimos seis meses
  cobertura: {inicio: 1988-07, fim: em-curso}
  unidade: saldo de um verbete da ESTBAN de uma instituição em um município, numa data-base
  granularidade: {espacial: município, temporal: mês}
  formato_bruto: ZIP com um CSV por mês (documento 4500), separado por ponto e vírgula, latin-1, duas linhas de preâmbulo e uma coluna por verbete (formato largo)
  lake: {estado: convertido, particoes: [ano, mes], chave: [data_base, codmun, cnpj, verbete_codigo], colunas: 13}
  unidades_de_medida:
    valor: moeda da data-base (coluna moeda), sem centavos
    agen_esperadas: agências
    agen_processadas: agências
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

# ESTBAN por município

## Resumo

A Estatística Bancária Mensal (ESTBAN) é um subsistema estatístico do Cosif (documentos 4500, mensal, e 4510, global). Cada verbete agrega contas do balancete 4010, e o BCB publica os saldos abertos por instituição e município. É a principal fonte pública para ver onde estão o crédito, a poupança e os depósitos bancários no território, mês a mês, desde 1988.

Este dataset traz os arquivos por município em formato longo: uma linha por instituição, município, data-base e verbete. A versão por agência está em [`estban_agencia`](estban_agencia.md).

## Ficha técnica

<!-- gerado:ficha -->

| Campo | Valor |
|---|---|
| Dataset | `bcb-microdados/estban_municipio` |
| Órgão | Banco Central do Brasil (BCB) |
| Página oficial | https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios |
| Licença | Não declarada na página da ESTBAN. Os conjuntos do BCB no portal de dados abertos (dadosabertos.bcb.gov.br) usam a Open Data Commons Open Database License (ODbL): http://www.opendefinition.org/licenses/odc-odbl |
| Periodicidade | mensal; publicação trimestral desde o Comunicado 44.132/2025, e cada publicação reabrange os últimos seis meses |
| Cobertura | 1988-07 a em-curso |
| Unidade (uma linha) | saldo de um verbete da ESTBAN de uma instituição em um município, numa data-base |
| Granularidade | espacial: município; temporal: mês |
| Formato bruto | ZIP com um CSV por mês (documento 4500), separado por ponto e vírgula, latin-1, duas linhas de preâmbulo e uma coluna por verbete (formato largo) |
| Estado no lake | convertido |
| Partições | `ano`, `mes` |
| Chave | `data_base`, `codmun`, `cnpj`, `verbete_codigo` |
| Colunas | 13 |
| Unidades de medida | `valor`: moeda da data-base (coluna moeda), sem centavos; `agen_esperadas`: agências; `agen_processadas`: agências; `data_base`: AAAAMM; `codmun`: código de município do BCB; `codmun_ibge`: código IBGE de município (7 dígitos) |
| Dados pessoais | nenhum |
| Eras | 1989-01: valores em cruzado novo (NCz$); antes, cruzado (Cz$); 1990-03: valores em cruzeiro (Cr$); 1993-08: valores em cruzeiro real (CR$); 1994-07: valores em real (R$); 2022-07: 12 verbetes deixam de ser publicados; 167+168 passa a 167 e 461+462+463+467+468 passa a 461+467+468 |
| Revisado em | 2026-11-07 |
| Versão do fetcher | 0.4.0 |

## Origem e coleta

- O fetcher lista os arquivos pela API de conteúdo do site do BCB (identificador `estatistica_bancaria_estban`, pasta `municipio`) e baixa a `Url` informada. Os endereços antigos `/estban/...` passaram a devolver a página do site em HTML.
- Na fonte, cada mês é um ZIP com um CSV que começa com duas linhas de preâmbulo (`ESTBAN (Documento 4500) por municipio` e a data de geração) e o cabeçalho com `#DATA_BASE`. No bruto, o fetcher grava `estban_municipio_<AAAA-MM>@<AAAAMMDD>.zip`, em que o sufixo é a data da coleta.
- Cada publicação reabrange os últimos seis meses; um mês pode ser baixado mais de uma vez, com conteúdo revisto. O lake converte a versão mais recente.

## Conteúdo

- Uma linha por instituição, município, data-base e verbete, com o saldo do verbete. Instituições aparecem nos municípios onde têm agências.
- Cobertura no lake: 456 meses contínuos, de 1988-07 a 2026-06 (conferido em 2026-11-07); 270,9 milhões de linhas.
- Segundo o BCB, os saldos estão na moeda corrente da data-base, sem centavos, e incluem junho e dezembro.
- Alguns verbetes são publicados somados, para respeitar a regra de divulgação até o nível 3 do Cosif; o cabeçalho da fonte indica a soma (`VERBETE_141_... + VERBETE_142_...`), e o lake guarda `141+142` em `verbete_codigo`.

Verbetes no lake (códigos de `verbete_codigo`, nomes de `verbete_nome`, normalizados a partir do cabeçalho da fonte):

| Verbete | Nome | Período |
|---|---|---|
| `110` | `encaixe` | todo |
| `111` | `caixa` | todo |
| `112` | `depositos_bancarios` | todo |
| `113` | `bacen_reserv_banc_em_especie` | todo |
| `114` | `aplic_temporarias_em_ouro` | 1988-07 a 2022-06 |
| `120` | `aplic_interfinanc_de_liquidez` | todo |
| `130` | `tit_e_val_mob_e_inst_fin_deriv` | todo |
| `140` | `rel_interfinanc_e_interdepend` | todo |
| `141+142` | `correspondentes_no_exterior+correspondentes_no_pais` | todo |
| `143` | `depend_matriz_e_congeneres_no_exterior_em` | 1988-07 a 2022-06 |
| `144+145+146+147+152` | `cobranca_em_transito+ordens_de_pagamento+val_ligadas_e_terc_em_transito+dependencias_no_pais+suprimentos_interdependencias` | todo |
| `153` | `relacoes_com_a_carteira_de_cambio_e_de_desenvol` | 1988-07 a 2022-06 |
| `158` | `outr_rel_interf_e_interdepend` | todo |
| `160` | `operacoes_de_credito` | todo |
| `161` | `empres_e_tit_descontados` | todo |
| `162` | `financiamentos` | todo |
| `163` | `fin_rurais_agricul_cust_invest` | todo |
| `164` | `fin_rurais_pecuar_cust_invest` | 1988-07 a 2022-06 |
| `165` | `fin_rurais_agricul_comercializ` | 1988-07 a 2022-06 |
| `166` | `fin_rurais_pecuaria_comercializ` | 1988-07 a 2022-06 |
| `167` | `financiamentos_agroindustriais` | 2022-07 em diante |
| `167+168` | `financiamentos_agroindustriais+rendas_a_apropriar_financ...` | 1988-07 a 2022-06 |
| `169` | `financiamentos_imobiliarios` | todo |
| `171` | `outras_operacoes_de_credito` | todo |
| `172` | `outros_creditos` | todo |
| `173` | `creditos_em_liquidacao` | 1988-07 a 2022-06 |
| `174` | `prov_p_oper_creditos` | todo |
| `176` | `operacoes_especiais` | todo |
| `180` | `arrendamento_mercantil` | todo |
| `184` | `prov_p_oper_arr_mercantil` | todo |
| `190` | `outros_valores_e_bens` | todo |
| `200` | `permanente` | todo |
| `300` | `contas_de_compensacao` | 1988-07 a 2022-06 |
| `399` | `total_do_ativo` | todo |
| `401+402+403+404+411+412+413+414+415+416+417+418+419` | `servicos_publicos+atividades_empresariais+especiais_do_tesouro_nacional+...` (13 verbetes) | todo |
| `420` | `depositos_de_poupanca` | todo |
| `430` | `depositos_interifnanceiros` | todo |
| `431` | `depositos_interfinanceiros` | todo |
| `432` | `depositos_a_prazo` | todo |
| `433` | `captaceos_no_mercado_aberto` | todo |
| `440` | `rel_interfinanc_e_interdepend` | todo |
| `441+442` | `correspondentes_no_exterior+correspondentes_no_pais` | todo |
| `443` | `dependencias_matriz_e_congeneres_no_exterior` | 1988-07 a 2022-06 |
| `444+445+446+447+456+458` | cobranca_em_transito+ordens_de_pagamento+... (6 verbetes) | todo |
| `457` | `relacoes_com_a_carteira_de_cambio_e_de_desenvolv` | 1988-07 a 2022-06 |
| `460` | `obrig_por_emp_e_repasses` | todo |
| `461+462+463+467+468` | `banco_central_assistencia_financeira+redesconto+refinan...` | 1988-07 a 2022-06 |
| `461+467+468` | `banco_central_assistencia_financeira+operacoes_especiais+...` | 2022-07 em diante |
| `470` | `inst_financeiros_derivativos` | todo |
| `480` | `obrigacoes_por_recebimento` | todo |
| `481+482+483+484+485+487` | `iof+contribuicoes_previdenciarias+tributos_estad_e_municipais+tributos_federais+fgts+demais_recebimentos` | todo |
| `486` | `pis_pasep` | 1988-07 a 2022-06 |
| `490+500` | `cheques_administrativos+outras_obrigacoes` | todo |
| `610` | `patrimonio_liquido` | todo |
| `710` | `contas_de_resultado` | todo |
| `711` | `contas_credoras` | todo |
| `712` | `contas_devedoras` | todo |
| `800` | `contas_de_compensacao` | 1988-07 a 2022-06 |
| `899` | `total_do_passivo` | todo |
A discriminação dos verbetes está no Cosif, capítulo 3, documento nº 13 (Estatística Bancária Mensal / Global); a correspondência entre contas e verbetes, no capítulo 2, coluna E.

## Variáveis

| Coluna no lake | Na fonte | Tipo | Descrição | Unidade / códigos | Período |
|---|---|---|---|---|---|
| `data_base` | `#DATA_BASE` | inteiro | Data-base | AAAAMM | todo |
| `uf` | `UF` | texto | Unidade da federação do município | sigla | todo |
| `codmun` | `CODMUN` | inteiro | Código do município no BCB (não é o do IBGE) | — | todo |
| `municipio` | `MUNICIPIO` | texto | Nome do município | — | todo |
| `cnpj` | `CNPJ` | texto | Raiz do CNPJ da instituição | 8 dígitos | todo |
| `nome_instituicao` | `NOME_INSTITUICAO` | texto | Nome da instituição | — | todo |
| `agen_esperadas` | `AGEN_ESPERADAS` | inteiro | Quantidade de agências esperadas da instituição no município | agências | todo |
| `agen_processadas` | `AGEN_PROCESSADAS` | inteiro | Quantidade de agências processadas da instituição no município | agências | todo |
| `codmun_ibge` | `CODMUN_IBGE` | inteiro | Código IBGE do município; nulo em cerca de 1% das linhas | 7 dígitos | todo |
| `verbete_codigo` | cabeçalho `VERBETE_<código>_<nome>` | texto | Código do verbete; soma de verbetes com `+` | ver tabela de verbetes | todo |
| `verbete_nome` | cabeçalho `VERBETE_<código>_<nome>` | texto | Nome do verbete, normalizado; somas com `+` | — | todo |
| `valor` | coluna de cada verbete | inteiro | Saldo do verbete; nulo quando a fonte vem vazia | moeda da data-base, sem centavos | todo |
| `moeda` | — (gerada) | texto | Padrão monetário da data-base | `Cz$`, `NCz$`, `Cr$`, `CR$`, `R$` | todo |
| `ano` | — (partição) | inteiro | Ano da data-base | — | todo |
| `mes` | — (partição) | inteiro | Mês da data-base | 1 a 12 | todo |

## No lake

- Dataset `bcb-microdados/estban_municipio`, particionado por `ano` e `mes`; um Parquet por mês.
- O formato largo da fonte (uma coluna por verbete) vira formato longo: `verbete_codigo`, `verbete_nome` e `valor`.
- `cnpj` é texto (o Banco do Brasil é `00000000`).
- Textos perdem os espaços de preenchimento (`"COMERCINHO      "` vira `"COMERCINHO"`).
- `agen_esperadas` e `agen_processadas` são colunas de cada linha. Até a versão 0.3.3 do fetcher elas viravam linhas com `verbete_codigo` `agen_esperadas` e `agen_processadas`; lakes convertidos com essas versões precisam de reconversão.
- `moeda` é acrescentada a partir da data-base (desde a versão 0.4.0).

## Cuidados de uso

- **Não some todos os verbetes.** Há verbetes de total (`399` total do ativo, `899` total do passivo) e de grupo (`160` operações de crédito, com subitens como `161`, `162` e `169`). Escolha os verbetes da análise.
- **Composição muda em 2022-07.** `167+168` passa a `167` e `461+462+463+467+468` passa a `461+467+468`; 12 verbetes deixam de existir (veja a tabela). Séries longas desses códigos precisam de ajuste.
- **Moeda da época e sem centavos.** Até 1994-06 os valores estão em Cz$, NCz$, Cr$ ou CR$, sem conversão nem correção monetária; a coluna `moeda` diz qual. Os valores são inteiros.
- **Verbete 153 vem sempre vazio** no arquivo por município (até 2022-06, quando deixa de existir). No arquivo por agência ele tem valores.
- **Valores vazios.** Cerca de 0,85% das linhas de cada verbete têm `valor` nulo, porque a fonte veio vazia (39.544 de 4.675.403 por verbete, conferido em 2026-11-07).
- **Dois códigos de município.** `codmun` é o código interno do BCB; para cruzar com IBGE use `codmun_ibge`, que falta em cerca de 1% das linhas.
- **Salto em 2026-04 na própria fonte.** O crédito somado (`160`) passa de R$ 7,1 tri em 2026-03 para R$ 12,5 tri em 2026-04. O CSV do BCB mostra, por exemplo, o crédito do Banco do Brasil em Brasília indo de R$ 234 bi para R$ 1,5 tri de um mês para o outro. Até 2025-12 o crédito da ESTBAN ficava entre 0,82 e 0,94 do SCR.data (conferido em 2026-11-07).
- **ESTBAN × Cosif não fecha por instituição.** Em 2026-06, o crédito (`160`) dos dez maiores bancos na ESTBAN ficou entre 2,2 e 8,6 vezes o crédito no balancete 4010 do Cosif (conferido em 2026-11-07).
- **Revisões.** Cada publicação reabrange os seis meses anteriores; números de meses recentes podem mudar.
- **Nomes como na fonte.** `verbete_nome` mantém grafias do cabeçalho original, como `depositos_interifnanceiros` e `captaceos_no_mercado_aberto`.

## Exemplos

Crédito (verbete 160) e poupança (420) por UF em um mês, em R$ bilhões:

```python
import polars as pl

estban = pl.scan_parquet("lake/bcb-microdados/estban_municipio/**/*.parquet", hive_partitioning=True)
por_uf = (
    estban.filter((pl.col("data_base") == 202506) & pl.col("verbete_codigo").is_in(["160", "420"]))
    .group_by("uf", "verbete_codigo")
    .agg((pl.col("valor").sum() / 1e9).alias("bi"))
    .collect()
    .pivot(on="verbete_codigo", index="uf", values="bi")
    .rename({"160": "credito_bi", "420": "poupanca_bi"})
    .sort("credito_bi", descending=True)
)
```

## Referências

- Estatística Bancária Mensal por município (BCB): https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios
- Cosif, capítulo 2 (elenco de contas, coluna E) e capítulo 3 (documento nº 13): https://www.bcb.gov.br/?COSIF
