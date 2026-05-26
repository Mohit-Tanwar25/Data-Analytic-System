import streamlit.components.v1 as components


def inject_theme(dark_mode: bool) -> None:
    """Load CSS and set data-theme on .stApp so selectors apply correctly."""
    import streamlit as st

    theme = "dark" if dark_mode else "light"

    with open("style.css", encoding="utf-8") as f:
        base_css = f.read()

    st.markdown(
        f"<style>{base_css}</style>",
        unsafe_allow_html=True,
    )

    components.html(
        f"""
        <script>
            const doc = window.parent.document;
            const app = doc.querySelector(".stApp");
            if (app) {{
                app.setAttribute("data-theme", "{theme}");
            }}
        </script>
        """,
        height=0,
    )


def apply_chart_theme(fig, dark_mode: bool):
    if dark_mode:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(30, 41, 59, 0.6)",
            font=dict(color="#f8fafc"),
        )
    else:
        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248, 250, 252, 0.8)",
            font=dict(color="#0f172a"),
        )

    return fig
