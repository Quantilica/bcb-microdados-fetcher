"""Tests for bcb-microdados-fetcher storage module."""

import datetime as dt
from pathlib import Path

from bcb_microdados_fetcher.storage import DataRepository


def test_path_for_entry_fallback_timestamp() -> None:
    """Test that when last_modified=None, the filename gets today's @YYYYMMDD timestamp."""
    repo = DataRepository(Path("/tmp/test"))
    entry = {"base_id": "scr", "ext": "csv", "group": "scr"}

    # Call path_for_entry with last_modified=None
    path = repo.path_for_entry(entry, last_modified=None)

    # The filename should contain today's date in @YYYYMMDD format
    today_str = dt.date.today().strftime("@%Y%m%d")
    assert today_str in path.name
    assert path.name.startswith(f"scr{today_str}")
    assert path.name.endswith(".csv")