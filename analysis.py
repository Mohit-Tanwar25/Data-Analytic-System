import pandas as pd
import numpy as np

# ---------------- CLEAN DATA ----------------

def clean_data(df):

    # Convert column names to lowercase
    df.columns = (
        df.columns
        .str.lower()
        .str.replace(" ", "_")
    )

    numeric_columns = [
        "sales",
        "profit",
        "discount",
        "shipping_cost",
        "quantity"
    ]

    # Clean numeric columns
    for col in numeric_columns:

        if col in df.columns:

            # Remove commas and spaces
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )

            # Convert invalid values to NaN
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    # ---------------- REMOVE BAD ROWS ----------------

    existing_numeric_cols = [
        col for col in numeric_columns
        if col in df.columns
    ]

    if existing_numeric_cols:

        df = df.dropna(
            subset=existing_numeric_cols
        )

    # ---------------- DATE CONVERSION ----------------

    date_columns = [
        "order_date",
        "ship_date"
    ]

    for col in date_columns:

        if col in df.columns:

            df[col] = pd.to_datetime(
                df[col],
                errors="coerce"
            )

    # ---------------- REMOVE DUPLICATES ----------------

    df = df.drop_duplicates()

    return df


# ---------------- KPI CALCULATIONS ----------------

def calculate_kpis(df):

    total_sales = (
        round(df["sales"].sum(), 2)
        if "sales" in df.columns
        else 0
    )

    total_profit = (
        round(df["profit"].sum(), 2)
        if "profit" in df.columns
        else 0
    )

    total_orders = (
        df["order_id"].nunique()
        if "order_id" in df.columns
        else 0
    )

    total_quantity = (
        int(df["quantity"].sum())
        if "quantity" in df.columns
        else 0
    )

    return (
        total_sales,
        total_profit,
        total_orders,
        total_quantity
    )


# ---------------- SALES TREND ----------------

def sales_trend(df):

    if (
        "order_date" not in df.columns
        or "sales" not in df.columns
    ):
        return pd.DataFrame()

    trend_df = (
        df.groupby("order_date")["sales"]
        .sum()
        .reset_index()
        .sort_values(by="order_date")
    )

    return trend_df


# ---------------- CATEGORY ANALYSIS ----------------

def category_analysis(df):

    if (
        "category" not in df.columns
        or "sales" not in df.columns
    ):
        return pd.DataFrame()

    category_df = (
        df.groupby("category")["sales"]
        .sum()
        .reset_index()
        .sort_values(
            by="sales",
            ascending=False
        )
    )

    return category_df


# ---------------- REGION ANALYSIS ----------------

def region_analysis(df):

    if (
        "region" not in df.columns
        or "profit" not in df.columns
    ):
        return pd.DataFrame()

    region_df = (
        df.groupby("region")["profit"]
        .sum()
        .reset_index()
        .sort_values(
            by="profit",
            ascending=False
        )
    )

    return region_df


# ---------------- TOP PRODUCTS ----------------

def top_products(df):

    if (
        "product_name" not in df.columns
        or "sales" not in df.columns
    ):
        return pd.DataFrame()

    top_products_df = (
        df.groupby("product_name")["sales"]
        .sum()
        .sort_values(
            ascending=False
        )
        .head(10)
        .reset_index()
    )

    return top_products_df


# ---------------- MONTHLY SALES ----------------

def monthly_sales(df):

    if (
        "order_date" not in df.columns
        or "sales" not in df.columns
    ):
        return pd.DataFrame()

    df["month"] = (
        df["order_date"]
        .dt.strftime("%Y-%m")
    )

    monthly_df = (
        df.groupby("month")["sales"]
        .sum()
        .reset_index()
    )

    return monthly_df


# ---------------- DATA SUMMARY ----------------

def dataset_summary(df):

    summary = {

        "Rows": df.shape[0],
        "Columns": df.shape[1],
        "Missing Values": int(df.isnull().sum().sum()),
        "Duplicate Rows": int(df.duplicated().sum())

    }

    return summary


# ---------------- BUSINESS INSIGHTS ----------------

def generate_insights(df):

    insights = []

    # Empty dataframe protection
    if df.empty:

        insights.append(
            "No data available for analysis."
        )

        return insights

    # ---------------- TOP CATEGORY ----------------

    if (
        "category" in df.columns
        and "sales" in df.columns
    ):

        top_category = (
            df.groupby("category")["sales"]
            .sum()
            .idxmax()
        )

        insights.append(
            f"{top_category} recorded the strongest sales performance."
        )

    # ---------------- TOP REGION ----------------

    if (
        "region" in df.columns
        and "profit" in df.columns
    ):

        top_region = (
            df.groupby("region")["profit"]
            .sum()
            .idxmax()
        )

        insights.append(
            f"{top_region} achieved the highest profitability."
        )

    # ---------------- LOWEST PROFIT CATEGORY ----------------

    if (
        "category" in df.columns
        and "profit" in df.columns
    ):

        low_profit_category = (
            df.groupby("category")["profit"]
            .sum()
            .idxmin()
        )

        insights.append(
            f"{low_profit_category} showed the weakest profit margins."
        )

    # ---------------- NEGATIVE PROFIT ----------------

    if "profit" in df.columns:

        negative_profit_count = (
            df[df["profit"] < 0]
            .shape[0]
        )

        insights.append(
            f"{negative_profit_count} transactions resulted in negative profit."
        )

    # ---------------- TOP PRODUCT ----------------

    if (
        "product_name" in df.columns
        and "sales" in df.columns
    ):

        best_product = (
            df.groupby("product_name")["sales"]
            .sum()
            .idxmax()
        )

        insights.append(
            f"{best_product} emerged as the highest selling product."
        )

    # ---------------- AVERAGE SALES ----------------

    if "sales" in df.columns:

        average_sales = round(
            df["sales"].mean(),
            2
        )

        insights.append(
            f"Average sales per transaction were {average_sales}."
        )

    return insights