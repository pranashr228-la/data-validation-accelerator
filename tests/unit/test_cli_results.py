"""Tests for CLI results output helpers."""

from unittest.mock import MagicMock

from dva.cli import _make_filtered, _print_rows


def test_print_rows_empty(capsys):
    _print_rows("Empty Section", [])
    output = capsys.readouterr().out
    assert "-- Empty Section" in output
    assert "(none)" in output


def test_print_rows_with_data(capsys):
    _print_rows("Count", [{"dataset_name": "ds1", "status": "FAIL"}], ["dataset_name", "status"])
    output = capsys.readouterr().out
    assert "dataset_name=ds1" in output
    assert "status=FAIL" in output


def test_make_filtered_returns_hash_summary_before_forensics():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.side_effect = [
        [{"dataset_name": "ds1", "matched_count": 8, "missing_count": 1, "extra_count": 0, "mismatch_count": 1, "status": "FAIL"}],
        [{"dataset_name": "ds1", "primary_key": '{"id": 1}', "record": "{}"}],
    ]
    filtered = _make_filtered(conn, "run-1", "ds1")
    summary_rows = filtered("hash_summary")
    missing_rows = filtered("missing_records")
    assert summary_rows[0]["matched_count"] == 8
    assert missing_rows[0]["primary_key"] == '{"id": 1}'


def test_make_filtered_caps_not_applied_at_filter_level():
    conn = MagicMock()
    rows = [{"dataset_name": "ds1", "primary_key": f'{{"id": {i}}}', "record": "{}"} for i in range(5)]
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = rows
    filtered = _make_filtered(conn, "run-1", None)
    all_rows = filtered("missing_records")
    assert len(all_rows) == 5
    assert len(all_rows[:3]) == 3
