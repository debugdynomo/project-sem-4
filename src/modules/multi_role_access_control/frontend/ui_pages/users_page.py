import streamlit as st

from backend.database import get_db_connection
from admin_service import (
    create_user,
    get_all_users,
    assign_role_to_user,
    get_all_roles
)

def show_users_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("User Management")

    st.subheader("Create New User")

    with st.form("create_user_form"):

        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        submitted = st.form_submit_button("Create User")

        if submitted:

            if username and email and password:
                try:
                    create_user(db, admin_id, username, email, password)
                    st.success("User created successfully")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

            else:
                st.error("Please fill all fields")

    st.divider()

    st.subheader("Assign Role to User")

    users = get_all_users(db)
    roles = get_all_roles(db)

    user_names = [u.get("Username", "Unknown") for u in users]
    role_names = [r.get("Role_name", "Unknown") for r in roles]

    selected_user = st.selectbox("Select User", user_names)
    selected_role = st.selectbox("Select Role", role_names)

    if st.button("Assign Role"):
        try:
            # We need to map back to target_user_id and new_role
            target_user = next((u for u in users if u.get("Username") == selected_user), None)
            if target_user:
                assign_role_to_user(db, admin_id, str(target_user["_id"]), selected_role)
                st.success("Role assigned successfully")
            else:
                st.error("Selected user not found.")
        except Exception as e:
            st.error(f"Error: {str(e)}")

    st.divider()

    st.subheader("All Users")
    users = get_all_users(db)

    if users:
        st.dataframe(users)

    else:
        st.write("No users found")