"""Tests for bcb-microdados-fetcher storage module."""

import datetime as dt
from pathlib import Path

from bcb_microdados_fetcher.storage import DataRepository


def test_path_for_entry_fallback_timestamp() -> None:
    """With last_modified=None the filename gets today's @YYYYMMDD timestamp."""
    repo = DataRepository(Path("/tmp/test"))
    entry = {"base_id": "scr", "ext": "csv", "group": "scr"}

    # Call path_for_entry with last_modified=None
    path = repo.path_for_entry(entry, last_modified=None)

    # The filename should contain today's date in @YYYYMMDD format
    today_str = dt.date.today().strftime("@%Y%m%d")
    assert today_str in path.name
    assert path.name.startswith(f"scr{today_str}")
    assert path.name.endswith(".csv")


def test_olinda_entry_has_stable_unstamped_name(tmp_path) -> None:
    from bcb_microdados_fetcher.catalog import list_datasets

    entry = list_datasets("pix_municipio_transacoes")[0]
    a = DataRepository(tmp_path).path_for_entry(entry, last_modified=None)
    b = DataRepository(tmp_path).path_for_entry(
        entry, last_modified=__import__("datetime").date(2030, 1, 1)
    )
    assert (
        a
        == b
        == tmp_path
        / "pix_municipio_transacoes"
        / ("pix_municipio_transacoes_2020-11.json")
    )
