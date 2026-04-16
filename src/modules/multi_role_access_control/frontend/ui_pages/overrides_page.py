"""
overrides_page.py — Dedicated Emergency Override analytics page for Admin dashboard.
Shows all overrides (active + resolved), resolution metrics, and usage frequency.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from backend.database import get_db_connection
from backend.override_tracker import get_active_overrides, resolve_emergency_override


def show_overrides_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("🚨 Emergency Override Tracking")
    st.caption("Comprehensive view of all break-glass override events.")

    tab_active, tab_history, tab_analytics = st.tabs([
        "🔴 Active Overrides", "📋 Full History", "📊 Analytics"
    ])

    # ── TAB 1: Active Overrides ──
    with tab_active:
        overrides = get_active_overrides(db)

        if not overrides:
            st.success("✅ No active emergency overrides. System is in normal operation.")
        else:
            st.error(f"**{len(overrides)}** unresolved emergency override(s) require attention!")

            for o in overrides:
                user_doc = db["users"].find_one({"_id": o.get("user_id")})
                username = user_doc.get("Username", "Unknown") if user_doc else "Unknown"

                hours_elapsed = (datetime.utcnow() - o.get("timestamp", datetime.utcnow())).total_seconds() / 3600

                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**User:** {username}")
                        st.markdown(f"**Target System:** `{o.get('overridden_system', 'N/A')}`")
                        st.caption(f"Reason: {o.get('reason', 'N/A')}")
                        st.caption(f"Activated: {o.get('timestamp', 'N/A')} | "
                                  f"Duration: {o.get('duration_hours', 'N/A')}h | "
                                  f"Elapsed: {hours_elapsed:.1f}h")
                    with col2:
                        if hours_elapsed > o.get("duration_hours", 1):
                            st.warning("⏰ OVERDUE")
                        else:
                            st.info("⏳ Active")
                    with col3:
                        if st.button("✅ Resolve", key=f"resolve_{o['_id']}"):
                            resolve_emergency_override(db, admin_id, str(o["_id"]))
                            st.success("Override resolved.")
                            st.rerun()
                    st.divider()

    # ── TAB 2: Full History ──
    with tab_history:
        all_overrides = list(db["overrides"].find({}).sort("timestamp", -1).limit(100))

        if not all_overrides:
            st.info("No override events recorded.")
        else:
            history_data = []
            for o in all_overrides:
                user_doc = db["users"].find_one({"_id": o.get("user_id")})
                username = user_doc.get("Username", "Unknown") if user_doc else "Unknown"

                resolved_by_name = "-"
                if o.get("resolved_by"):
                    rb_doc = db["users"].find_one({"_id": o["resolved_by"]})
                    resolved_by_name = rb_doc.get("Username", "Unknown") if rb_doc else "Unknown"

                # Calculate time-to-resolution
                ttr = "-"
                if o.get("resolved") and o.get("resolved_at") and o.get("timestamp"):
                    delta = (o["resolved_at"] - o["timestamp"]).total_seconds() / 3600
                    ttr = f"{delta:.1f}h"

                history_data.append({
                    "User": username,
                    "Target System": o.get("overridden_system", "N/A"),
                    "Reason": o.get("reason", "N/A"),
                    "Activated": o.get("timestamp", "N/A"),
                    "Duration (h)": o.get("duration_hours", "N/A"),
                    "Status": "✅ Resolved" if o.get("resolved") else "🔴 Active",
                    "Resolved By": resolved_by_name,
                    "Time to Resolution": ttr
                })

            st.dataframe(pd.DataFrame(history_data), width="stretch")

    # ── TAB 3: Analytics ──
    with tab_analytics:
        all_overrides = list(db["overrides"].find({}))

        if not all_overrides:
            st.info("No data for analytics.")
        else:
            total = len(all_overrides)
            resolved = sum(1 for o in all_overrides if o.get("resolved"))
            active = total - resolved

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Overrides", total)
            col2.metric("Resolved", resolved)
            col3.metric("Active/Unresolved", active)

            st.divider()

            # Frequency by user
            st.subheader("Override Frequency by User")
            user_freq = {}
            for o in all_overrides:
                user_doc = db["users"].find_one({"_id": o.get("user_id")})
                username = user_doc.get("Username", "Unknown") if user_doc else "Unknown"
                user_freq[username] = user_freq.get(username, 0) + 1

            freq_df = pd.DataFrame([
                {"User": u, "Override Count": c} for u, c in
                sorted(user_freq.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(freq_df, width="stretch")

            # Average time to resolution
            resolved_overrides = [o for o in all_overrides if o.get("resolved") and o.get("resolved_at") and o.get("timestamp")]
            if resolved_overrides:
                avg_ttr = sum(
                    (o["resolved_at"] - o["timestamp"]).total_seconds() / 3600
                    for o in resolved_overrides
                ) / len(resolved_overrides)
                st.metric("Avg. Time to Resolution", f"{avg_ttr:.1f} hours")
            else:
                st.info("No resolved overrides to calculate average resolution time.")
