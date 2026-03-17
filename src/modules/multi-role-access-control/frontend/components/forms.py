import streamlit as st


def user_form():

    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    return username, email, password



def role_form():

    role_name = st.text_input("Role Name")
    description = st.text_input("Description")

    return role_name, description



def delegation_form(user_names, role_names):

    delegator = st.selectbox("Delegator (From User)", user_names)
    delegatee = st.selectbox("Delegatee (To User)", user_names)
    role = st.selectbox("Role", role_names)

    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

    reason = st.text_input("Reason")

    return delegator, delegatee, role, start_date, end_date, reason