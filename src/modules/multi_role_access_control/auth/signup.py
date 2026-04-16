"""
auth/signup.py — Streamlit signup page wired to MongoDB backend.
"""
import hashlib
from datetime import datetime, timezone

import streamlit as st
from backend.database import get_db_connection
from backend.audit import log_audit_event


def signup_page():
    st.title("Create Account")

    db = get_db_connection()
    # Build a list of creatable roles dynamically from MongoDB 
    available_roles = [r["Role_name"] for r in db["roles"].find({"Role_name": {"$in": ["Patient", "Doctor"]}})]
    if not available_roles:
        available_roles = ["Patient", "Doctor"] # safe fallback
        
    role = st.selectbox("Signup as", available_roles)
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Create Account"):
        if not username or not email or not password:
            st.error("All fields are required.")
            return

        if not username or not email or not password:
            st.error("All fields are required.")
            return

        # Check if username or email already exists
        if db["users"].find_one({"Username": username}):
            st.error("❌ Username already taken.")
            return
        if db["users"].find_one({"Email": email}):
            st.error("❌ Email already registered.")
            return

        # Hash password (SHA-256 for demo — matches auth_service.py)
        pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        # Find the role ObjectId from the roles collection
        role_doc = db["roles"].find_one({"Role_name": role})
        assigned_roles = [{"role_id": role_doc["_id"]}] if role_doc else []

        user_doc = {
            "Username": username,
            "Hashed_password": pw_hash,
            "Email": email,
            "Status": "Active",
            "Assigned_Roles": assigned_roles,
        }

        result = db["users"].insert_one(user_doc)

        log_audit_event(db, action="USER_SIGNUP", user_id=str(result.inserted_id),
                        target_entity="users", status="SUCCESS",
                        details={"role": role})

        st.success(f"✅ Account created! Username: **{username}**, Role: **{role}**")
        st.info("You can now log in.")
        st.session_state.page = "login"

    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.rerun()
