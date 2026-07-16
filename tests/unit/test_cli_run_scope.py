"""Tests for CLI run scoping flags."""

import pytest

from dva.engine.run_scope import (
    RunScope,
    parse_dataset_names,
    parse_validation_types,
)


def test_parse_validation_types_aliases():
    types = parse_validation_types("count,hash,stats,agg,dq,duplicates")
    assert types == frozenset(
        {
            "count",
            "row_hash",
            "statistical",
            "aggregate",
            "data_quality",
            "duplicate_keys",
        }
    )


def test_parse_validation_types_default():
    types = parse_validation_types(None)
    assert "count" in types
    assert "row_hash" in types
    assert "aggregate" in types
    assert "statistical" in types
    assert "data_quality" in types
    assert "duplicate_keys" in types
    assert "schema_contract" not in types


def test_parse_validation_types_skip():
    types = parse_validation_types(None, skip="row_hash,aggregate")
    assert "count" in types
    assert "row_hash" not in types
    assert "aggregate" not in types


def test_parse_validation_types_unknown_raises():
    with pytest.raises(ValueError, match="Unknown validation type"):
        parse_validation_types("count,not_a_real_type")


def test_parse_dataset_names_glob():
    names = parse_dataset_names(
        "fact_*,dim_product_validation",
        ["fact_internet_sales_validation", "dim_date_validation", "dim_product_validation"],
    )
    assert names == ["fact_internet_sales_validation", "dim_product_validation"]


def test_parse_dataset_names_no_match_raises():
    with pytest.raises(ValueError, match="No datasets matched"):
        parse_dataset_names("missing_*", ["dim_date_validation"])


def test_run_scope_includes():
    scope = RunScope(
        dataset_names=("fact_internet_sales_validation",),
        validation_types=frozenset({"count", "statistical"}),
    )
    assert scope.includes_dataset("fact_internet_sales_validation")
    assert not scope.includes_dataset("dim_date_validation")
    assert scope.includes_validation("count")
    assert not scope.includes_validation("row_hash")
