#!/usr/bin/env python3
"""
Standalone schema.txt generator.

Produces a realistic SQL DDL file (PostgreSQL dialect) with CREATE TABLE and
CREATE VIEW statements that form a layered dependency DAG suitable for the
column-lineage web app.

Usage:
    python generate_schema.py                          # default e-commerce domain
    python generate_schema.py --domain healthcare      # healthcare domain
    python generate_schema.py --domain saas            # SaaS / subscription domain
    python generate_schema.py --domain ecommerce       # explicit e-commerce
    python generate_schema.py -o my_schema.txt         # custom output path
    python generate_schema.py --seed 42                # reproducible output
    python generate_schema.py --tables 4 --depth 3     # control table count & view depth
    python generate_schema.py --include-dbt            # add dbt Jinja syntax examples
    python generate_schema.py --dry-run                # print to stdout only
"""

from __future__ import annotations

import argparse
import random
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Column / table / view domain definitions
# ---------------------------------------------------------------------------

@dataclass
class ColumnDef:
    """A column definition for a base table."""
    name: str
    sql_type: str
    constraints: str = ""   # e.g. "NOT NULL", "PRIMARY KEY", "DEFAULT 0"
    fk_ref: str = ""        # e.g. "REFERENCES raw_orders(order_id)"


@dataclass
class TableDef:
    """A base (raw/source) table blueprint."""
    name: str
    columns: List[ColumnDef]
    comment: str = ""


@dataclass
class ViewColumn:
    """A column produced by a view."""
    alias: str
    expression: str
    source_columns: List[Tuple[str, str]]  # [(table_alias, column_name), ...]


@dataclass
class ViewDef:
    """A view blueprint."""
    name: str
    layer: str            # stg, int, fct, mart, rpt
    depends_on: List[str] # names of upstream tables/views
    sql: str = ""         # filled by the builder
    comment: str = ""


# ---------------------------------------------------------------------------
# Domain: e-commerce (default, modeled after the existing schema.txt)
# ---------------------------------------------------------------------------

def _ecommerce_tables(rng: random.Random, count: int) -> List[TableDef]:
    """Return a list of e-commerce base tables."""
    all_tables = [
        TableDef(
            name="raw_customers",
            comment="Customer master data.",
            columns=[
                ColumnDef("customer_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("email", "TEXT", "NOT NULL"),
                ColumnDef("first_name", "TEXT"),
                ColumnDef("last_name", "TEXT"),
                ColumnDef("signup_ts", "TIMESTAMPTZ", "NOT NULL"),
                ColumnDef("acquisition_channel", "TEXT"),
                ColumnDef("country_code", "TEXT"),
                ColumnDef("marketing_opt_in", "BOOLEAN", "DEFAULT FALSE"),
                ColumnDef("customer_status", "TEXT", "NOT NULL"),
            ],
        ),
        TableDef(
            name="raw_orders",
            comment="Order header records.",
            columns=[
                ColumnDef("order_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("customer_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_customers(customer_id)"),
                ColumnDef("order_number", "TEXT", "NOT NULL"),
                ColumnDef("order_ts", "TIMESTAMPTZ", "NOT NULL"),
                ColumnDef("order_status", "TEXT", "NOT NULL"),
                ColumnDef("currency", "TEXT", "NOT NULL"),
                ColumnDef("subtotal_amount", "NUMERIC(12, 2)", "NOT NULL"),
                ColumnDef("shipping_amount", "NUMERIC(12, 2)",
                          "NOT NULL DEFAULT 0"),
                ColumnDef("tax_amount", "NUMERIC(12, 2)", "NOT NULL DEFAULT 0"),
                ColumnDef("discount_amount", "NUMERIC(12, 2)",
                          "NOT NULL DEFAULT 0"),
                ColumnDef("coupon_code", "TEXT"),
                ColumnDef("sales_channel", "TEXT", "NOT NULL"),
            ],
        ),
        TableDef(
            name="raw_order_items",
            comment="Line-item detail per order.",
            columns=[
                ColumnDef("order_item_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("order_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_orders(order_id)"),
                ColumnDef("product_id", "BIGINT", "NOT NULL"),
                ColumnDef("sku", "TEXT", "NOT NULL"),
                ColumnDef("quantity", "INTEGER", "NOT NULL"),
                ColumnDef("unit_price_amount", "NUMERIC(12, 2)", "NOT NULL"),
                ColumnDef("item_discount_amt", "NUMERIC(12, 2)",
                          "NOT NULL DEFAULT 0"),
                ColumnDef("item_tax_amount", "NUMERIC(12, 2)",
                          "NOT NULL DEFAULT 0"),
                ColumnDef("fulfillment_status", "TEXT", "NOT NULL"),
            ],
        ),
        TableDef(
            name="raw_products",
            comment="Product catalog.",
            columns=[
                ColumnDef("product_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("sku", "TEXT", "NOT NULL"),
                ColumnDef("product_name", "TEXT", "NOT NULL"),
                ColumnDef("category", "TEXT"),
                ColumnDef("subcategory", "TEXT"),
                ColumnDef("brand", "TEXT"),
                ColumnDef("standard_cost_amt", "NUMERIC(12, 2)"),
                ColumnDef("is_active", "BOOLEAN", "NOT NULL DEFAULT TRUE"),
                ColumnDef("launched_date", "DATE"),
            ],
        ),
        TableDef(
            name="raw_payments",
            comment="Payment events per order.",
            columns=[
                ColumnDef("payment_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("order_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_orders(order_id)"),
                ColumnDef("payment_ts", "TIMESTAMPTZ", "NOT NULL"),
                ColumnDef("payment_method", "TEXT", "NOT NULL"),
                ColumnDef("payment_status", "TEXT", "NOT NULL"),
                ColumnDef("payment_type", "TEXT", "NOT NULL"),
                ColumnDef("amount", "NUMERIC(12, 2)", "NOT NULL"),
                ColumnDef("processor_fee", "NUMERIC(12, 2)",
                          "NOT NULL DEFAULT 0"),
                ColumnDef("refunded_amount", "NUMERIC(12, 2)",
                          "NOT NULL DEFAULT 0"),
                ColumnDef("gateway_txn_id", "TEXT"),
            ],
        ),
        TableDef(
            name="raw_inventory",
            comment="Warehouse inventory snapshots.",
            columns=[
                ColumnDef("inventory_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("product_id", "BIGINT", "NOT NULL"),
                ColumnDef("warehouse_code", "TEXT", "NOT NULL"),
                ColumnDef("snapshot_date", "DATE", "NOT NULL"),
                ColumnDef("quantity_on_hand", "INTEGER", "NOT NULL DEFAULT 0"),
                ColumnDef("quantity_reserved", "INTEGER", "NOT NULL DEFAULT 0"),
                ColumnDef("reorder_point", "INTEGER"),
            ],
        ),
    ]
    return all_tables[:min(count, len(all_tables))]


def _ecommerce_views(tables: List[TableDef], rng: random.Random,
                     depth: int, use_dbt: bool) -> List[str]:
    """Build e-commerce view SQL strings organized in layers."""
    table_names = [t.name for t in tables]
    views: List[str] = []

    # Helper to decide whether to wrap a table ref in dbt syntax
    def _tref(name: str) -> str:
        if not use_dbt:
            return name
        # tables get {{ source(...) }}, views get {{ ref(...) }}
        if name.startswith("raw_"):
            return "{{ source('raw', '%s') }}" % name
        return "{{ ref('%s') }}" % name

    # ---- Layer 1: staging views ----
    if "raw_orders" in table_names and "raw_payments" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Staging: order-level enrichment with payment aggregates.
            CREATE VIEW stg_orders_enriched AS
            WITH payment_agg AS (
                SELECT
                    p.order_id,
                    SUM(CASE WHEN p.payment_type = 'charge' THEN p.amount ELSE 0 END) AS charged_amount,
                    SUM(CASE WHEN p.payment_type = 'refund' THEN p.amount ELSE 0 END) AS refund_amount,
                    SUM(p.processor_fee) AS total_processor_fee,
                    MIN(p.payment_ts) FILTER (WHERE p.payment_type = 'charge') AS first_charge_ts,
                    MAX(p.payment_ts) AS last_payment_event_ts,
                    COUNT(*) FILTER (WHERE p.payment_status = 'failed') AS failed_payment_events
                FROM {_tref('raw_payments')} p
                GROUP BY p.order_id
            )
            SELECT
                o.order_id,
                o.customer_id,
                o.order_number,
                o.order_ts,
                o.order_ts::DATE AS order_date,
                DATE_TRUNC('month', o.order_ts)::DATE AS order_month,
                LOWER(TRIM(o.order_status)) AS order_status_normalized,
                CASE
                    WHEN LOWER(o.order_status) IN ('paid', 'complete', 'shipped') THEN 'completed'
                    WHEN LOWER(o.order_status) IN ('cancelled', 'canceled') THEN 'cancelled'
                    WHEN LOWER(o.order_status) IN ('returned', 'refunded') THEN 'returned'
                    ELSE 'open'
                END AS order_status_bucket,
                o.currency,
                COALESCE(o.subtotal_amount, 0)
                    + COALESCE(o.shipping_amount, 0)
                    + COALESCE(o.tax_amount, 0)
                    - COALESCE(o.discount_amount, 0) AS order_total_amount,
                COALESCE(pa.charged_amount, 0) AS charged_amount,
                COALESCE(pa.refund_amount, 0) AS refund_amount,
                COALESCE(pa.total_processor_fee, 0) AS total_processor_fee,
                COALESCE(pa.charged_amount, 0) - COALESCE(pa.refund_amount, 0) AS net_collected_amount,
                pa.first_charge_ts,
                pa.last_payment_event_ts,
                COALESCE(pa.failed_payment_events, 0) AS failed_payment_events,
                o.sales_channel,
                NULLIF(UPPER(TRIM(o.coupon_code)), '') AS coupon_code_normalized
            FROM {_tref('raw_orders')} o
            LEFT JOIN payment_agg pa
                ON pa.order_id = o.order_id;"""))

    if ("raw_order_items" in table_names and "raw_orders" in table_names
            and "raw_products" in table_names):
        views.append(textwrap.dedent(f"""\
            -- Staging: item-level pricing and margin.
            CREATE VIEW stg_line_items_priced AS
            SELECT
                oi.order_item_id,
                oi.order_id,
                o.customer_id,
                o.order_ts,
                o.order_ts::DATE AS order_date,
                oi.product_id,
                COALESCE(p.sku, oi.sku) AS resolved_sku,
                p.product_name,
                COALESCE(p.category, 'uncategorized') AS category,
                COALESCE(p.subcategory, 'unknown') AS subcategory,
                p.brand,
                oi.quantity,
                oi.unit_price_amount,
                oi.quantity * oi.unit_price_amount AS gross_line_amount,
                (oi.quantity * oi.unit_price_amount) - COALESCE(oi.item_discount_amt, 0) AS net_line_amount,
                COALESCE(p.standard_cost_amt, 0) * oi.quantity AS estimated_line_cost,
                ((oi.quantity * oi.unit_price_amount) - COALESCE(oi.item_discount_amt, 0))
                    - (COALESCE(p.standard_cost_amt, 0) * oi.quantity) AS estimated_line_margin,
                CASE
                    WHEN oi.fulfillment_status IN ('shipped', 'delivered') THEN TRUE
                    ELSE FALSE
                END AS is_fulfilled
            FROM {_tref('raw_order_items')} oi
            JOIN {_tref('raw_orders')} o
                ON o.order_id = oi.order_id
            LEFT JOIN {_tref('raw_products')} p
                ON p.product_id = oi.product_id;"""))

    if depth < 2:
        return views

    # ---- Layer 2: intermediate / fact views ----
    if "raw_customers" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Intermediate: customer order metrics aggregated from staging.
            CREATE VIEW int_customer_order_metrics AS
            WITH customer_orders AS (
                SELECT
                    c.customer_id,
                    LOWER(c.email) AS email_normalized,
                    TRIM(COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '')) AS full_name,
                    c.signup_ts::DATE AS signup_date,
                    COALESCE(c.acquisition_channel, 'unknown') AS acquisition_channel,
                    COALESCE(c.country_code, 'ZZ') AS country_code,
                    c.marketing_opt_in,
                    c.customer_status,
                    soe.order_id,
                    soe.order_date,
                    soe.order_status_bucket,
                    soe.order_total_amount,
                    soe.net_collected_amount,
                    soe.refund_amount,
                    soe.total_processor_fee,
                    soe.sales_channel,
                    soe.coupon_code_normalized
                FROM {_tref('raw_customers')} c
                LEFT JOIN stg_orders_enriched soe
                    ON soe.customer_id = c.customer_id
            )
            SELECT
                customer_id,
                email_normalized,
                full_name,
                signup_date,
                acquisition_channel,
                country_code,
                marketing_opt_in,
                customer_status,
                MIN(order_date) AS first_order_date,
                MAX(order_date) AS last_order_date,
                COUNT(order_id) AS lifetime_order_count,
                COUNT(order_id) FILTER (WHERE order_status_bucket = 'completed') AS completed_order_count,
                COUNT(order_id) FILTER (WHERE order_status_bucket = 'returned') AS returned_order_count,
                SUM(COALESCE(order_total_amount, 0)) AS lifetime_order_total_amount,
                SUM(COALESCE(net_collected_amount, 0)) AS lifetime_net_collected_amount,
                SUM(COALESCE(refund_amount, 0)) AS lifetime_refund_amount,
                SUM(COALESCE(total_processor_fee, 0)) AS lifetime_processor_fee_amount,
                SUM(COALESCE(net_collected_amount, 0))
                    / NULLIF(COUNT(order_id) FILTER (WHERE order_status_bucket = 'completed'), 0)
                    AS avg_completed_order_value,
                MAX(CASE WHEN coupon_code_normalized IS NOT NULL THEN 1 ELSE 0 END)::BOOLEAN AS has_used_coupon,
                MAX(CASE WHEN sales_channel = 'marketplace' THEN 1 ELSE 0 END)::BOOLEAN AS has_marketplace_order
            FROM customer_orders
            GROUP BY
                customer_id, email_normalized, full_name, signup_date,
                acquisition_channel, country_code, marketing_opt_in, customer_status;"""))

    views.append(textwrap.dedent("""\
        -- Fact: daily revenue events from line items and refunds via UNION ALL.
        CREATE VIEW fct_customer_revenue_daily AS
        WITH line_revenue AS (
            SELECT
                slip.customer_id,
                slip.order_id,
                slip.order_date AS revenue_date,
                'item_revenue' AS revenue_event_type,
                SUM(slip.net_line_amount) AS revenue_amount,
                SUM(slip.estimated_line_cost) * -1 AS cost_amount,
                SUM(slip.estimated_line_margin) AS margin_amount,
                COUNT(DISTINCT slip.product_id) AS distinct_products
            FROM stg_line_items_priced slip
            GROUP BY slip.customer_id, slip.order_id, slip.order_date
        ),
        refund_events AS (
            SELECT
                soe.customer_id,
                soe.order_id,
                COALESCE(soe.last_payment_event_ts::DATE, soe.order_date) AS revenue_date,
                'refund' AS revenue_event_type,
                SUM(soe.refund_amount) * -1 AS revenue_amount,
                0::NUMERIC(12, 2) AS cost_amount,
                SUM(soe.refund_amount) * -1 AS margin_amount,
                0 AS distinct_products
            FROM stg_orders_enriched soe
            WHERE soe.refund_amount > 0
            GROUP BY soe.customer_id, soe.order_id,
                     COALESCE(soe.last_payment_event_ts::DATE, soe.order_date)
        ),
        all_events AS (
            SELECT * FROM line_revenue
            UNION ALL
            SELECT * FROM refund_events
        )
        SELECT
            customer_id,
            revenue_date,
            DATE_TRUNC('month', revenue_date)::DATE AS revenue_month,
            SUM(revenue_amount) AS daily_revenue_amount,
            SUM(cost_amount) AS daily_cost_amount,
            SUM(margin_amount) AS daily_margin_amount,
            SUM(distinct_products) AS daily_distinct_products,
            COUNT(DISTINCT order_id) AS daily_order_count,
            COUNT(*) FILTER (WHERE revenue_event_type = 'refund') AS refund_event_count,
            SUM(revenue_amount) FILTER (WHERE revenue_event_type = 'refund') AS refund_revenue_amount
        FROM all_events
        GROUP BY customer_id, revenue_date, DATE_TRUNC('month', revenue_date)::DATE;"""))

    if depth < 3:
        return views

    # ---- Layer 3: mart views ----
    views.append(textwrap.dedent("""\
        -- Mart: customer LTV segmentation with window functions.
        CREATE VIEW mart_customer_ltv_segments AS
        WITH revenue_rollup AS (
            SELECT
                fcrd.customer_id,
                MIN(fcrd.revenue_date) AS first_revenue_date,
                MAX(fcrd.revenue_date) AS last_revenue_date,
                SUM(fcrd.daily_revenue_amount) AS total_revenue_amount,
                SUM(fcrd.daily_cost_amount) AS total_cost_amount,
                SUM(fcrd.daily_margin_amount) AS total_margin_amount,
                SUM(fcrd.refund_event_count) AS total_refund_events,
                SUM(COALESCE(fcrd.refund_revenue_amount, 0)) AS total_refund_revenue_amount
            FROM fct_customer_revenue_daily fcrd
            GROUP BY fcrd.customer_id
        ),
        scored AS (
            SELECT
                icom.customer_id,
                icom.email_normalized,
                icom.full_name,
                icom.signup_date,
                icom.acquisition_channel,
                icom.country_code,
                icom.marketing_opt_in,
                icom.customer_status,
                icom.first_order_date,
                icom.last_order_date,
                icom.lifetime_order_count,
                icom.completed_order_count,
                icom.returned_order_count,
                icom.lifetime_net_collected_amount,
                icom.avg_completed_order_value,
                icom.has_used_coupon,
                icom.has_marketplace_order,
                COALESCE(rr.total_revenue_amount, 0) AS total_revenue_amount,
                COALESCE(rr.total_cost_amount, 0) AS total_cost_amount,
                COALESCE(rr.total_margin_amount, 0) AS total_margin_amount,
                COALESCE(rr.total_refund_events, 0) AS total_refund_events,
                COALESCE(rr.total_refund_revenue_amount, 0) AS total_refund_revenue_amount,
                rr.first_revenue_date,
                rr.last_revenue_date,
                CASE
                    WHEN icom.first_order_date IS NULL THEN NULL
                    ELSE CURRENT_DATE - icom.first_order_date
                END AS customer_age_days,
                COALESCE(rr.total_revenue_amount, 0)
                    - COALESCE(icom.lifetime_processor_fee_amount, 0) AS ltv_after_fees_amount
            FROM int_customer_order_metrics icom
            LEFT JOIN revenue_rollup rr
                ON rr.customer_id = icom.customer_id
        )
        SELECT
            customer_id,
            email_normalized,
            full_name,
            signup_date,
            acquisition_channel,
            country_code,
            marketing_opt_in,
            customer_status,
            first_order_date,
            last_order_date,
            first_revenue_date,
            last_revenue_date,
            customer_age_days,
            lifetime_order_count,
            completed_order_count,
            returned_order_count,
            total_revenue_amount,
            total_cost_amount,
            total_margin_amount,
            ltv_after_fees_amount,
            avg_completed_order_value,
            total_refund_events,
            total_refund_revenue_amount,
            has_used_coupon,
            has_marketplace_order,
            DENSE_RANK() OVER (ORDER BY total_revenue_amount DESC) AS revenue_rank,
            NTILE(5) OVER (ORDER BY total_revenue_amount DESC) AS revenue_quintile,
            CASE
                WHEN lifetime_order_count = 0 THEN 'prospect'
                WHEN total_revenue_amount >= 1000 AND completed_order_count >= 5 THEN 'vip'
                WHEN total_refund_events >= 3 THEN 'refund_risk'
                WHEN customer_age_days <= 30 THEN 'new_customer'
                ELSE 'standard'
            END AS customer_segment,
            CASE
                WHEN total_margin_amount < 0 THEN 'negative_margin'
                WHEN total_margin_amount / NULLIF(total_revenue_amount, 0) >= 0.5 THEN 'high_margin'
                WHEN total_margin_amount / NULLIF(total_revenue_amount, 0) >= 0.2 THEN 'medium_margin'
                ELSE 'low_margin'
            END AS margin_segment
        FROM scored;"""))

    if depth < 4:
        return views

    # ---- Layer 4: reporting views ----
    views.append(textwrap.dedent("""\
        -- Report: cohort growth analysis over the LTV mart.
        CREATE VIEW rpt_customer_growth_cohorts AS
        WITH cohort_base AS (
            SELECT
                mcls.customer_id,
                mcls.signup_date,
                DATE_TRUNC('month', mcls.signup_date)::DATE AS signup_month,
                mcls.acquisition_channel,
                mcls.country_code,
                mcls.customer_segment,
                mcls.margin_segment,
                mcls.completed_order_count,
                mcls.returned_order_count,
                mcls.total_revenue_amount,
                mcls.total_margin_amount,
                mcls.ltv_after_fees_amount,
                mcls.customer_age_days,
                CASE
                    WHEN mcls.first_order_date IS NULL THEN 'never_ordered'
                    WHEN mcls.first_order_date <= mcls.signup_date + INTERVAL '7 days' THEN 'converted_week_1'
                    WHEN mcls.first_order_date <= mcls.signup_date + INTERVAL '30 days' THEN 'converted_month_1'
                    ELSE 'converted_later'
                END AS conversion_speed_bucket
            FROM mart_customer_ltv_segments mcls
        ),
        cohort_rollup AS (
            SELECT
                signup_month,
                acquisition_channel,
                country_code,
                COUNT(*) AS cohort_customer_count,
                COUNT(*) FILTER (WHERE conversion_speed_bucket <> 'never_ordered') AS converted_customer_count,
                COUNT(*) FILTER (WHERE customer_segment = 'vip') AS vip_customer_count,
                COUNT(*) FILTER (WHERE margin_segment = 'negative_margin') AS negative_margin_customer_count,
                SUM(total_revenue_amount) AS cohort_revenue_amount,
                SUM(total_margin_amount) AS cohort_margin_amount,
                SUM(ltv_after_fees_amount) AS cohort_ltv_after_fees_amount,
                SUM(completed_order_count) AS cohort_completed_orders,
                SUM(returned_order_count) AS cohort_returned_orders,
                AVG(customer_age_days) AS avg_customer_age_days
            FROM cohort_base
            GROUP BY signup_month, acquisition_channel, country_code
        )
        SELECT
            signup_month,
            acquisition_channel,
            country_code,
            cohort_customer_count,
            converted_customer_count,
            converted_customer_count::NUMERIC / NULLIF(cohort_customer_count, 0) AS conversion_rate,
            vip_customer_count::NUMERIC / NULLIF(cohort_customer_count, 0) AS vip_rate,
            negative_margin_customer_count::NUMERIC / NULLIF(cohort_customer_count, 0) AS negative_margin_rate,
            cohort_revenue_amount,
            cohort_margin_amount,
            cohort_ltv_after_fees_amount,
            cohort_revenue_amount / NULLIF(cohort_customer_count, 0) AS revenue_per_customer,
            cohort_ltv_after_fees_amount / NULLIF(cohort_customer_count, 0) AS ltv_per_customer,
            cohort_margin_amount / NULLIF(cohort_revenue_amount, 0) AS cohort_margin_rate,
            cohort_completed_orders,
            cohort_returned_orders,
            cohort_returned_orders::NUMERIC / NULLIF(cohort_completed_orders, 0) AS cohort_return_rate,
            avg_customer_age_days,
            cohort_revenue_amount
                - LAG(cohort_revenue_amount) OVER (
                    PARTITION BY acquisition_channel, country_code
                    ORDER BY signup_month
                ) AS revenue_delta_vs_prior_cohort,
            RANK() OVER (
                PARTITION BY signup_month
                ORDER BY cohort_ltv_after_fees_amount DESC
            ) AS cohort_ltv_rank_in_month
        FROM cohort_rollup;"""))

    views.append(textwrap.dedent("""\
        -- Report: executive revenue dashboard combining mart and fact layers.
        CREATE VIEW rpt_executive_revenue_dashboard AS
        WITH segment_rollup AS (
            SELECT
                DATE_TRUNC('month', mcls.signup_date)::DATE AS signup_month,
                mcls.acquisition_channel,
                mcls.country_code,
                mcls.customer_segment,
                COUNT(*) AS customer_count,
                SUM(mcls.total_revenue_amount) AS segment_total_revenue_amount,
                SUM(mcls.total_margin_amount) AS segment_total_margin_amount,
                SUM(mcls.ltv_after_fees_amount) AS segment_ltv_after_fees_amount,
                AVG(mcls.revenue_rank) AS avg_revenue_rank,
                COUNT(*) FILTER (WHERE mcls.customer_segment = 'vip') AS vip_count,
                COUNT(*) FILTER (WHERE mcls.customer_segment = 'refund_risk') AS refund_risk_count
            FROM mart_customer_ltv_segments mcls
            GROUP BY
                DATE_TRUNC('month', mcls.signup_date)::DATE,
                mcls.acquisition_channel,
                mcls.country_code,
                mcls.customer_segment
        ),
        fact_monthly AS (
            SELECT
                fcrd.revenue_month,
                SUM(fcrd.daily_revenue_amount) AS platform_revenue_amount,
                SUM(fcrd.daily_margin_amount) AS platform_margin_amount,
                SUM(fcrd.daily_order_count) AS platform_order_count,
                SUM(fcrd.refund_event_count) AS platform_refund_event_count
            FROM fct_customer_revenue_daily fcrd
            GROUP BY fcrd.revenue_month
        )
        SELECT
            sr.signup_month,
            sr.acquisition_channel,
            sr.country_code,
            sr.customer_segment,
            sr.customer_count,
            sr.segment_total_revenue_amount,
            sr.segment_total_margin_amount,
            sr.segment_ltv_after_fees_amount,
            sr.vip_count,
            sr.refund_risk_count,
            fm.platform_revenue_amount,
            fm.platform_margin_amount,
            fm.platform_order_count,
            fm.platform_refund_event_count,
            sr.segment_total_revenue_amount / NULLIF(fm.platform_revenue_amount, 0) AS segment_revenue_share,
            sr.segment_total_margin_amount / NULLIF(sr.segment_total_revenue_amount, 0) AS segment_margin_rate,
            sr.refund_risk_count::NUMERIC / NULLIF(sr.customer_count, 0) AS segment_risk_rate,
            CASE
                WHEN sr.segment_total_margin_amount / NULLIF(sr.segment_total_revenue_amount, 0) >= 0.4
                    THEN 'invest'
                WHEN sr.segment_total_margin_amount / NULLIF(sr.segment_total_revenue_amount, 0) < 0
                    OR sr.refund_risk_count::NUMERIC / NULLIF(sr.customer_count, 0) >= 0.30
                    THEN 'intervene'
                ELSE 'maintain'
            END AS executive_action,
            DENSE_RANK() OVER (
                PARTITION BY sr.signup_month
                ORDER BY sr.segment_total_revenue_amount DESC
            ) AS segment_revenue_rank
        FROM segment_rollup sr
        LEFT JOIN fact_monthly fm
            ON fm.revenue_month = sr.signup_month;"""))

    return views


# ---------------------------------------------------------------------------
# Domain: healthcare
# ---------------------------------------------------------------------------

def _healthcare_tables(rng: random.Random, count: int) -> List[TableDef]:
    all_tables = [
        TableDef(
            name="raw_patients",
            comment="Patient demographic records.",
            columns=[
                ColumnDef("patient_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("mrn", "TEXT", "NOT NULL"),
                ColumnDef("first_name", "TEXT"),
                ColumnDef("last_name", "TEXT"),
                ColumnDef("date_of_birth", "DATE", "NOT NULL"),
                ColumnDef("gender", "TEXT"),
                ColumnDef("zip_code", "TEXT"),
                ColumnDef("insurance_type", "TEXT"),
                ColumnDef("primary_care_provider_id", "BIGINT"),
                ColumnDef("enrollment_date", "DATE", "NOT NULL"),
                ColumnDef("patient_status", "TEXT", "NOT NULL"),
            ],
        ),
        TableDef(
            name="raw_encounters",
            comment="Clinical encounter events.",
            columns=[
                ColumnDef("encounter_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("patient_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_patients(patient_id)"),
                ColumnDef("provider_id", "BIGINT", "NOT NULL"),
                ColumnDef("encounter_ts", "TIMESTAMPTZ", "NOT NULL"),
                ColumnDef("encounter_type", "TEXT", "NOT NULL"),
                ColumnDef("facility_code", "TEXT", "NOT NULL"),
                ColumnDef("chief_complaint", "TEXT"),
                ColumnDef("discharge_disposition", "TEXT"),
                ColumnDef("length_of_stay_hours", "NUMERIC(8, 2)"),
            ],
        ),
        TableDef(
            name="raw_diagnoses",
            comment="Diagnosis codes per encounter.",
            columns=[
                ColumnDef("diagnosis_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("encounter_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_encounters(encounter_id)"),
                ColumnDef("icd10_code", "TEXT", "NOT NULL"),
                ColumnDef("diagnosis_description", "TEXT"),
                ColumnDef("is_primary", "BOOLEAN", "NOT NULL DEFAULT FALSE"),
                ColumnDef("diagnosis_rank", "INTEGER"),
            ],
        ),
        TableDef(
            name="raw_procedures",
            comment="Procedures performed during encounters.",
            columns=[
                ColumnDef("procedure_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("encounter_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_encounters(encounter_id)"),
                ColumnDef("cpt_code", "TEXT", "NOT NULL"),
                ColumnDef("procedure_description", "TEXT"),
                ColumnDef("procedure_ts", "TIMESTAMPTZ"),
                ColumnDef("billed_amount", "NUMERIC(12, 2)", "NOT NULL"),
                ColumnDef("allowed_amount", "NUMERIC(12, 2)"),
                ColumnDef("paid_amount", "NUMERIC(12, 2)"),
            ],
        ),
        TableDef(
            name="raw_providers",
            comment="Provider / physician master data.",
            columns=[
                ColumnDef("provider_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("npi", "TEXT", "NOT NULL"),
                ColumnDef("provider_name", "TEXT", "NOT NULL"),
                ColumnDef("specialty", "TEXT"),
                ColumnDef("department", "TEXT"),
                ColumnDef("facility_code", "TEXT"),
                ColumnDef("is_active", "BOOLEAN", "NOT NULL DEFAULT TRUE"),
            ],
        ),
    ]
    return all_tables[:min(count, len(all_tables))]


def _healthcare_views(tables: List[TableDef], rng: random.Random,
                      depth: int, use_dbt: bool) -> List[str]:
    table_names = [t.name for t in tables]
    views: List[str] = []

    def _tref(name: str) -> str:
        if not use_dbt:
            return name
        if name.startswith("raw_"):
            return "{{ source('clinical', '%s') }}" % name
        return "{{ ref('%s') }}" % name

    # Layer 1: staging
    if "raw_encounters" in table_names and "raw_providers" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Staging: encounter enrichment with provider details.
            CREATE VIEW stg_encounters_enriched AS
            SELECT
                e.encounter_id,
                e.patient_id,
                e.provider_id,
                e.encounter_ts,
                e.encounter_ts::DATE AS encounter_date,
                DATE_TRUNC('month', e.encounter_ts)::DATE AS encounter_month,
                LOWER(TRIM(e.encounter_type)) AS encounter_type_normalized,
                e.facility_code,
                e.chief_complaint,
                e.discharge_disposition,
                COALESCE(e.length_of_stay_hours, 0) AS length_of_stay_hours,
                CASE
                    WHEN e.length_of_stay_hours > 24 THEN 'inpatient'
                    WHEN e.encounter_type = 'emergency' THEN 'emergency'
                    ELSE 'outpatient'
                END AS visit_category,
                pv.provider_name,
                COALESCE(pv.specialty, 'unknown') AS specialty,
                COALESCE(pv.department, 'unassigned') AS department
            FROM {_tref('raw_encounters')} e
            LEFT JOIN {_tref('raw_providers')} pv
                ON pv.provider_id = e.provider_id;"""))

    if "raw_diagnoses" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Staging: diagnosis rollup per encounter.
            CREATE VIEW stg_diagnosis_summary AS
            SELECT
                d.encounter_id,
                COUNT(*) AS diagnosis_count,
                MAX(CASE WHEN d.is_primary THEN d.icd10_code END) AS primary_icd10_code,
                MAX(CASE WHEN d.is_primary THEN d.diagnosis_description END) AS primary_diagnosis,
                COUNT(DISTINCT d.icd10_code) AS distinct_diagnosis_count,
                STRING_AGG(d.icd10_code, ', ' ORDER BY COALESCE(d.diagnosis_rank, 999)) AS all_icd10_codes
            FROM {_tref('raw_diagnoses')} d
            GROUP BY d.encounter_id;"""))

    if depth < 2:
        return views

    # Layer 2: intermediate
    if "raw_patients" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Intermediate: patient encounter metrics.
            CREATE VIEW int_patient_encounter_metrics AS
            WITH patient_encounters AS (
                SELECT
                    p.patient_id,
                    p.mrn,
                    TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS full_name,
                    p.date_of_birth,
                    EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.date_of_birth))::INTEGER AS age_years,
                    p.gender,
                    COALESCE(p.insurance_type, 'self_pay') AS insurance_type,
                    p.enrollment_date,
                    p.patient_status,
                    se.encounter_id,
                    se.encounter_date,
                    se.encounter_month,
                    se.visit_category,
                    se.specialty,
                    se.length_of_stay_hours,
                    ds.primary_icd10_code,
                    ds.primary_diagnosis,
                    ds.diagnosis_count
                FROM {_tref('raw_patients')} p
                LEFT JOIN stg_encounters_enriched se
                    ON se.patient_id = p.patient_id
                LEFT JOIN stg_diagnosis_summary ds
                    ON ds.encounter_id = se.encounter_id
            )
            SELECT
                patient_id,
                mrn,
                full_name,
                date_of_birth,
                age_years,
                gender,
                insurance_type,
                enrollment_date,
                patient_status,
                MIN(encounter_date) AS first_encounter_date,
                MAX(encounter_date) AS last_encounter_date,
                COUNT(encounter_id) AS lifetime_encounter_count,
                COUNT(encounter_id) FILTER (WHERE visit_category = 'emergency') AS emergency_visit_count,
                COUNT(encounter_id) FILTER (WHERE visit_category = 'inpatient') AS inpatient_count,
                SUM(COALESCE(length_of_stay_hours, 0)) AS total_length_of_stay_hours,
                AVG(COALESCE(diagnosis_count, 0)) AS avg_diagnoses_per_encounter,
                COUNT(DISTINCT specialty) AS distinct_specialties_seen
            FROM patient_encounters
            GROUP BY
                patient_id, mrn, full_name, date_of_birth, age_years,
                gender, insurance_type, enrollment_date, patient_status;"""))

    if "raw_procedures" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Fact: procedure costs per encounter per day.
            CREATE VIEW fct_encounter_cost_daily AS
            SELECT
                se.patient_id,
                se.encounter_id,
                se.encounter_date AS cost_date,
                se.encounter_month AS cost_month,
                se.visit_category,
                se.specialty,
                SUM(pr.billed_amount) AS total_billed_amount,
                SUM(COALESCE(pr.allowed_amount, 0)) AS total_allowed_amount,
                SUM(COALESCE(pr.paid_amount, 0)) AS total_paid_amount,
                SUM(pr.billed_amount) - SUM(COALESCE(pr.paid_amount, 0)) AS write_off_amount,
                COUNT(DISTINCT pr.cpt_code) AS distinct_procedures,
                COUNT(*) AS procedure_count
            FROM stg_encounters_enriched se
            JOIN {_tref('raw_procedures')} pr
                ON pr.encounter_id = se.encounter_id
            GROUP BY
                se.patient_id, se.encounter_id, se.encounter_date,
                se.encounter_month, se.visit_category, se.specialty;"""))

    if depth < 3:
        return views

    # Layer 3: mart
    views.append(textwrap.dedent("""\
        -- Mart: patient risk segmentation with window functions.
        CREATE VIEW mart_patient_risk_segments AS
        WITH cost_rollup AS (
            SELECT
                fcd.patient_id,
                SUM(fcd.total_billed_amount) AS total_billed_amount,
                SUM(fcd.total_paid_amount) AS total_paid_amount,
                SUM(fcd.write_off_amount) AS total_write_off_amount,
                SUM(fcd.procedure_count) AS total_procedures
            FROM fct_encounter_cost_daily fcd
            GROUP BY fcd.patient_id
        )
        SELECT
            ipem.patient_id,
            ipem.mrn,
            ipem.full_name,
            ipem.age_years,
            ipem.gender,
            ipem.insurance_type,
            ipem.patient_status,
            ipem.first_encounter_date,
            ipem.last_encounter_date,
            ipem.lifetime_encounter_count,
            ipem.emergency_visit_count,
            ipem.inpatient_count,
            ipem.avg_diagnoses_per_encounter,
            COALESCE(cr.total_billed_amount, 0) AS total_billed_amount,
            COALESCE(cr.total_paid_amount, 0) AS total_paid_amount,
            COALESCE(cr.total_write_off_amount, 0) AS total_write_off_amount,
            DENSE_RANK() OVER (ORDER BY COALESCE(cr.total_billed_amount, 0) DESC) AS cost_rank,
            NTILE(5) OVER (ORDER BY COALESCE(cr.total_billed_amount, 0) DESC) AS cost_quintile,
            CASE
                WHEN ipem.emergency_visit_count >= 3 THEN 'high_utilizer'
                WHEN ipem.inpatient_count >= 2 AND ipem.avg_diagnoses_per_encounter >= 3 THEN 'complex'
                WHEN ipem.age_years >= 65 THEN 'senior'
                WHEN ipem.lifetime_encounter_count = 0 THEN 'no_encounter'
                ELSE 'standard'
            END AS risk_segment,
            CASE
                WHEN COALESCE(cr.total_write_off_amount, 0) / NULLIF(cr.total_billed_amount, 0) >= 0.3
                    THEN 'high_write_off'
                WHEN COALESCE(cr.total_write_off_amount, 0) / NULLIF(cr.total_billed_amount, 0) >= 0.1
                    THEN 'moderate_write_off'
                ELSE 'low_write_off'
            END AS financial_segment
        FROM int_patient_encounter_metrics ipem
        LEFT JOIN cost_rollup cr
            ON cr.patient_id = ipem.patient_id;"""))

    if depth < 4:
        return views

    # Layer 4: reporting
    views.append(textwrap.dedent("""\
        -- Report: clinical operations dashboard.
        CREATE VIEW rpt_clinical_operations_dashboard AS
        WITH segment_summary AS (
            SELECT
                mprs.insurance_type,
                mprs.risk_segment,
                mprs.financial_segment,
                COUNT(*) AS patient_count,
                SUM(mprs.total_billed_amount) AS segment_billed_amount,
                SUM(mprs.total_paid_amount) AS segment_paid_amount,
                SUM(mprs.total_write_off_amount) AS segment_write_off_amount,
                AVG(mprs.lifetime_encounter_count) AS avg_encounters,
                AVG(mprs.emergency_visit_count) AS avg_emergency_visits,
                COUNT(*) FILTER (WHERE mprs.risk_segment = 'high_utilizer') AS high_utilizer_count
            FROM mart_patient_risk_segments mprs
            GROUP BY mprs.insurance_type, mprs.risk_segment, mprs.financial_segment
        ),
        monthly_cost AS (
            SELECT
                fcd.cost_month,
                SUM(fcd.total_billed_amount) AS monthly_billed_amount,
                SUM(fcd.total_paid_amount) AS monthly_paid_amount,
                SUM(fcd.procedure_count) AS monthly_procedure_count
            FROM fct_encounter_cost_daily fcd
            GROUP BY fcd.cost_month
        )
        SELECT
            ss.insurance_type,
            ss.risk_segment,
            ss.financial_segment,
            ss.patient_count,
            ss.segment_billed_amount,
            ss.segment_paid_amount,
            ss.segment_write_off_amount,
            ss.avg_encounters,
            ss.avg_emergency_visits,
            ss.high_utilizer_count,
            ss.high_utilizer_count::NUMERIC / NULLIF(ss.patient_count, 0) AS high_utilizer_rate,
            ss.segment_paid_amount / NULLIF(ss.segment_billed_amount, 0) AS collection_rate,
            DENSE_RANK() OVER (
                ORDER BY ss.segment_billed_amount DESC
            ) AS segment_cost_rank
        FROM segment_summary ss;"""))

    return views


# ---------------------------------------------------------------------------
# Domain: SaaS / subscription
# ---------------------------------------------------------------------------

def _saas_tables(rng: random.Random, count: int) -> List[TableDef]:
    all_tables = [
        TableDef(
            name="raw_accounts",
            comment="Company / organization accounts.",
            columns=[
                ColumnDef("account_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("account_name", "TEXT", "NOT NULL"),
                ColumnDef("domain", "TEXT"),
                ColumnDef("industry", "TEXT"),
                ColumnDef("company_size", "TEXT"),
                ColumnDef("created_ts", "TIMESTAMPTZ", "NOT NULL"),
                ColumnDef("plan_tier", "TEXT", "NOT NULL"),
                ColumnDef("account_status", "TEXT", "NOT NULL"),
                ColumnDef("sales_rep_id", "BIGINT"),
            ],
        ),
        TableDef(
            name="raw_users",
            comment="Individual users within accounts.",
            columns=[
                ColumnDef("user_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("account_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_accounts(account_id)"),
                ColumnDef("email", "TEXT", "NOT NULL"),
                ColumnDef("display_name", "TEXT"),
                ColumnDef("role", "TEXT", "NOT NULL"),
                ColumnDef("created_ts", "TIMESTAMPTZ", "NOT NULL"),
                ColumnDef("last_login_ts", "TIMESTAMPTZ"),
                ColumnDef("is_active", "BOOLEAN", "NOT NULL DEFAULT TRUE"),
            ],
        ),
        TableDef(
            name="raw_subscriptions",
            comment="Subscription billing records.",
            columns=[
                ColumnDef("subscription_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("account_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_accounts(account_id)"),
                ColumnDef("plan_tier", "TEXT", "NOT NULL"),
                ColumnDef("billing_interval", "TEXT", "NOT NULL"),
                ColumnDef("mrr_amount", "NUMERIC(12, 2)", "NOT NULL"),
                ColumnDef("start_date", "DATE", "NOT NULL"),
                ColumnDef("end_date", "DATE"),
                ColumnDef("cancellation_reason", "TEXT"),
                ColumnDef("subscription_status", "TEXT", "NOT NULL"),
            ],
        ),
        TableDef(
            name="raw_events",
            comment="Product usage events.",
            columns=[
                ColumnDef("event_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("user_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_users(user_id)"),
                ColumnDef("event_ts", "TIMESTAMPTZ", "NOT NULL"),
                ColumnDef("event_type", "TEXT", "NOT NULL"),
                ColumnDef("feature_name", "TEXT"),
                ColumnDef("session_id", "TEXT"),
                ColumnDef("properties_json", "JSONB"),
            ],
        ),
        TableDef(
            name="raw_invoices",
            comment="Billing invoices.",
            columns=[
                ColumnDef("invoice_id", "BIGINT", "PRIMARY KEY"),
                ColumnDef("account_id", "BIGINT", "NOT NULL",
                          "REFERENCES raw_accounts(account_id)"),
                ColumnDef("invoice_date", "DATE", "NOT NULL"),
                ColumnDef("due_date", "DATE", "NOT NULL"),
                ColumnDef("amount", "NUMERIC(12, 2)", "NOT NULL"),
                ColumnDef("tax_amount", "NUMERIC(12, 2)", "NOT NULL DEFAULT 0"),
                ColumnDef("payment_status", "TEXT", "NOT NULL"),
                ColumnDef("paid_date", "DATE"),
            ],
        ),
    ]
    return all_tables[:min(count, len(all_tables))]


def _saas_views(tables: List[TableDef], rng: random.Random,
                depth: int, use_dbt: bool) -> List[str]:
    table_names = [t.name for t in tables]
    views: List[str] = []

    def _tref(name: str) -> str:
        if not use_dbt:
            return name
        if name.startswith("raw_"):
            return "{{ source('app', '%s') }}" % name
        return "{{ ref('%s') }}" % name

    # Layer 1: staging
    if "raw_accounts" in table_names and "raw_subscriptions" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Staging: account with current subscription status.
            CREATE VIEW stg_accounts_enriched AS
            WITH current_sub AS (
                SELECT DISTINCT ON (s.account_id)
                    s.account_id,
                    s.subscription_id,
                    s.plan_tier AS current_plan_tier,
                    s.mrr_amount AS current_mrr,
                    s.billing_interval,
                    s.start_date AS sub_start_date,
                    s.end_date AS sub_end_date,
                    s.subscription_status
                FROM {_tref('raw_subscriptions')} s
                ORDER BY s.account_id, s.start_date DESC
            )
            SELECT
                a.account_id,
                a.account_name,
                LOWER(TRIM(a.domain)) AS domain_normalized,
                COALESCE(a.industry, 'unknown') AS industry,
                COALESCE(a.company_size, 'unknown') AS company_size,
                a.created_ts,
                a.created_ts::DATE AS signup_date,
                DATE_TRUNC('month', a.created_ts)::DATE AS signup_month,
                a.account_status,
                cs.subscription_id AS current_subscription_id,
                COALESCE(cs.current_plan_tier, a.plan_tier) AS effective_plan_tier,
                COALESCE(cs.current_mrr, 0) AS current_mrr,
                cs.billing_interval,
                cs.sub_start_date,
                cs.sub_end_date,
                COALESCE(cs.subscription_status, 'none') AS subscription_status,
                CASE
                    WHEN cs.subscription_status = 'active' THEN TRUE
                    ELSE FALSE
                END AS is_active_subscriber
            FROM {_tref('raw_accounts')} a
            LEFT JOIN current_sub cs
                ON cs.account_id = a.account_id;"""))

    if "raw_users" in table_names and "raw_events" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Staging: user activity aggregates.
            CREATE VIEW stg_user_activity AS
            SELECT
                u.user_id,
                u.account_id,
                u.email,
                u.display_name,
                u.role,
                u.created_ts::DATE AS user_signup_date,
                u.is_active,
                COUNT(e.event_id) AS total_events,
                COUNT(DISTINCT e.session_id) AS total_sessions,
                COUNT(DISTINCT e.event_ts::DATE) AS active_days,
                MIN(e.event_ts) AS first_event_ts,
                MAX(e.event_ts) AS last_event_ts,
                MAX(e.event_ts)::DATE AS last_active_date,
                COUNT(DISTINCT e.feature_name) AS distinct_features_used,
                COUNT(e.event_id) FILTER (WHERE e.event_ts >= CURRENT_TIMESTAMP - INTERVAL '30 days')
                    AS events_last_30d,
                COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_ts >= CURRENT_TIMESTAMP - INTERVAL '7 days')
                    AS sessions_last_7d
            FROM {_tref('raw_users')} u
            LEFT JOIN {_tref('raw_events')} e
                ON e.user_id = u.user_id
            GROUP BY
                u.user_id, u.account_id, u.email, u.display_name,
                u.role, u.created_ts, u.is_active;"""))

    if depth < 2:
        return views

    # Layer 2: intermediate
    views.append(textwrap.dedent("""\
        -- Intermediate: account-level engagement metrics.
        CREATE VIEW int_account_engagement AS
        SELECT
            sae.account_id,
            sae.account_name,
            sae.signup_date,
            sae.signup_month,
            sae.industry,
            sae.company_size,
            sae.effective_plan_tier,
            sae.current_mrr,
            sae.is_active_subscriber,
            COUNT(sua.user_id) AS total_users,
            COUNT(sua.user_id) FILTER (WHERE sua.is_active) AS active_users,
            SUM(COALESCE(sua.total_events, 0)) AS account_total_events,
            SUM(COALESCE(sua.total_sessions, 0)) AS account_total_sessions,
            SUM(COALESCE(sua.events_last_30d, 0)) AS account_events_last_30d,
            SUM(COALESCE(sua.active_days, 0)) AS account_total_active_days,
            MAX(sua.last_active_date) AS account_last_active_date,
            AVG(sua.distinct_features_used) AS avg_features_per_user,
            CASE
                WHEN SUM(COALESCE(sua.events_last_30d, 0)) = 0 THEN 'dormant'
                WHEN SUM(COALESCE(sua.events_last_30d, 0)) < 50 THEN 'low'
                WHEN SUM(COALESCE(sua.events_last_30d, 0)) < 500 THEN 'medium'
                ELSE 'high'
            END AS engagement_tier
        FROM stg_accounts_enriched sae
        LEFT JOIN stg_user_activity sua
            ON sua.account_id = sae.account_id
        GROUP BY
            sae.account_id, sae.account_name, sae.signup_date, sae.signup_month,
            sae.industry, sae.company_size, sae.effective_plan_tier,
            sae.current_mrr, sae.is_active_subscriber;"""))

    if "raw_invoices" in table_names:
        views.append(textwrap.dedent(f"""\
            -- Fact: monthly revenue per account.
            CREATE VIEW fct_account_revenue_monthly AS
            WITH invoice_agg AS (
                SELECT
                    inv.account_id,
                    DATE_TRUNC('month', inv.invoice_date)::DATE AS revenue_month,
                    SUM(inv.amount) AS invoiced_amount,
                    SUM(inv.tax_amount) AS tax_amount,
                    SUM(inv.amount) + SUM(inv.tax_amount) AS total_amount,
                    SUM(CASE WHEN inv.payment_status = 'paid' THEN inv.amount ELSE 0 END) AS collected_amount,
                    SUM(CASE WHEN inv.payment_status = 'overdue' THEN inv.amount ELSE 0 END) AS overdue_amount,
                    COUNT(*) AS invoice_count,
                    COUNT(*) FILTER (WHERE inv.payment_status = 'paid') AS paid_invoice_count,
                    AVG(CASE WHEN inv.paid_date IS NOT NULL
                         THEN inv.paid_date - inv.invoice_date END) AS avg_days_to_pay
                FROM {_tref('raw_invoices')} inv
                GROUP BY inv.account_id, DATE_TRUNC('month', inv.invoice_date)::DATE
            )
            SELECT
                ia.account_id,
                ia.revenue_month,
                ia.invoiced_amount,
                ia.tax_amount,
                ia.total_amount,
                ia.collected_amount,
                ia.overdue_amount,
                ia.invoice_count,
                ia.paid_invoice_count,
                ia.avg_days_to_pay,
                ia.collected_amount / NULLIF(ia.invoiced_amount, 0) AS collection_rate,
                SUM(ia.invoiced_amount) OVER (
                    PARTITION BY ia.account_id
                    ORDER BY ia.revenue_month
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS cumulative_invoiced_amount
            FROM invoice_agg ia;"""))

    if depth < 3:
        return views

    # Layer 3: mart
    views.append(textwrap.dedent("""\
        -- Mart: account health scoring with churn risk.
        CREATE VIEW mart_account_health AS
        WITH rev_rollup AS (
            SELECT
                farm.account_id,
                SUM(farm.invoiced_amount) AS lifetime_invoiced_amount,
                SUM(farm.collected_amount) AS lifetime_collected_amount,
                SUM(farm.overdue_amount) AS lifetime_overdue_amount,
                AVG(farm.avg_days_to_pay) AS overall_avg_days_to_pay,
                MAX(farm.revenue_month) AS last_revenue_month,
                COUNT(DISTINCT farm.revenue_month) AS active_revenue_months
            FROM fct_account_revenue_monthly farm
            GROUP BY farm.account_id
        )
        SELECT
            iae.account_id,
            iae.account_name,
            iae.signup_date,
            iae.industry,
            iae.company_size,
            iae.effective_plan_tier,
            iae.current_mrr,
            iae.is_active_subscriber,
            iae.total_users,
            iae.active_users,
            iae.account_total_events,
            iae.account_events_last_30d,
            iae.engagement_tier,
            iae.avg_features_per_user,
            COALESCE(rr.lifetime_invoiced_amount, 0) AS lifetime_invoiced_amount,
            COALESCE(rr.lifetime_collected_amount, 0) AS lifetime_collected_amount,
            COALESCE(rr.lifetime_overdue_amount, 0) AS lifetime_overdue_amount,
            rr.overall_avg_days_to_pay,
            rr.active_revenue_months,
            CURRENT_DATE - iae.signup_date AS account_age_days,
            DENSE_RANK() OVER (ORDER BY COALESCE(rr.lifetime_collected_amount, 0) DESC) AS revenue_rank,
            NTILE(4) OVER (ORDER BY COALESCE(rr.lifetime_collected_amount, 0) DESC) AS revenue_quartile,
            CASE
                WHEN iae.engagement_tier = 'dormant' AND NOT iae.is_active_subscriber THEN 'churned'
                WHEN iae.engagement_tier = 'dormant' AND iae.is_active_subscriber THEN 'at_risk'
                WHEN iae.engagement_tier = 'low' THEN 'monitor'
                WHEN iae.effective_plan_tier IN ('enterprise', 'business') AND iae.engagement_tier = 'high'
                    THEN 'champion'
                ELSE 'healthy'
            END AS health_segment,
            CASE
                WHEN COALESCE(rr.lifetime_overdue_amount, 0) / NULLIF(rr.lifetime_invoiced_amount, 0) >= 0.2
                    THEN 'payment_risk'
                WHEN rr.overall_avg_days_to_pay > 45 THEN 'slow_payer'
                ELSE 'good_standing'
            END AS payment_segment
        FROM int_account_engagement iae
        LEFT JOIN rev_rollup rr
            ON rr.account_id = iae.account_id;"""))

    if depth < 4:
        return views

    # Layer 4: reporting
    views.append(textwrap.dedent("""\
        -- Report: SaaS executive metrics dashboard.
        CREATE VIEW rpt_saas_executive_dashboard AS
        WITH health_summary AS (
            SELECT
                mah.effective_plan_tier,
                mah.industry,
                mah.health_segment,
                COUNT(*) AS account_count,
                SUM(mah.current_mrr) AS tier_mrr,
                SUM(mah.lifetime_collected_amount) AS tier_lifetime_revenue,
                AVG(mah.account_age_days) AS avg_account_age_days,
                AVG(mah.active_users) AS avg_active_users,
                AVG(mah.avg_features_per_user) AS avg_features_adopted,
                COUNT(*) FILTER (WHERE mah.health_segment = 'at_risk') AS at_risk_accounts,
                COUNT(*) FILTER (WHERE mah.health_segment = 'churned') AS churned_accounts,
                COUNT(*) FILTER (WHERE mah.health_segment = 'champion') AS champion_accounts,
                SUM(mah.current_mrr) FILTER (WHERE mah.health_segment = 'at_risk') AS at_risk_mrr
            FROM mart_account_health mah
            GROUP BY mah.effective_plan_tier, mah.industry, mah.health_segment
        )
        SELECT
            hs.effective_plan_tier,
            hs.industry,
            hs.health_segment,
            hs.account_count,
            hs.tier_mrr,
            hs.tier_lifetime_revenue,
            hs.avg_account_age_days,
            hs.avg_active_users,
            hs.avg_features_adopted,
            hs.at_risk_accounts,
            hs.churned_accounts,
            hs.champion_accounts,
            hs.at_risk_mrr,
            hs.at_risk_accounts::NUMERIC / NULLIF(hs.account_count, 0) AS churn_risk_rate,
            hs.tier_mrr * 12 AS tier_arr,
            hs.at_risk_mrr * 12 AS at_risk_arr,
            hs.champion_accounts::NUMERIC / NULLIF(hs.account_count, 0) AS champion_rate,
            DENSE_RANK() OVER (
                ORDER BY hs.tier_mrr DESC
            ) AS tier_mrr_rank
        FROM health_summary hs;"""))

    return views


# ---------------------------------------------------------------------------
# Domain registry
# ---------------------------------------------------------------------------

DOMAINS = {
    "ecommerce": (_ecommerce_tables, _ecommerce_views),
    "healthcare": (_healthcare_tables, _healthcare_views),
    "saas": (_saas_tables, _saas_views),
}


# ---------------------------------------------------------------------------
# PostgreSQL introspection
# ---------------------------------------------------------------------------

def _pg_import():
    """Lazily import psycopg2, raising a clear error if not installed."""
    try:
        import psycopg2
        return psycopg2
    except ImportError:
        raise ImportError(
            "psycopg2 is required for PostgreSQL introspection. "
            "Install it with: pip install psycopg2-binary"
        )


# Map PostgreSQL type OIDs / information_schema names to DDL-friendly types.
_PG_TYPE_MAP = {
    "bigint": "BIGINT",
    "integer": "INTEGER",
    "smallint": "SMALLINT",
    "numeric": "NUMERIC",
    "real": "REAL",
    "double precision": "DOUBLE PRECISION",
    "boolean": "BOOLEAN",
    "text": "TEXT",
    "character varying": "TEXT",
    "character": "TEXT",
    "date": "DATE",
    "timestamp without time zone": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMPTZ",
    "time without time zone": "TIME",
    "time with time zone": "TIMETZ",
    "bytea": "BYTEA",
    "json": "JSON",
    "jsonb": "JSONB",
    "uuid": "UUID",
    "inet": "INET",
    "cidr": "CIDR",
    "macaddr": "MACADDR",
    "interval": "INTERVAL",
    "xml": "XML",
    "money": "MONEY",
    "point": "POINT",
    "line": "LINE",
    "circle": "CIRCLE",
    "box": "BOX",
    "path": "PATH",
    "polygon": "POLYGON",
    "bit": "BIT",
    "bit varying": "BIT VARYING",
    "tsvector": "TSVECTOR",
    "tsquery": "TSQUERY",
    "oid": "OID",
    "ARRAY": "TEXT[]",
    "USER-DEFINED": "TEXT",
}


def _pg_format_type(
    data_type: str,
    char_max_len: Optional[int],
    numeric_precision: Optional[int],
    numeric_scale: Optional[int],
    udt_name: Optional[str] = None,
) -> str:
    """Convert information_schema type info to a DDL type string."""
    mapped = _PG_TYPE_MAP.get(data_type, data_type.upper())

    # character varying(N) → VARCHAR(N)
    if data_type == "character varying" and char_max_len is not None:
        return f"VARCHAR({char_max_len})"
    if data_type == "character" and char_max_len is not None:
        return f"CHAR({char_max_len})"

    # numeric(P, S) → NUMERIC(P, S)
    if data_type == "numeric" and numeric_precision is not None:
        if numeric_scale is not None and numeric_scale > 0:
            return f"NUMERIC({numeric_precision}, {numeric_scale})"
        return f"NUMERIC({numeric_precision})"

    # Array types → use the underlying type name
    if data_type == "ARRAY" and udt_name:
        base = udt_name.lstrip("_").upper()
        return f"{base}[]"

    # User-defined (enum, composite) — use udt_name if available
    if data_type == "USER-DEFINED" and udt_name:
        return udt_name.upper()

    return mapped


def _pg_introspect_tables(
    conn,
    pg_schema: str = "public",
) -> List[TableDef]:
    """Query information_schema for base tables and return TableDef list."""
    cur = conn.cursor()

    # 1. Discover tables in dependency-safe order (tables with no FKs first).
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """, (pg_schema,))
    table_names = [row[0] for row in cur.fetchall()]

    if not table_names:
        cur.close()
        return []

    # 2. Discover primary key columns per table.
    cur.execute("""
        SELECT kcu.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
        WHERE tc.table_schema = %s
          AND tc.constraint_type = 'PRIMARY KEY'
    """, (pg_schema,))
    pk_columns: Dict[str, set] = {}
    for tname, cname in cur.fetchall():
        pk_columns.setdefault(tname, set()).add(cname)

    # 3. Discover foreign key references per column.
    cur.execute("""
        SELECT
            kcu.table_name AS from_table,
            kcu.column_name AS from_column,
            ccu.table_name AS to_table,
            ccu.column_name AS to_column
        FROM information_schema.referential_constraints rc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = rc.constraint_name
         AND kcu.table_schema = rc.constraint_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = rc.unique_constraint_name
         AND ccu.table_schema = rc.unique_constraint_schema
        WHERE rc.constraint_schema = %s
    """, (pg_schema,))
    fk_refs: Dict[Tuple[str, str], str] = {}
    for from_t, from_c, to_t, to_c in cur.fetchall():
        fk_refs[(from_t, from_c)] = f"REFERENCES {to_t}({to_c})"

    # 4. Discover columns for each table.
    cur.execute("""
        SELECT
            table_name,
            column_name,
            data_type,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            is_nullable,
            column_default,
            ordinal_position,
            udt_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = ANY(%s)
        ORDER BY table_name, ordinal_position
    """, (pg_schema, table_names))

    columns_by_table: Dict[str, List[ColumnDef]] = {}
    for (tname, cname, dtype, char_max, num_prec, num_scale,
         is_nullable, col_default, _ordinal, udt_name) in cur.fetchall():

        sql_type = _pg_format_type(dtype, char_max, num_prec, num_scale, udt_name)

        # Build constraints string
        constraint_parts = []
        if tname in pk_columns and cname in pk_columns[tname]:
            constraint_parts.append("PRIMARY KEY")
        elif is_nullable == "NO":
            constraint_parts.append("NOT NULL")

        if col_default is not None:
            # Skip auto-generated defaults like nextval(...) sequences
            default_str = str(col_default)
            if not default_str.startswith("nextval("):
                constraint_parts.append(f"DEFAULT {default_str}")

        constraints = " ".join(constraint_parts)
        fk_ref = fk_refs.get((tname, cname), "")

        col = ColumnDef(
            name=cname,
            sql_type=sql_type,
            constraints=constraints,
            fk_ref=fk_ref,
        )
        columns_by_table.setdefault(tname, []).append(col)

    cur.close()

    # 5. Build dependency-ordered table list.
    # Tables referenced by FKs should appear before tables that reference them.
    fk_deps: Dict[str, set] = {}
    for (from_t, _), ref_str in fk_refs.items():
        # Parse "REFERENCES to_table(to_col)"
        import re
        m = re.match(r"REFERENCES\s+(\w+)", ref_str)
        if m:
            to_t = m.group(1)
            if to_t in table_names:
                fk_deps.setdefault(from_t, set()).add(to_t)

    # Simple topological sort
    ordered: List[str] = []
    visited: set = set()

    def _topo_visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        for dep in fk_deps.get(name, set()):
            _topo_visit(dep)
        ordered.append(name)

    for tn in table_names:
        _topo_visit(tn)

    tables = []
    for tn in ordered:
        cols = columns_by_table.get(tn, [])
        if cols:
            tables.append(TableDef(name=tn, columns=cols))

    return tables


def _pg_introspect_views(
    conn,
    pg_schema: str = "public",
) -> List[str]:
    """Query pg_views for view definitions and return CREATE VIEW SQL strings."""
    cur = conn.cursor()
    cur.execute("""
        SELECT viewname, definition
        FROM pg_views
        WHERE schemaname = %s
        ORDER BY viewname
    """, (pg_schema,))

    view_sqls: List[str] = []
    for viewname, definition in cur.fetchall():
        # pg_views.definition is the SELECT body (without CREATE VIEW ... AS).
        # Normalize: strip trailing semicolon/whitespace from definition,
        # then wrap in CREATE VIEW.
        defn = definition.strip().rstrip(";").strip()
        sql = f"CREATE VIEW {viewname} AS\n{defn};"
        view_sqls.append(sql)

    cur.close()
    return view_sqls


def build_schema_from_postgres(
    connection_string: str,
    pg_schema: str = "public",
) -> str:
    """Introspect a live PostgreSQL database and produce a schema.txt DDL string.

    Connects to the database specified by *connection_string*, reads table and
    view definitions from ``information_schema`` and ``pg_views``, and returns a
    DDL string in the same format as ``build_schema()`` — compatible with the
    lineage parser and the column-lineage web app.

    Args:
        connection_string: A PostgreSQL connection string (DSN) such as
            ``"host=localhost dbname=mydb user=me password=secret"`` or a
            ``postgresql://`` URI.
        pg_schema: The database schema to introspect (default: ``"public"``).

    Returns:
        The full SQL DDL text ready to write to ``schema.txt``.

    Raises:
        ImportError: If ``psycopg2`` is not installed.
        psycopg2.OperationalError: If the connection fails.
        ValueError: If no tables or views are found in the specified schema.
    """
    psycopg2 = _pg_import()

    conn = psycopg2.connect(connection_string)
    try:
        tables = _pg_introspect_tables(conn, pg_schema)
        view_sqls = _pg_introspect_views(conn, pg_schema)
    finally:
        conn.close()

    if not tables and not view_sqls:
        raise ValueError(
            f"No tables or views found in schema '{pg_schema}'. "
            "Check the schema name and database connection."
        )

    view_names = _collect_view_names(view_sqls)

    parts: List[str] = []

    # ---- DROP statements (reverse dependency order) ----
    for vn in reversed(view_names):
        parts.append(f"DROP VIEW IF EXISTS {vn};")
    if view_names:
        parts.append("")
    for t in reversed(tables):
        parts.append(f"DROP TABLE IF EXISTS {t.name};")
    if tables:
        parts.append("")

    # ---- CREATE TABLE statements ----
    for t in tables:
        parts.append(_render_table(t))
        parts.append("")

    # ---- CREATE VIEW statements ----
    for vsql in view_sqls:
        parts.append(vsql)
        parts.append("")

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------

def _render_table(table: TableDef) -> str:
    """Render a CREATE TABLE statement."""
    lines = []
    if table.comment:
        lines.append(f"-- {table.comment}")
    lines.append(f"CREATE TABLE {table.name} (")
    col_lines = []
    for col in table.columns:
        parts = [f"    {col.name:<30s} {col.sql_type}"]
        if col.constraints:
            parts.append(col.constraints)
        if col.fk_ref:
            parts.append(col.fk_ref)
        col_lines.append(" ".join(parts))
    lines.append(",\n".join(col_lines))
    lines.append(");")
    return "\n".join(lines)


def _collect_view_names(view_sqls: List[str]) -> List[str]:
    """Extract view names from CREATE VIEW statements."""
    import re
    names = []
    for sql in view_sqls:
        m = re.search(r'CREATE\s+VIEW\s+(\w+)', sql, re.IGNORECASE)
        if m:
            names.append(m.group(1))
    return names


def build_schema(
    domain: str = "ecommerce",
    table_count: int = 5,
    depth: int = 4,
    include_dbt: bool = False,
    seed: Optional[int] = None,
) -> str:
    """Build a complete schema.txt content string.

    Args:
        domain: One of 'ecommerce', 'healthcare', 'saas'.
        table_count: Max number of base tables (capped by domain's available tables).
        depth: View layer depth (1=staging only, 2=+intermediate, 3=+mart, 4=+reporting).
        include_dbt: If True, wrap some table refs in dbt Jinja syntax.
        seed: Random seed for reproducibility.

    Returns:
        The full SQL DDL text ready to write to schema.txt.
    """
    if domain not in DOMAINS:
        raise ValueError(
            f"Unknown domain '{domain}'. Choose from: {', '.join(DOMAINS)}"
        )

    rng = random.Random(seed)
    table_fn, view_fn = DOMAINS[domain]

    tables = table_fn(rng, table_count)
    view_sqls = view_fn(tables, rng, depth, include_dbt)
    view_names = _collect_view_names(view_sqls)

    parts: List[str] = []

    # ---- DROP statements (reverse dependency order) ----
    for vn in reversed(view_names):
        parts.append(f"DROP VIEW IF EXISTS {vn};")
    parts.append("")  # blank line
    for t in reversed(tables):
        parts.append(f"DROP TABLE IF EXISTS {t.name};")
    parts.append("")

    # ---- CREATE TABLE statements ----
    for t in tables:
        parts.append(_render_table(t))
        parts.append("")

    # ---- CREATE VIEW statements ----
    for vsql in view_sqls:
        parts.append(vsql)
        parts.append("")

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate a schema.txt file with SQL DDL for the column-lineage app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Domains (for in-memory generation):
              ecommerce   Customers, orders, payments, products (default)
              healthcare  Patients, encounters, diagnoses, procedures, providers
              saas        Accounts, users, subscriptions, events, invoices

            Depth controls how many view layers are generated:
              1  staging only
              2  + intermediate / fact
              3  + mart
              4  + reporting (default)

            PostgreSQL introspection:
              --from-postgres DSN   Connect to a live PostgreSQL database and
                                    extract tables/views instead of generating
                                    from in-memory domain definitions.
              --pg-schema NAME      Database schema to introspect (default: public).

            Example PostgreSQL usage:
              python generate_schema.py --from-postgres "host=localhost dbname=mydb user=me"
              python generate_schema.py --from-postgres "postgresql://me@localhost/mydb"
              python generate_schema.py --from-postgres "host=db port=5432 dbname=app" --pg-schema analytics -o schema.txt
        """),
    )
    parser.add_argument(
        "--domain", "-d",
        choices=list(DOMAINS.keys()),
        default="ecommerce",
        help="Business domain to generate (default: ecommerce)",
    )
    parser.add_argument(
        "--tables", "-t",
        type=int,
        default=5,
        help="Max number of base tables (default: 5)",
    )
    parser.add_argument(
        "--depth",
        type=int,
        choices=[1, 2, 3, 4],
        default=4,
        help="View layer depth: 1=stg, 2=+int/fct, 3=+mart, 4=+rpt (default: 4)",
    )
    parser.add_argument(
        "--include-dbt",
        action="store_true",
        help="Wrap some table references in dbt Jinja syntax ({{ source/ref }})",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=None,
        help="Random seed for reproducible output",
    )
    parser.add_argument(
        "-o", "--output",
        default="schema.txt",
        help="Output file path (default: schema.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print to stdout instead of writing a file",
    )
    parser.add_argument(
        "--from-postgres",
        metavar="DSN",
        default=None,
        help="PostgreSQL connection string (DSN or URI). When set, introspects "
             "a live database instead of generating from in-memory domains. "
             "Requires psycopg2-binary.",
    )
    parser.add_argument(
        "--pg-schema",
        default="public",
        help="Database schema to introspect when using --from-postgres (default: public)",
    )

    args = parser.parse_args(argv)

    if args.from_postgres:
        # PostgreSQL introspection mode
        schema_text = build_schema_from_postgres(
            connection_string=args.from_postgres,
            pg_schema=args.pg_schema,
        )
    else:
        # In-memory domain generation mode
        schema_text = build_schema(
            domain=args.domain,
            table_count=args.tables,
            depth=args.depth,
            include_dbt=args.include_dbt,
            seed=args.seed,
        )

    if args.dry_run:
        sys.stdout.write(schema_text)
    else:
        output_path = Path(args.output)
        output_path.write_text(schema_text, encoding="utf-8")
        # Summary stats
        table_count = schema_text.count("CREATE TABLE")
        view_count = schema_text.count("CREATE VIEW")
        source = "PostgreSQL" if args.from_postgres else args.domain
        print(f"Wrote {output_path} ({table_count} tables, {view_count} views, "
              f"{len(schema_text)} bytes, source: {source})")


if __name__ == "__main__":
    main()
