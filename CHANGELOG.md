# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Corrigido
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

