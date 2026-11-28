# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.7.0] - 2026-11-28

### Corrigido

- **Falha de descoberta do ESTBAN e do COSIF não zera mais o grupo com saída 0.** A listagem do BCB (`conteudosite` e `Documentos/byListGuid`) registrava a falha em `DiscoveryReport.listing_errors` e ninguém a lia: com o endpoint em 5xx, o `identificador` mudado ou um formato novo, o grupo ficava sem entrada e o `sync` saía 0 com 0 arquivos, só com aviso. Agora cada falha guarda a causa (`DiscoveryReport.failures`; `group_failures(grupo)` as devolve como `item: causa`) e o `sync` conta uma falha por grupo pedido como erro `descoberta:<grupo>` (a causa na mensagem, também no `--summary-json`): sai 3 se outros grupos baixaram e 1 se nada baixou, com uma linha em ERROR com o grupo e a causa. Contam como falha: `conteudosite` fora do ar ou sem `tronco`/`guidLista`; listagem de uma pasta com erro HTTP ou fora do formato `{"conteudo": [...]}`; pasta com arquivos em que nenhum tem período identificável (formato novo); grupo cujas pastas responderam todas sem arquivo; e ESTBAN/COSIF pedidos com a descoberta desligada (`BCB_DISCOVER=0`), que não têm catálogo estático. Pasta isolada que responde válida e sem item continua sendo só aviso (a fonte não tem arquivo ali). O erro só vale para os grupos pedidos (`--from-plan` não lista, e não conta). `sync --dry-run` registra a falha em ERROR, mas o código de saída dele não muda. O `check` sai com 1 (e não grava o plano de `--out`) quando um grupo pedido falhou na descoberta: na coleta em modo de plano o `check` e o `sync --from-plan` são processos separados e o segundo não lista grupo, então só o `check` pode levar a falha ao código de saída; sem plano, quem opera cai no `sync` completo, que conta `descoberta:<grupo>` e sai 3 ou 1.
- **Download descartado por geração anterior não se repete todo dia.** O descarte (0.6.2) apagava o arquivo e o sidecar do manifesto; o servidor segue servindo a geração antiga com o mesmo `Last-Modified`, então o nome com o carimbo do dia seguinte não existia e o frescor baixava de novo, e descartava de novo, a cada execução. O arquivo continua saindo, mas o sidecar fica: com o arquivo ausente e o sidecar presente, o core dá o download por em dia (mesmo tamanho e `Last-Modified` não mais novo, ou mesmo `ETag`) sem recriar o arquivo. Limite: se o BCB republicar o arquivo com o mesmo `Last-Modified` e o mesmo tamanho (ou o mesmo `ETag`), a mudança não é percebida; só um `Last-Modified` mais novo ou um tamanho diferente leva a baixar de novo, e então vale a regra da geração.
- **`check`: motivo `geracao-descartada`.** Quando o arquivo do carimbo não existe, o sidecar dá o frescor por em dia e há uma versão anterior do mesmo arquivo (isto é, a geração foi descartada), o plano do `check` traz `skip-up-to-date` com o motivo `geracao-descartada` no lugar de `manifest-fresh`. Quem consome o plano e o reclassifica por histórico pode tratar o motivo como decisão de política e manter o `skip`; quem não o conhece o trata como qualquer `skip-up-to-date`, como antes.
- O cliente de descoberta (`BcbMicrodadosClient`) usa o cliente padrão do host quando ele está instalado (respeita `QUANTILICA_HTTP_*`, `QUANTILICA_SSL_VERIFY` e o bundle de CA) e, sem o host, um cliente do core com a verificação TLS lida do ambiente. Antes era um `HttpClient()` sem nada disso.

### Removido

- `BcbMicrodadosClient.download_file`: chamava `download_with_manifest` com `manifest_path=` (que não existe) e sem `source_id`, `dataset_id` e `producer`, isto é, `TypeError` certo na chamada real; o teste mockava o método. Nada a usava: o download é do `sync` do host.

### Adicionado

- Testes: descoberta com falha x pasta vazia válida x formato novo x grupo sem arquivo; `sync` com falha de descoberta (saída 1 e 3, `--summary-json`, apelido de grupo, grupo não pedido); cliente padrão do host e plano B sem o host; frescor depois do descarte por geração com transporte simulado, sem mock do core.

## [0.6.2] - 2026-11-24

### Corrigido

- **ESTBAN: a troca de formato do bruto não deixa mais um Parquet duplicado.** O BCB republicou meses antigos (`2022-12`, `2023-01`, `2023-07`) como ZIP, com o mesmo conteúdo do CSV solto anterior. A chave do Parquet vem do nome do bruto e do membro (`x` para o CSV, `x__x_csv` para o membro do ZIP), então a versão nova gravava ao lado do Parquet antigo, na mesma partição, e a auditoria acusava `versao_duplicada` e `origem_superada`. Agora o conversor remove, por bruto, o Parquet por membro do mesmo bruto (mesma `file_key`, deste dataset) cuja chave o bruto vigente já não gera. A limpeza roda depois de todos os membros do bruto no lake e sem erro, e também na reexecução (em que cada membro só é pulado). Formatos gêmeos da mesma publicação (`x@D.csv` e `x@D.zip`) continuam os dois.
- **ESTBAN: membro só com o cabeçalho vira Parquet vazio, com o esquema do arquivo com linhas.** Antes era pulado, e o arquivo vigente ficava sem Parquet (`sem_parquet`) enquanto o Parquet da versão anterior seguia no lake. `data_base`, `codmun` e `codmun_ibge` saem `Int64`, como nos meses com linhas (não `String`), então `scan_parquet` e o `union_by_name` do DuckDB leem a pasta junta. Sem linhas não há `data_base`: a partição vem do `AAAAMM` do nome do membro e, na falta dele, do nome do bruto; sem data em nenhum dos dois é erro (não cai mais em `ano=2000`).
- **Download com data de geração anterior à da versão vigente é descartado (ESTBAN e COSIF).** O nome do bruto leva o carimbo do `Last-Modified` do servidor e a versão de carimbo mais novo é a vigente. Em 23/11/2026 o BCB sobrescreveu em lote arquivos de meses antigos com gerações anteriores às que já estavam no bruto (`Data de geracao dos dados` de 2023-10-16 contra 2024-03-21, por exemplo; um deles só com o cabeçalho), e a versão mais velha virava a vigente. O fetcher compara a linha `Data de geracao dos dados` do arquivo baixado com a da versão vigente do mesmo arquivo e descarta o download (e o sidecar do manifesto) se for anterior, com aviso no log. Sem a data em qualquer das duas, vale o download. Enquanto o servidor seguir servindo a geração antiga, o arquivo é baixado e descartado a cada execução.

## [0.6.1] - 2026-11-19

### Alterado

- **Build do lake sem mudança não lê o bruto.** O sha256 vem do sidecar `.manifest.json` (`quantilica.analytics.lake.sha256_file`), e o que já está no lake com o mesmo sha256 é pulado antes de transcodificar o membro ou ler o JSON: `scr`, `estban_*` e os datasets do Olinda conferem o rodapé do Parquet em qualquer partição `ano=/mes=` (a partição só se conheceria lendo os dados); o `cosif` confere os membros e `is_current_group` de cada arquivo agrupado sem espiar o início de cada membro. Continuam abertos o índice dos ZIPs e, no `cosif`, o início do membro que não deixa registro no lake (mês sem dados). Uma tarefa `scr` não abre mais os brutos do `estban`, e os sidecars de manifesto são ignorados logo na descoberta.
- **Revisão de layout do conversor.** `LAYOUT_REVISION` (1 hoje) cobre `scr`, `estban_*` e o Olinda, cujo Parquet só guardava o sha256 do bruto: a regra que deriva `ano`/`mes` não era conferida pelo build sem mudança. Subir a constante grava a revisão no rodapé (versão de contrato) e reconverte uma vez o que foi gravado com outra; na revisão 1 nada muda no lake. No `cosif`, a nota junto de `COSIF_CONVERTER_VERSION` diz quando subi-la (mudança de segmento, mês, esquema ou nome do grupo).
- Piso do `quantilica-analytics` em 0.14.0 (sha256 pelo sidecar).

### Corrigido

- O atalho que dá um CSV solto por convertido sem abri-lo valia também para ZIP: um Parquet gravado com a chave do próprio ZIP (layout anterior) e o sha256 dele fazia o build pular os membros ainda não convertidos. Agora só vale para `.csv`/`.txt`, e um erro de E/S ao calcular o sha256 cai no caminho normal (erro da tarefa) em vez de derrubar o `convert`.
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

