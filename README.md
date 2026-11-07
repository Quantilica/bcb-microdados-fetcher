# bcb-microdados-fetcher

[![CI](https://github.com/Quantilica/bcb-microdados-fetcher/actions/workflows/test.yml/badge.svg)](https://github.com/Quantilica/bcb-microdados-fetcher/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Coletor e conversor Lake Hive para dados abertos de **Banco Central do Brasil — Microdados (SCR, ESTBAN, COSIF)** (`bcb-microdados`), parte do ecossistema [Quantilica](https://quantilica.com).

## Instalação

### Via CLI Quantilica (recomendado)

```bash
quantilica install bcb-microdados
```

Para instalar com suporte à conversão Parquet Lake:

```bash
quantilica install bcb-microdados --extra analysis
```

### Como biblioteca Python

```bash
uv add bcb-microdados-fetcher --index https://index.quantilica.com/simple/
```

Com o extra de análise analítica:

```bash
uv add 'bcb-microdados-fetcher[analysis]' --index https://index.quantilica.com/simple/
```

## Uso via CLI

```bash
# Listar conjuntos disponíveis
quantilica bcb-microdados list

# Verificar novos arquivos e frescor
quantilica bcb-microdados check

# Sincronizar arquivos para o diretório local bruto
quantilica bcb-microdados sync -o /data/bcb-microdados

# Converter acervo bruto para o Universal Hive Parquet Lake
quantilica bcb-microdados convert /data/bcb-microdados /data/lake
```

## Documentação dos dados

O que cada dataset contém, de onde vem, como chega ao lake e os cuidados de uso: [docs/README.md](docs/README.md).

## Licença

Distribuído sob licença MIT. Consulte [LICENSE](LICENSE) para mais detalhes.
