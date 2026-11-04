"""Pytest configuration and fixtures for bcb-microdados-fetcher."""

import os

# Testes offline: a descoberta de catálogo (rede) fica desligada por padrão.
os.environ.setdefault("BCB_DISCOVER", "0")
