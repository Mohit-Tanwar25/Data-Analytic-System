from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
from plotly.io import to_image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from analysis import (
    calculate_kpis,
    category_analysis,
    generate_insights,
    region_analysis,
    sales_trend,
)

CHART_COLORS = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#ea580c",
    "#9333ea",
    "#0891b2",
    "#ca8a04",
    "#db2777",
    "#4f46e5",
    "#059669",
]

CHART_LAYOUT = dict(
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(color="#0f172a", size=12),
    margin=dict(l=50, r=30, t=50, b=50),
    colorway=CHART_COLORS,
)


def _apply_vivid_style(fig, chart_type: str):
    """Force saturated colours so Kaleido PNG export matches dashboard charts."""
    fig.update_layout(
        **CHART_LAYOUT,
        showlegend=chart_type == "bar",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.8)",
        ),
    )

    if chart_type == "line":
        fig.update_traces(
            line=dict(color="#2563eb", width=3),
            marker=dict(
                color=CHART_COLORS,
                size=10,
                line=dict(width=1.5, color="#ffffff"),
            ),
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.25)",
        )
        fig.update_layout(
            xaxis=dict(
                rangeslider=dict(visible=False),
                type="date",
                gridcolor="#e2e8f0",
            ),
            yaxis=dict(gridcolor="#e2e8f0"),
        )

    elif chart_type == "bar":
        fig.update_traces(
            marker=dict(
                line=dict(color="#ffffff", width=1.2),
                opacity=0.95,
            ),
        )
        fig.update_layout(
            xaxis=dict(gridcolor="#e2e8f0"),
            yaxis=dict(gridcolor="#e2e8f0"),
        )


def _fig_to_image(fig, width=900, height=450):
    fig.update_layout(height=height)
    return to_image(
        fig,
        format="png",
        width=width,
        height=height,
        scale=2,
        engine="kaleido",
    )


def _build_chart_figures(df):
    charts = []

    trend_df = sales_trend(df)
    if not trend_df.empty:
        fig1 = px.line(
            trend_df,
            x="order_date",
            y="sales",
            markers=True,
            color_discrete_sequence=CHART_COLORS,
        )
        _apply_vivid_style(fig1, "line")
        charts.append(("Sales Trend", fig1))

    category_df = category_analysis(df)
    if not category_df.empty:
        fig2 = px.bar(
            category_df,
            x="category",
            y="sales",
            color="category",
            color_discrete_sequence=CHART_COLORS,
            text="sales",
        )
        fig2.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="outside",
            textfont=dict(color="#0f172a", size=10),
        )
        _apply_vivid_style(fig2, "bar")
        charts.append(("Category Performance", fig2))

    region_df = region_analysis(df)
    if not region_df.empty:
        fig3 = px.bar(
            region_df,
            x="region",
            y="profit",
            color="region",
            color_discrete_sequence=CHART_COLORS,
            text="profit",
        )
        fig3.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="outside",
            textfont=dict(color="#0f172a", size=10),
        )
        _apply_vivid_style(fig3, "bar")
        charts.append(("Regional Profit", fig3))

    return charts


def generate_dashboard_pdf(
    df: pd.DataFrame,
    filter_summary: str | None = None,
) -> bytes:
    """Build a PDF with KPIs, coloured charts, and insights (no dataset table)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=22,
        spaceAfter=8,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.HexColor("#1e40af"),
    )
    insight_style = ParagraphStyle(
        "Insight",
        parent=styles["Normal"],
        fontSize=11,
        leftIndent=12,
        spaceAfter=8,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []
    generated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    story.append(Paragraph("Business Analytics Dashboard Report", title_style))
    story.append(Paragraph(f"Generated on {generated_at}", subtitle_style))

    if filter_summary:
        story.append(Paragraph(f"<b>Applied filters:</b> {filter_summary}", subtitle_style))

    total_sales, total_profit, total_orders, total_quantity = calculate_kpis(df)

    story.append(Paragraph("Key Performance Indicators", section_style))

    kpi_data = [
        ["Metric", "Value"],
        ["Total Sales", f"{total_sales:,.2f}"],
        ["Total Profit", f"{total_profit:,.2f}"],
        ["Orders", f"{total_orders:,}"],
        ["Quantity", f"{total_quantity:,}"],
    ]

    kpi_table = Table(kpi_data, colWidths=[2.8 * inch, 3.2 * inch])
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 0.25 * inch))

    charts = _build_chart_figures(df)
    if charts:
        story.append(PageBreak())
        story.append(Paragraph("Analytics Charts", section_style))
        story.append(Spacer(1, 0.1 * inch))

        page_width = letter[0] - 1.2 * inch

        for index, (chart_title, fig) in enumerate(charts):
            png_bytes = _fig_to_image(fig)
            img_buffer = BytesIO(png_bytes)

            story.append(Paragraph(chart_title, section_style))

            img = Image(img_buffer, width=page_width, height=page_width * 0.45)
            story.append(img)
            story.append(Spacer(1, 0.15 * inch))

            if index == 0 and len(charts) > 1:
                story.append(PageBreak())

    insights = generate_insights(df)
    if insights:
        story.append(PageBreak())
        story.append(Paragraph("Business Insights", section_style))
        story.append(Spacer(1, 0.1 * inch))

        for insight in insights:
            story.append(Paragraph(f"• {insight}", insight_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
