import streamlit as st
import datetime
from backend.database import get_db_connection
from backend.reviews_service import (
    create_review_campaign,
    certify_access,
    revoke_access_review,
    get_active_campaigns
)

def show_reviews_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("Access Recertification")
    st.write("Periodically review and certify user access to ensure compliance.")

    tab_active, tab_create = st.tabs(["Active Campaigns", "Create Campaign"])

    with tab_active:
        campaigns = get_active_campaigns(db)
        if not campaigns:
            st.info("No active recertification campaigns.")
        else:
            for c in campaigns:
                with st.expander(f"Campaign: {c.get('title')} (Deadline: {c.get('deadline').date() if c.get('deadline') else 'N/A'})"):
                    reviews = c.get("reviews", [])
                    pending_reviews = [r for r in reviews if r.get("status") == "Pending"]
                    
                    if not pending_reviews:
                        st.success("All access lines in this campaign have been reviewed.")
                    else:
                        st.write(f"**{len(pending_reviews)}** access lines awaiting review.")
                        
                        for r in pending_reviews:
                            user_id = r.get("user_id")
                            role_id = r.get("role_id")
                            
                            user_doc = db["users"].find_one({"_id": user_id})
                            role_doc = db["roles"].find_one({"_id": role_id})
                            
                            username = user_doc.get("Username", str(user_id)) if user_doc else str(user_id)
                            role_name = role_doc.get("Role_name", str(role_id)) if role_doc else str(role_id)
                            
                            col1, col2, col3 = st.columns([4,1,1])
                            with col1:
                                st.write(f"User **{username}** holds role **{role_name}**")
                            with col2:
                                if st.button("✅ Certify", key=f"cert_{c['_id']}_{user_id}_{role_id}"):
                                    certify_access(db, admin_id, str(c["_id"]), str(user_id), str(role_id))
                                    st.rerun()
                            with col3:
                                if st.button("❌ Revoke", key=f"rev_{c['_id']}_{user_id}_{role_id}"):
                                    revoke_access_review(db, admin_id, str(c["_id"]), str(user_id), str(role_id))
                                    st.rerun()
                            st.divider()

    with tab_create:
        st.subheader("Launch New Campaign")
        title = st.text_input("Campaign Title", value=f"Q{((datetime.datetime.now().month-1)//3)+1} {datetime.datetime.now().year} Access Review")
        deadline = st.date_input("Deadline")
        
        if st.button("Create Campaign"):
            try:
                deadline_dt = datetime.datetime.combine(deadline, datetime.datetime.min.time())
                campaign_id = create_review_campaign(db, admin_id, title, deadline_dt)
                st.success(f"Campaign generated successfully! ID: {campaign_id}")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating campaign: {e}")
