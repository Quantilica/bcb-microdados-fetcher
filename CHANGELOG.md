# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado
- CI e infraestrutura alinhados ao template (fetcher-template v0.2.1).

## [0.6.0] - 2026-11-16
### Alterado
- **Quebra de layout no lake (só o dataset `cosif`): um Parquet por segmento e mês, em `segmento=/ano=/mes=`.** Os outros datasets não mudam. Antes e depois, em `bcb-microdados/cosif/`:
  - antes: `segmento=bancos/ano=2024/cosif_bancos_2024-12__202412bancos.parquet` (um Parquet por arquivo CSV de cada ZIP, todos os meses do ano na mesma pasta);
  - depois: `segmento=bancos/ano=2024/mes=12/cosif_bancos_202412.parquet` (um por segmento e mês, escrito por `LakeWriter.write_group`; `mes` é texto de 2 dígitos).
  - Os CSVs do mesmo segmento e mês no ZIP, quando têm as mesmas colunas, viram um Parquet só. Se as colunas diferem entre eles, cada conjunto de colunas fica no seu Parquet (`cosif_<segmento>_<AAAAMM>-v2.parquet`...), sem misturar esquemas, e um aviso é registrado no log.
  - Cada linha ganha a coluna `_origem` (o arquivo de origem) e o rodapé do Parquet lista os arquivos (`quantilica.members`, com sha256 e linhas de cada um). `segmento` e `ano` continuam vindo das pastas; `mes` é nova.
  - O segmento e o mês de cada arquivo vêm do início dele (a primeira linha de dados, como antes), lido antes de decidir o grupo: um ZIP que já está no lake não é decodificado de novo. Um arquivo que mudou reescreve o Parquet do mês, mas só ele é decodificado.
  - Na reconversão, o Parquet antigo de cada arquivo (`segmento=X/ano=AAAA/<chave>.parquet`) é apagado depois que o do mês é publicado, só se for deste dataset e não agrupado; um Parquet antigo cujo ZIP já não está no bruto fica no lake (o grupo não tem as linhas dele) e deve ser apagado à mão. O grupo de um mês é a lista completa de arquivos do bruto: um ZIP que sai do bruto sai do Parquet. Se algum ZIP não puder ser lido, nada é descartado nessa execução.
  - `ConvertResult.converted` e `skipped` continuam contando arquivos CSV; cada mensagem de erro do cosif começa por `Erro ao converter COSIF <grupo>` (ou o arquivo, se o erro for na leitura).
  - O que sobrar do layout antigo (`segmento=/ano=/<chave>.parquet`) ao fim de `convert` é listado em `ConvertResult.errors`, com o caminho; nada além do que a migração substitui é apagado.
  - Um arquivo CSV com mais de uma `data_base` (mês) é erro: ele não é gravado no mês da primeira linha, e o grupo daquele mês não é escrito (a mensagem cita o arquivo e os meses encontrados).
  - Um arquivo `.zip` sem a assinatura `PK` (vazio, ou uma página HTML no lugar) do cosif passa a ser erro em `errors`, em vez de ignorado; nessa execução, nenhum grupo descarta arquivos ausentes (`prune=False`).
- O conversor registra `contract_version` (1) e `converter_version` ("1") em cada arquivo do grupo; mudar a leitura do cosif e subir uma delas reconverte o mês.
- Exige `quantilica-analytics>=0.12.0` no extra `analysis` (`write_group`).
- Documentação dos dados do `cosif`: partições, coluna `mes` e `_origem`.

### Adicionado
- Testes de equivalência do agrupamento do cosif: o conteúdo do lake (linhas, colunas e tipos, hash do conteúdo ordenado por segmento, mês e esquema) é igual ao do conversor de um Parquet por arquivo (`tests/golden/lake_antes_do_agrupamento.json`, gerado antes da mudança), mais segunda execução sem reescrita nem decodificação, migração do layout antigo sem linhas duplicadas, `lake_audit` limpo, mudança de esquema, ZIP ilegível e `profile_from_lake` com período mensal.
- Testes: identidade do registro conferida.

### Corrigido
- CI: o pyproject declara o PyPI antes do índice Quantilica (`[[tool.uv.index]]`), e o workflow perde `--index` e `--index-strategy`. Com a estratégia padrão `first-index`, o `uv sync` só consulta o índice para o que não está no PyPI (`quantilica-analytics`) e deixa de receber o 503 intermitente que o GitHub Pages devolve a caminhos inexistentes.

## [0.5.0] - 2026-11-14

### Adicionado
- O fetcher declara os fatos da fonte (`FetcherInfo`: id canônico, apelidos, órgão, licença, página e cadência) para o registro de fetchers da Quantilica.

### Alterado
- Requer `quantilica-core>=0.19.0` (e `quantilica-cli>=0.17.0` como host).

## [0.4.1] - 2026-11-08

### Corrigido
- Pix e SCR por sub-região: um mês que a API do Olinda ainda não publicou (`value` vazio) é pulado com um aviso, em vez de contar como erro e fazer a construção do lake falhar.

## [0.4.0] - 2026-11-08

### Adicionado
- Documentação dos dados em `docs/`, conforme a norma de documentação dos dados: página, dicionário de todas as variáveis e esquema de referência para cada um dos seis datasets. Um teste a verifica.

### Alterado
- ESTBAN: nova coluna `moeda` com o padrão monetário da data-base (`Cz$` até 1988-12, `NCz$`, `Cr$`, `CR$` e `R$` a partir de 1994-07), como no COSIF. Os valores continuam na moeda da época, sem conversão.

### Corrigido
- ESTBAN por município: `AGEN_ESPERADAS` e `AGEN_PROCESSADAS` (quantidade de agências esperadas e processadas da instituição no município) viravam linhas com `verbete_codigo` `agen_esperadas` e `agen_processadas`, misturadas aos saldos. Agora são colunas inteiras de cada linha, e somas por verbete não incluem mais essas contagens.
- ESTBAN: textos (município, instituição) sem os espaços de preenchimento nas pontas.

## [0.3.3] - 2026-11-07

### Corrigido
- ESTBAN: verbetes compostos, publicados pelo BCB como uma coluna só
  (`VERBETE_141_... + VERBETE_142_...`), saíam com `verbete_codigo` igual ao primeiro código
  (`141`) e o restante do cabeçalho em `verbete_nome`. Agora o código traz todos os verbetes
  da soma (`141+142`) e o nome traz os nomes de cada um, separados por `+`. Os valores não
  mudam.

## [0.3.2] - 2026-11-07

### Corrigido
- COSIF: os meses de consórcios sem dados (2009 e 2010) trazem só uma linha com o aviso
  `NAO EXISTE DADOS PARA ESTE SEGMENTO`. Antes, essa linha virava um registro com `saldo`
  nulo e fazia `data_base` e `documento` saírem como texto, o que tornava o esquema do
  dataset incompatível entre partições. Agora esses arquivos não geram partição.

## [0.3.1] - 2026-11-06

### Corrigido
- COSIF, balancetes de conglomerados no layout de largura fixa (2007 a 2010 e parte de
  1994): `saldo` saía como texto, porque o valor vem com espaço no lugar do sinal
  (`" 0000363577595065,18"`), e o código do conglomerado (`COD.CONGLOMERADO`) saía como
  inteiro, sem os zeros à esquerda. Agora `saldo` é numérico, `cod_congl` é texto e os
  campos de texto não trazem mais os espaços de preenchimento.

## [0.3.0] - 2026-11-06

### Corrigido
- COSIF: a conversão falhava no balancete prudencial de 2026-06, cuja coluna `CNPJ`
  traz o código do conglomerado (`C0085111`) depois de milhares de linhas numéricas,
  fora da janela de inferência de tipos.

### Alterado
- COSIF e ESTBAN: identificadores agora são lidos como texto. Antes eram inteiros e
  perdiam os zeros à esquerda (`00000000` virava `0`). No COSIF, isso vale para `cnpj`,
  `agencia`, `cod_congl`, `taxonomia` e `conta`. Na ESTBAN, para `cnpj` e `agencia`.
  Partições gravadas por versões anteriores precisam ser reconvertidas (`force`) para que
  o tipo seja o mesmo em todo o dataset.

## [0.2.0] - 2026-11-04

### Adicionado
- `pix_municipio_transacoes` (TC-03): transações Pix por município, do Olinda
  `Pix_DadosAbertos`, de 2020-11 até o último mês publicado (um JSON por mês, ~5,6 mil
  linhas). O `500` de 30/10 vinha de consultar o conjunto de entidades
  (`_TransacoesPixPorMunicipio`); a *função* responde `200`:
  `TransacoesPixPorMunicipio(DataBase=@DataBase)?@DataBase='AAAAMM'&$filter=AnoMes eq AAAAMM`
  (sem o `$filter`, `DataBase` devolve todos os meses a partir dele, em ordem aleatória).
  Lake: `codigo_ibge` (7) e `uf_ibge` (2) como texto, valores `Decimal(20,2)`, contagens
  inteiras, partição `ano/mes` vinda do próprio dado.
- `scr_sub_regiao` (TC-03): SCR por UF/sub-região/modalidade do Olinda `scr_sub_regiao`
  (função `scr_sub_regiao(DataBase=@DataBase)`), 2006-01 em diante. `risco` só vem
  preenchido (`AA-C`/`D-H`) até 2024-12; de 2025-01 é nulo e de 2026-03 é `N/D`.
- A descoberta tira do fim os meses Olinda ainda vazios (`$top=1`); resposta
  inconclusiva mantém o mês e entra em `DiscoveryReport.olinda_inconclusive`.
- Arquivos Olinda têm nome estável (`<grupo>_AAAA-MM.json`, sem `@data`): o Olinda não manda
  `Last-Modified`, e o carimbo do dia faria baixar tudo de novo a cada execução.
  Use `--force` para rebaixar um mês revisado.

Sondado e não implementado (TC-03):
- `fluxo_cambial_diario`: nenhum serviço Olinda (28 nomes testados, todos 404), nada no CKAN
  do BCB fora do SGS, e as páginas `/estatisticas/fluxocambial` etc. devolvem a SPA em HTML
  (206). A única fonte máquina-a-máquina é o SGS, já coberto por `bcb-sgs-fetcher` e pelo
  pipeline `movimento_cambio_contratado`.
- `scr_carteira_cnae_rating`: o cruzamento CNAE x rating não é publicado. O `scrdata_{ano}.zip`
  (2013 e 2025 conferidos) traz `cnae_ocupacao` e `porte`, mas nenhuma coluna de risco/rating,
  e já é o dataset `scr`; o Olinda `SCR` responde `401`. O risco (`AA-C`/`D-H`) existe só em
  `scr_sub_regiao`, sem CNAE.

- ESTBAN (`municipio`, `agencia`) e COSIF (8 segmentos) de volta ao catálogo, via a
  listagem JSON interna do BCB (`conteudosite` -> `Documentos/byListGuid`), que segue
  respondendo apesar de os caminhos antigos `/estban/...` e `/cosif/...` terem virado
  a SPA (HTML). O catálogo usa sempre a `Url` da listagem (nunca monta o nome),
  deduplica por período (2025-12 tem `X.csv.zip` e `X.zip.csv.zip`) e guarda tamanho,
  data de publicação e duplicatas em `extra`. Listagem que falha é erro contado
  (`DiscoveryReport.listing_errors`), sem derrubar as demais pastas.
  `BCB_DISCOVER=0` desliga a descoberta (testes offline).
- SCR.data dirigido por HEAD: o catálogo só inclui os anos cujo `scrdata_{ano}.zip`
  existe (inclui o ano seguinte, assim que o BCB o publica); HEAD inconclusivo mantém
  o ano e é contado. O BCB não expõe listagem JSON dos ZIPs do SCR.data (a pasta `scr`
  traz só PDFs e a inadimplência por coorte).

### Corrigido
- `convert` identifica `scr_sub_regiao` e `pix_municipio_transacoes` pelo diretório do grupo, antes
  da busca por substring "scr".
- Lake (`scr`, `estban_*`, `cosif`): ZIP com varios membros perdia os membros 2..N (chave de origem so do ZIP; mesma classe do bug A1). Agora cada membro tem chave composta zip+membro, e a leitura e em streaming (transcodificacao em blocos para UTF-8 temporario, sem `ZipFile.read`), com decodificacao estrita (SCR utf-8, ESTBAN latin-1, COSIF cp1252): byte invalido e erro contado do membro, nunca U+FFFD. Reconverter com `--force` os parquets legados de ZIPs multi-membro.
- Política de frescor volta a F2 (`HEAD_FALLBACK_GET`): `REMOTE_ONLY` (F3, para fontes sem validadores) causava re-download diário de fontes com Last-Modified/ETag, porque descartava o Last-Modified e o nome do arquivo caía em `@hoje`.

### Alterado
- Grupos `estban` e `cosif` removidos: os endpoints `/estban/...` e `/cosif/...`
  passaram a devolver a SPA do BCB (HTML em vez de ZIP). O grupo `scr`
  continua íntegro e é o único com URL pública estável.

## [0.1.0] - 2026-11-01

### Adicionado
- Versão inicial do pacote `bcb-microdados-fetcher` (`quantilica bcb-microdados`).
- Suporte a `list`, `check`, `sync` e verificação de frescor via SDK `FetcherApp`.

- Conversor Universal Hive Parquet Lake com `DatasetSpec` em `lake.py`.

