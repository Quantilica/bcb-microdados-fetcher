# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
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

