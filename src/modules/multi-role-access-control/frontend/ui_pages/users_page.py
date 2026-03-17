import streamlit as st

# from backend.services.user_service import (
#     create_user,
#     get_all_users,
#     assign_role_to_user
# )

# from backend.services.role_service import get_all_roles

from mock_backend.services import (
    create_user,
    get_all_users,
    assign_role_to_user
)
from mock_backend.services import get_all_roles


def show_users_page():

    st.title("User Management")

    st.subheader("Create New User")

    with st.form("create_user_form"):

        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        submitted = st.form_submit_button("Create User")

        if submitted:

            if username and email and password:

                create_user(username, email, password)

                st.success("User created successfully")

            else:
                st.error("Please fill all fields")

    st.divider()

    st.subheader("Assign Role to User")

    users = get_all_users()
    roles = get_all_roles()

    user_names = [u["username"] for u in users]
    role_names = [r["role_name"] for r in roles]

    selected_user = st.selectbox("Select User", user_names)
    selected_role = st.selectbox("Select Role", role_names)

    if st.button("Assign Role"):

        assign_role_to_user(selected_user, selected_role)

        st.success("Role assigned successfully")

    st.divider()

    st.subheader("All Users")

    users = get_all_users()

    if users:
        st.dataframe(users)

    else:
        st.write("No users found")