import streamlit as st
import pandas as pd
import plotly.express as px

from analysis import *
from file_storage import (
    count_duplicate_datasets,
    delete_dataset,
    format_uploaded_at,
    get_active_dataset_id,
    get_dataset,
    init_database_tables,
    list_datasets,
    load_dataset_from_database,
    load_from_database,
    run_dataset_cleanup,
    set_active_dataset,
    storage_stats,
    store_uploaded_csv,
)
from pdf_export import generate_dashboard_pdf
from theme import apply_chart_theme, inject_theme

# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="Business Analytics Dashboard",
    layout="wide"
)

# ---------------- SESSION ----------------

if "uploaded" not in st.session_state:
    st.session_state.uploaded = False

if "active_dataset_id" not in st.session_state:
    st.session_state.active_dataset_id = get_active_dataset_id()

if "db_initialized" not in st.session_state:
    init_database_tables()
    st.session_state.db_initialized = True

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True


def sidebar_section_label(title: str) -> None:
    st.sidebar.markdown(
        f'<div class="sidebar-section-label">{title}</div>',
        unsafe_allow_html=True,
    )


def dataset_option_label(item: dict) -> str:
    """Unique label when several uploads share the same filename."""
    short_id = item["id"][:6]
    return (
        f"{item['name']} · {short_id} · {item['rows']:,} rows · "
        f"{format_uploaded_at(item['uploaded_at'])}"
    )


def process_csv_upload(uploaded_file, source_key: str) -> tuple[str, str | None]:
    """Store CSV once per upload. Returns (status, dataset_id)."""
    file_signature = f"{uploaded_file.name}_{uploaded_file.size}"
    session_key = f"processed_upload_{source_key}"

    if st.session_state.get(session_key) == file_signature:
        return "skipped", None

    dataset_id = store_uploaded_csv(
        uploaded_file.getvalue(),
        uploaded_file.name,
    )

    if not dataset_id:
        return "failed", None

    st.session_state[session_key] = file_signature
    return "success", dataset_id


def process_csv_uploads(uploaded_files, source_prefix: str) -> str:
    """Upload one or more files; activate the last successful dataset."""
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]

    last_dataset_id = None
    any_success = False
    any_failed = False
    all_skipped = True

    for uploaded_file in uploaded_files:
        safe_key = f"{source_prefix}_{uploaded_file.name}_{uploaded_file.size}"
        status, dataset_id = process_csv_upload(uploaded_file, safe_key)
        if status == "success" and dataset_id:
            any_success = True
            all_skipped = False
            last_dataset_id = dataset_id
        elif status == "failed":
            any_failed = True
            all_skipped = False
        elif status != "skipped":
            all_skipped = False

    if last_dataset_id and activate_dataset(last_dataset_id):
        return "success"
    if any_failed:
        return "failed"
    if all_skipped:
        return "skipped"
    return "failed"


def _clear_upload_session_keys() -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith("processed_upload_"):
            del st.session_state[key]


def render_run_cleanup_button(button_key: str) -> None:
    """Remove duplicate datasets (same filename or identical file content)."""
    dup = count_duplicate_datasets()
    if dup["total"] > 0:
        st.caption(
            f"**{dup['total']}** duplicate(s) found "
            f"({dup['by_name']} same filename, {dup['by_hash']} identical content). "
            f"Cleanup keeps the newest copy of each."
        )
    else:
        st.caption("No duplicates found. Run cleanup anytime after uploading.")

    if st.button(
        "Run cleanup",
        type="secondary",
        width="stretch",
        key=button_key,
        help="Deletes older copies with the same filename or identical file content.",
    ):
        result = run_dataset_cleanup()
        if result["removed"] > 0:
            parts = [f"Removed **{result['removed']}** duplicate dataset(s)."]
            if result["by_name"]:
                parts.append(f"{result['by_name']} had the same filename.")
            if result["by_hash"]:
                parts.append(f"{result['by_hash']} had identical file content.")
            parts.append(f"**{result['remaining']}** dataset(s) remain.")
            st.session_state.cleanup_message = " ".join(parts)
            if result["cleared_active"]:
                st.session_state.uploaded = False
                st.session_state.active_dataset_id = None
                _clear_upload_session_keys()
        else:
            st.session_state.cleanup_message = (
                "No duplicates to remove. Each saved file is already unique."
            )
        st.rerun()


def activate_dataset(dataset_id: str) -> bool:
    if get_dataset(dataset_id) is None:
        return False

    df = load_dataset_from_database(dataset_id)
    if df.empty:
        return False

    set_active_dataset(dataset_id)
    st.session_state.active_dataset_id = dataset_id
    st.session_state.uploaded = True
    return True


def render_saved_dataset_picker():
    datasets = list_datasets()

    if not datasets:
        st.info("No saved CSV files yet. Use **Upload a new CSV file** to add one.")
        return

    stats = storage_stats()
    st.caption(
        f"{stats['count']} saved dataset(s) in MySQL · "
        f"{stats['total_rows']:,} total rows · no limit on how many you can store"
    )

    library = pd.DataFrame(
        [
            {
                "File": item["name"],
                "ID": item["id"][:6],
                "Rows": item["rows"],
                "Columns": item["columns"],
                "Saved": format_uploaded_at(item["uploaded_at"]),
            }
            for item in datasets
        ]
    )
    st.dataframe(library, width="stretch", hide_index=True)

    options = {dataset_option_label(item): item["id"] for item in datasets}

    selected_label = st.selectbox(
        "Select a saved dataset",
        options=list(options.keys()),
    )

    st.divider()
    render_run_cleanup_button("landing_run_cleanup")

    manage_col1, manage_col2 = st.columns(2)

    with manage_col1:
        if st.button(
            "Open Dashboard",
            type="primary",
            width="stretch",
            key="open_selected_dataset",
        ):
            if activate_dataset(options[selected_label]):
                st.rerun()
            st.error("Could not load the selected dataset.")

    with manage_col2:
        if st.button(
            "Delete selected file",
            width="stretch",
            key="delete_selected_dataset",
        ):
            dataset_id = options[selected_label]
            delete_dataset(dataset_id)
            if st.session_state.active_dataset_id == dataset_id:
                st.session_state.active_dataset_id = None
            st.rerun()

# ---------------- THEME TOGGLE ----------------

dark_mode = st.sidebar.toggle(
    "Dark Mode",
    value=st.session_state.dark_mode,
    key="dark_mode_toggle",
)

st.session_state.dark_mode = dark_mode
inject_theme(dark_mode)

# ---------------- LANDING PAGE ----------------

if not st.session_state.uploaded:

    st.markdown(
        """
        <h1 class="theme-heading main-title">
            📊 Business Analytics Dashboard
        </h1>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <p class="theme-subheading">
            Upload datasets and analyze business performance dynamically.
        </p>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # SAMPLE DATA

    st.markdown(
        """
        <h2 class="theme-heading section-title">
            Example Dataset Format
        </h2>
        """,
        unsafe_allow_html=True
    )

    sample_data = pd.DataFrame({

        "order_id": ["CA-1001", "CA-1002"],
        "category": ["Technology", "Furniture"],
        "sales": [50000, 12000],
        "profit": [5000, 1200],
        "quantity": [2, 4],
        "region": ["West", "East"]

    })

    st.dataframe(
        sample_data,
        width="stretch"
    )

    st.divider()

    # FEATURES

    col1, col2, col3 = st.columns(3)

    with col1:

        st.info(
            """
            ### KPI Tracking

            Monitor sales, profits,
            orders and quantity.
            """
        )

    with col2:

        st.info(
            """
            ### Interactive Charts

            Analyze trends visually
            using dynamic graphs.
            """
        )

    with col3:

        st.info(
            """
            ### Business Insights

            Automatically generate
            business insights.
            """
        )

    st.divider()

    if st.session_state.get("cleanup_message"):
        st.success(st.session_state.cleanup_message)
        del st.session_state.cleanup_message

    st.markdown(
        """
        <h2 class="theme-heading section-title">
            Get Started
        </h2>
        """,
        unsafe_allow_html=True,
    )

    start_choice = st.radio(
        "Choose how to continue",
        [
            "Use a saved dataset",
            "Upload a new CSV file",
        ],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.divider()

    if start_choice == "Use a saved dataset":
        render_saved_dataset_picker()
    else:
        st.markdown(
            """
            <h3 class="theme-heading section-title">
                Upload New Dataset
            </h3>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            key="landing_csv_upload",
        )

        if uploaded_file is not None:
            status, dataset_id = process_csv_upload(uploaded_file, "landing")
            if status == "success" and dataset_id and activate_dataset(dataset_id):
                st.success(f"Saved and loaded: {uploaded_file.name}")
                st.rerun()
            elif status == "failed":
                st.error(
                    "Could not save or load the file. "
                    "Check your database connection and CSV format."
                )

# ---------------- DASHBOARD ----------------

else:

    df = load_from_database()

    if df.empty:
        st.session_state.uploaded = False
        st.rerun()

    # FIX DATE

    if "order_date" in df.columns:

        df["order_date"] = pd.to_datetime(
            df["order_date"]
        )

    active_dataset = get_dataset(st.session_state.active_dataset_id)

    sidebar_section_label("Workspace")

    with st.sidebar.expander("Saved Data", expanded=False):

        if active_dataset:
            st.caption(f"Active: {active_dataset['name']}")
            st.caption(
                f"{active_dataset['rows']:,} rows · "
                f"{format_uploaded_at(active_dataset['uploaded_at'])}"
            )
        else:
            st.caption("No active dataset")

        others = [
            d for d in list_datasets()
            if d["id"] != st.session_state.active_dataset_id
        ]

        if others:
            switch_map = {dataset_option_label(d): d["id"] for d in others}
            picked = st.selectbox("Switch dataset", list(switch_map.keys()))
            if st.button("Load selected", width="stretch"):
                if activate_dataset(switch_map[picked]):
                    st.rerun()
                st.error("Could not switch dataset.")

        extra = st.file_uploader(
            "Upload more CSV files",
            type=["csv"],
            accept_multiple_files=True,
            key="sidebar_csv_upload",
        )
        if extra:
            result = process_csv_uploads(extra, "sidebar")
            if result == "success":
                st.rerun()
            elif result == "failed":
                st.error("Could not save or load the file(s).")

        st.divider()
        render_run_cleanup_button("sidebar_run_cleanup")

        if st.session_state.get("cleanup_message"):
            st.success(st.session_state.cleanup_message)
            del st.session_state.cleanup_message

        if st.button("Back to start", width="stretch"):
            st.session_state.uploaded = False
            st.session_state.processed_upload_landing = None
            st.session_state.processed_upload_sidebar = None
            st.rerun()

        if active_dataset and st.button(
            "Delete active file",
            width="stretch",
        ):
            delete_dataset(st.session_state.active_dataset_id)
            st.session_state.active_dataset_id = None
            st.session_state.uploaded = False
            st.rerun()

    st.sidebar.divider()

    # ---------------- SIDEBAR FILTERS ----------------

    sidebar_section_label("Filters")

    filter_parts = []

    with st.sidebar.container(border=True):
        if "category" in df.columns:
            category = st.multiselect(
                "Category",
                options=sorted(df["category"].dropna().unique()),
                default=sorted(df["category"].dropna().unique()),
            )
            filter_parts.append(f"Categories: {', '.join(category)}")
            df = df[df["category"].isin(category)]

        if "region" in df.columns:
            region = st.multiselect(
                "Region",
                options=sorted(df["region"].dropna().unique()),
                default=sorted(df["region"].dropna().unique()),
            )
            filter_parts.append(f"Regions: {', '.join(region)}")
            df = df[df["region"].isin(region)]

        if "order_date" in df.columns:
            years = sorted(df["order_date"].dt.year.dropna().unique())
            if len(years) > 0:
                min_year = int(min(years))
                max_year = int(max(years))
                selected_years = st.slider(
                    "Select Year Range",
                    min_value=min_year,
                    max_value=max_year,
                    value=(min_year, max_year),
                )
                filter_parts.append(
                    f"Years: {selected_years[0]}–{selected_years[1]}"
                )
                df = df[
                    (df["order_date"].dt.year >= selected_years[0])
                    & (df["order_date"].dt.year <= selected_years[1])
                ]

    filter_summary = (
        "; ".join(filter_parts)
        if filter_parts
        else "All records"
    )

    # ---------------- SIDEBAR PDF DOWNLOAD ----------------

    @st.cache_data(show_spinner="Generating PDF report...")
    def cached_dashboard_pdf(
        filtered_df: pd.DataFrame,
        filter_summary: str,
    ) -> bytes:
        return generate_dashboard_pdf(
            filtered_df.copy(),
            filter_summary,
        )

    sidebar_section_label("Export")

    with st.sidebar.container(border=True):
        st.markdown(
            """
            <div class="sidebar-download-section">
                <p>Dashboard report</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        try:
            st.download_button(
                label="Download Dashboard PDF",
                data=cached_dashboard_pdf(df, filter_summary),
                file_name="business_analytics_report.pdf",
                mime="application/pdf",
                width="stretch",
                type="primary",
            )

        except Exception:
            st.error(
                "PDF export needs kaleido. Run: pip install kaleido"
            )

    # ---------------- DASHBOARD TITLE ----------------

    st.markdown(
        """
        <h1 class="theme-heading dashboard-title">
            📈 Analytics Dashboard
        </h1>
        """,
        unsafe_allow_html=True
    )

    active_name = active_dataset["name"] if active_dataset else "Unknown dataset"
    active_rows = f"{active_dataset['rows']:,} rows" if active_dataset else ""
    st.markdown(
        f"""
        <div class="dashboard-subline">
            <span class="pill"><span class="muted">Active:</span> {active_name}</span>
            <span class="pill"><span class="muted">Filters:</span> {filter_summary}</span>
            {f'<span class="pill"><span class="muted">Data:</span> {active_rows}</span>' if active_rows else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------------- KPIs ----------------

    total_sales, total_profit, total_orders, total_quantity = calculate_kpis(df)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Sales",
        f"{total_sales:,.2f}"
    )

    col2.metric(
        "Total Profit",
        f"{total_profit:,.2f}"
    )

    col3.metric(
        "Orders",
        total_orders
    )

    col4.metric(
        "Quantity",
        total_quantity
    )

    st.divider()

    # ---------------- TABS ----------------

    charts_tab, insights_tab, data_tab = st.tabs([
        "Charts",
        "Business Insights",
        "Dataset"
    ])

    # ---------------- CHARTS ----------------

    with charts_tab:

        chart1, chart2 = st.columns(2)

        # SALES TREND

        with chart1:

            with st.container(border=True):
                st.markdown(
                    """
                    <h2 class="theme-heading section-title">
                        Sales Trend
                    </h2>
                    """,
                    unsafe_allow_html=True
                )

                trend_df = sales_trend(df)

                fig1 = px.line(
                    trend_df,
                    x="order_date",
                    y="sales",
                    markers=True
                )

                fig1.update_layout(
                    xaxis=dict(
                        rangeslider=dict(visible=True),
                        type="date"
                    ),
                    height=460,
                    margin=dict(l=20, r=20, t=40, b=20),
                )

                apply_chart_theme(fig1, dark_mode)

                st.plotly_chart(
                    fig1,
                    width="stretch"
                )

        # CATEGORY CHART

        with chart2:

            with st.container(border=True):
                st.markdown(
                    """
                    <h2 class="theme-heading section-title">
                        Category Performance
                    </h2>
                    """,
                    unsafe_allow_html=True
                )

                category_df = category_analysis(df)

                fig2 = px.bar(
                    category_df,
                    x="category",
                    y="sales",
                    color="category"
                )

                fig2.update_layout(
                    height=460,
                    margin=dict(l=20, r=20, t=40, b=20),
                    showlegend=False,
                )
                apply_chart_theme(fig2, dark_mode)

                st.plotly_chart(
                    fig2,
                    width="stretch"
                )

        # REGION CHART

        with st.container(border=True):
            st.markdown(
                """
                <h2 class="theme-heading section-title">
                    Regional Profit
                </h2>
                """,
                unsafe_allow_html=True
            )

            region_df = region_analysis(df)

            fig3 = px.bar(
                region_df,
                x="region",
                y="profit",
                color="region"
            )

            fig3.update_layout(
                height=460,
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=False,
            )
            apply_chart_theme(fig3, dark_mode)

            st.plotly_chart(
                fig3,
                width="stretch"
            )

    # ---------------- INSIGHTS ----------------

    with insights_tab:

        st.markdown(
            """
            <h2 class="theme-heading section-title">
                Business Insights
            </h2>
            """,
            unsafe_allow_html=True
        )

        insights = generate_insights(df)

        for insight in insights:

            st.success(insight)

    # ---------------- DATA TAB ----------------

    with data_tab:

        st.markdown(
            """
            <h2 class="theme-heading section-title">
                Dataset Preview
            </h2>
            """,
            unsafe_allow_html=True
        )
        with st.container(border=True):
            st.dataframe(
                df,
                width="stretch"
            )
