"""
permission_guard.py — Reusable UI-level permission gate for Streamlit.

Provides decorators, context managers, and utility functions to dynamically
show/hide/disable UI elements based on the current user's effective permissions.
"""
import streamlit as st
from contextlib import contextmanager


# ──────────────────────────────────────────────────────────────────────
# Simple permission check
# ──────────────────────────────────────────────────────────────────────

def has_permission(permission_name: str) -> bool:
    """Check if the current user has a specific permission."""
    perms = st.session_state.get("permissions", [])
    return permission_name in perms


def has_any_permission(*permission_names) -> bool:
    """Check if the current user has ANY of the listed permissions."""
    perms = st.session_state.get("permissions", [])
    return any(p in perms for p in permission_names)


def has_all_permissions(*permission_names) -> bool:
    """Check if the current user has ALL of the listed permissions."""
    perms = st.session_state.get("permissions", [])
    return all(p in perms for p in permission_names)


# ──────────────────────────────────────────────────────────────────────
# Context manager for permission-gated UI blocks
# ──────────────────────────────────────────────────────────────────────

@contextmanager
def require_permission(permission_name: str, fallback_msg: str = None):
    """
    Context manager that gates a Streamlit UI block behind a permission check.

    Usage:
        with require_permission("EDIT_PATIENT_DATA"):
            st.button("Edit Record")
    
    If the user lacks the permission, a styled denied card is shown instead.
    """
    if has_permission(permission_name):
        yield True
    else:
        msg = fallback_msg or f"🔒 Access Denied: requires `{permission_name}` permission."
        st.warning(msg)
        yield False


@contextmanager
def require_any_permission(*permission_names, fallback_msg: str = None):
    """Gate behind ANY of the listed permissions."""
    if has_any_permission(*permission_names):
        yield True
    else:
        msg = fallback_msg or f"🔒 Access Denied: requires one of {list(permission_names)}."
        st.warning(msg)
        yield False


# ──────────────────────────────────────────────────────────────────────
# Visual indicators
# ──────────────────────────────────────────────────────────────────────

_ROLE_COLORS = {
    "Admin": "🔴",
    "System_Admin": "🔴",
    "Lead_Doctor": "🟠",
    "Lead Doctor": "🟠",
    "Doctor": "🔵",
    "Nurse": "🟢",
    "Patient": "🟣",
}


def role_indicator():
    """Render the user's current role as a colored badge in the sidebar."""
    role = st.session_state.get("role", "Unknown")
    emoji = _ROLE_COLORS.get(role, "⚪")
    perms = st.session_state.get("permissions", [])
    st.markdown(f"{emoji} **{role}** · {len(perms)} permissions")


def permission_badge():
    """
    Render the user's active permissions as styled chips.
    Best placed in an expander for clean UI.
    """
    perms = st.session_state.get("permissions", [])
    if not perms:
        st.caption("No active permissions.")
        return

    # Group into rows of 3
    for i in range(0, len(perms), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(perms):
                col.markdown(f"`{perms[idx]}`")


def delegation_indicator(db):
    """
    Show an indicator if the user has active incoming delegations.
    Counts how many delegated permissions the user currently has.
    """
    from bson import ObjectId
    from datetime import datetime

    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    try:
        uid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    except Exception:
        return

    now = datetime.utcnow()
    active_delegations = db["delegations"].count_documents({
        "Delegatee_id": uid,
        "Status": "Active",
        "Start_time": {"$lte": now},
        "End_time": {"$gt": now}
    })

    if active_delegations > 0:
        st.markdown(f"⚡ **+{active_delegations} delegated** role(s) active")


def user_status_badge(status: str) -> str:
    """Return a colored emoji for a user status string."""
    badges = {
        "Active": "🟢",
        "Inactive": "🔴",
        "Suspended": "🟡",
    }
    return badges.get(status, "⚪")
