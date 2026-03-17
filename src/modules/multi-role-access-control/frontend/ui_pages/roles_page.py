import streamlit as st

# from backend.services.role_service import (
#     create_role,
#     get_all_roles,
#     assign_permission_to_role
# )

# from backend.services.access_control_service import get_all_permissions
from mock_backend.services import (
    create_role,
    get_all_roles,
    assign_permission_to_role
)
from mock_backend.services import get_all_permissions


def show_roles_page():

    st.title("Role Management")

    st.subheader("Create New Role")

    role_name = st.text_input("Role Name")
    description = st.text_input("Description")

    if st.button("Create Role"):

        if role_name:

            create_role(role_name, description)

            st.success("Role created successfully")

        else:
            st.error("Role name is required")

    st.divider()

    st.subheader("Assign Permission to Role")

    roles = get_all_roles()
    permissions = get_all_permissions()

    role_names = [r["role_name"] for r in roles]
    permission_names = [p["permission_name"] for p in permissions]

    selected_role = st.selectbox("Select Role", role_names)
    selected_permission = st.selectbox("Select Permission", permission_names)

    if st.button("Assign Permission"):

        assign_permission_to_role(selected_role, selected_permission)

        st.success("Permission assigned successfully")

    st.divider()

    st.subheader("All Roles")

    if roles:

        st.dataframe(roles)

    else:

        st.write("No roles found")