import streamlit as st
import pandas as pd


def render_table(data, title=None):

    if title:
        st.subheader(title)

    if not data:
        st.write("No data available")
        return

    df = pd.DataFrame(data)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )