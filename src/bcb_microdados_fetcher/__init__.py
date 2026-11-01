"""Coletor e conversor Lake Hive de microdados do Banco Central (SCR, ESTBAN, COSIF)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bcb-microdados-fetcher")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
