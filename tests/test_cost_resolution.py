import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from build_fact_sales_margin import (
    AVOCADO_COST,
    COST_ESTIMATION_MULTIPLIER,
    DRINK_KEYWORDS,
    resolve_unit_cost,
)

PARQUET_PATH = Path("data/analytics/fact_sales_margin.parquet")


def make_row(
    product_name_norm="HAMBURGUESA",
    non_product_revenue=False,
    cantidad=1.0,
    importe=100.0,
    bundle_code=None,
    product_code=None,
) -> pd.Series:
    return pd.Series({
        "product_name_norm": product_name_norm,
        "non_product_revenue": non_product_revenue,
        "cantidad": cantidad,
        "importe": importe,
        "bundle_code": bundle_code,
        "product_code": product_code,
    })


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="session")
def margin_df():
    return pd.read_parquet(PARQUET_PATH)


# ============================================================
# Tests
# ============================================================

def test_bundle_cost_takes_precedence_over_product_cost():
    row = make_row(bundle_code="bundle_1", product_code="burger_cheese")
    cost, estimated = resolve_unit_cost(
        row,
        product_costs={"burger_cheese": 27.75},
        bundle_costs={"bundle_1": 45.0},
        expected_drink_cost=8.0,
    )
    assert cost == pytest.approx(45.0)
    assert estimated is False


@pytest.mark.parametrize("keyword", DRINK_KEYWORDS)
def test_drink_keyword_uses_expected_drink_cost(keyword):
    row = make_row(product_name_norm=keyword)
    cost, estimated = resolve_unit_cost(
        row,
        product_costs={},
        bundle_costs={},
        expected_drink_cost=12.5,
    )
    assert cost == pytest.approx(12.5)
    assert estimated is False


def test_extra_aguacate_uses_fixed_cost():
    row = make_row(product_name_norm="EXTRA AGUACATE")
    cost, estimated = resolve_unit_cost(
        row,
        product_costs={},
        bundle_costs={},
        expected_drink_cost=8.0,
    )
    assert cost == pytest.approx(AVOCADO_COST)
    assert estimated is False


def test_unmapped_product_uses_fallback_with_flag():
    row = make_row(product_name_norm="PRODUCTO DESCONOCIDO", cantidad=2.0, importe=100.0)
    cost, estimated = resolve_unit_cost(
        row,
        product_costs={},
        bundle_costs={},
        expected_drink_cost=8.0,
    )
    assert cost == pytest.approx((100.0 / 2.0) * COST_ESTIMATION_MULTIPLIER)
    assert estimated is True


def test_fallback_flag_is_true():
    row = make_row(product_name_norm="MYSTERY ITEM", cantidad=1.0, importe=50.0)
    _, estimated = resolve_unit_cost(
        row,
        product_costs={},
        bundle_costs={},
        expected_drink_cost=8.0,
    )
    assert estimated is True


@pytest.mark.parametrize("name,bundle_code,product_code,bundle_costs,product_costs", [
    ("HAMBURGUESA", "b1",  None,           {"b1": 45.0}, {}),
    ("HAMBURGUESA", None,  "burger_cheese", {},           {"burger_cheese": 27.75}),
    ("REFRESCO",    None,  None,            {},           {}),
    ("EXTRA AGUACATE", None, None,          {},           {}),
])
def test_known_cost_flag_is_false(name, bundle_code, product_code, bundle_costs, product_costs):
    row = make_row(product_name_norm=name, bundle_code=bundle_code, product_code=product_code)
    _, estimated = resolve_unit_cost(row, product_costs, bundle_costs, expected_drink_cost=8.0)
    assert estimated is False


def test_unit_cost_never_nan_on_full_dataset(margin_df):
    nan_count = margin_df["unit_cost"].isna().sum()
    assert nan_count == 0, f"Found {nan_count} NaN values in unit_cost"


def test_non_product_revenue_zero_margin():
    row = make_row(
        product_name_norm="ENVIO UBER",
        non_product_revenue=True,
        cantidad=1.0,
        importe=25.0,
    )
    cost, estimated = resolve_unit_cost(
        row,
        product_costs={},
        bundle_costs={},
        expected_drink_cost=8.0,
    )
    gross_margin = row["importe"] - cost * row["cantidad"]
    assert gross_margin == pytest.approx(0.0)
    assert estimated is False
