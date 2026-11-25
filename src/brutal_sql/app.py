"""Streamlit entry point for Brutal SQL.

Run with: ``poetry run streamlit run src/brutal_sql/app.py``
"""

import streamlit as st

from brutal_sql.logging_config import configure_logging

APP_TITLE = "Brutal SQL"
APP_TAGLINE = (
    "Text-to-SQL by brute-force generation, "
    "guided by a graph ontology of your database schema."
)


def render_landing_page() -> None:
    """Render the landing page: browser tab title, page heading and tagline."""
    st.set_page_config(page_title=APP_TITLE, page_icon="🧱")
    st.title(APP_TITLE)
    st.caption(APP_TAGLINE)


def main() -> None:
    """Start the Brutal SQL Streamlit app."""
    configure_logging()
    render_landing_page()


if __name__ == "__main__":
    main()
