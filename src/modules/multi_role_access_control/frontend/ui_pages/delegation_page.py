import streamlit as st
from datetime import datetime

from backend.database import get_db_connection
from admin_service import (
    get_all_users,
    get_all_roles,
    get_active_delegations,
    get_pending_delegations,
    create_delegation,
    revoke_delegation,
    approve_delegation,
    reject_delegation
)

def show_delegation_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("Role Delegation")

    tab_create, tab_pending, tab_active, tab_chains = st.tabs([
        "Create Delegation", "Pending Approvals", "Active Delegations", "Delegation Chains"
    ])

    # ── TAB 1: Create Delegation ──
    with tab_create:
        st.subheader("Create Delegation")

        users = get_all_users(db)
        roles = get_all_roles(db)

        user_names = [u.get("Username", "Unknown") for u in users]
        role_names = [r.get("Role_name", "Unknown") for r in roles]

        delegator = st.selectbox("Delegator (From User)", user_names)
        delegatee = st.selectbox("Delegatee (To User)", user_names)
        role = st.selectbox("Role to Delegate", role_names)

        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")

        reason = st.text_input("Reason")

        if st.button("Create Delegation"):
            if delegator != delegatee:
                try:
                    delegator_id = next((u["_id"] for u in users if u.get("Username") == delegator), None)
                    delegatee_id = next((u["_id"] for u in users if u.get("Username") == delegatee), None)
                    role_id = next((r["_id"] for r in roles if r.get("Role_name") == role), None)

                    if not delegator_id or not delegatee_id or not role_id:
                        st.error("Invalid selection for users or role.")
                    else:
                        create_delegation(
                            db,
                            delegator_id,
                            delegatee_id,
                            role_id,
                            datetime.combine(start_date, datetime.min.time()),
                            datetime.combine(end_date, datetime.max.time()),
                            reason,
                            delegation_type="Hierarchical"
                        )
                        st.success("Delegation submitted for admin approval!")
                except Exception as e:
                    st.error(f"Validation or Database Error: {str(e)}")
            else:
                st.error("Delegator and Delegatee cannot be identical")

    # ── TAB 2: Pending Approvals ──
    with tab_pending:
        st.subheader("Pending Delegation Requests")
        pending = get_pending_delegations(db)

        if not pending:
            st.success("No pending delegation requests.")
        else:
            for d in pending:
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        st.markdown(f"**{d.get('Delegator_Name', 'Unknown')}** → **{d.get('Delegatee_Name', 'Unknown')}**")
                        st.caption(
                            f"Role: {d.get('Target_Role_Name', 'N/A')} | "
                            f"Type: {d.get('Delegation_type', 'N/A')} | "
                            f"Reason: {d.get('Reason', 'N/A')}"
                        )
                    with col2:
                        if st.button("Approve", key=f"adm_approve_{d['_id']}"):
                            try:
                                approve_delegation(db, admin_id=admin_id, delegation_id=str(d["_id"]))
                                st.success("Delegation approved!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    with col3:
                        if st.button("Reject", key=f"adm_reject_{d['_id']}"):
                            try:
                                reject_delegation(db, admin_id=admin_id, delegation_id=str(d["_id"]))
                                st.warning("Delegation rejected.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    st.divider()

    # ── TAB 3: Active Delegations ──
    with tab_active:
        st.subheader("Active Delegations")

        delegations = get_active_delegations(db)
        
        del_formatted = []
        for d in delegations:
            record = d.copy()
            record["_id"] = str(d["_id"])
            record["Delegator_id"] = str(d.get("Delegator_id"))
            record["Delegatee_id"] = str(d.get("Delegatee_id"))
            record["Target_Role_id"] = str(d.get("Target_Role_id"))
            del_formatted.append(record)

        if del_formatted:
            st.dataframe(del_formatted)
            
            st.subheader("Revoke Delegation")
            del_ids = [d["_id"] for d in del_formatted]
            revoke_id = st.selectbox("Select Delegation to Revoke", del_ids)
            if st.button("Revoke Delegation"):
                try:
                    revoke_delegation(db, admin_id, revoke_id)
                    st.success("Delegation revoked successfully")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        else:
            st.write("No active delegations")

    # ── TAB 4: Delegation Chains ──
    with tab_chains:
        st.subheader("Delegation Chain Tracer")
        st.markdown("Trace delegation chains from a selected user using `$graphLookup`.")

        users = get_all_users(db)
        user_map = {u.get("Username", "Unknown"): str(u["_id"]) for u in users}
        selected_user = st.selectbox("Select User to Trace", list(user_map.keys()), key="chain_user")

        if st.button("Trace Chains", key="trace_btn"):
            from bson import ObjectId as _OID
            user_oid = _OID(user_map[selected_user])

            # Use $graphLookup to find all delegation chains starting from this user
            chain_pipeline = [
                {"$match": {"Delegatee_id": user_oid, "Status": "Active"}},
                {"$graphLookup": {
                    "from": "delegations",
                    "startWith": "$Delegator_id",
                    "connectFromField": "Delegator_id",
                    "connectToField": "Delegatee_id",
                    "as": "chain",
                    "maxDepth": 5,
                    "depthField": "depth",
                    "restrictSearchWithMatch": {"Status": "Active"}
                }}
            ]

            results = list(db["delegations"].aggregate(chain_pipeline))

            if not results:
                st.info(f"No active delegation chains found for **{selected_user}**.")
            else:
                for i, root in enumerate(results):
                    delegator_doc = db["users"].find_one({"_id": root["Delegator_id"]})
                    delegatee_doc = db["users"].find_one({"_id": root["Delegatee_id"]})
                    role_doc = db["roles"].find_one({"_id": root["Target_Role_id"]})

                    delegator_name = delegator_doc.get("Username", "?") if delegator_doc else "?"
                    delegatee_name = delegatee_doc.get("Username", "?") if delegatee_doc else "?"
                    role_name = role_doc.get("Role_name", "?") if role_doc else "?"

                    st.markdown(f"#### Chain {i+1}")

                    # Root link
                    chain_display = f"**{delegator_name}** →  `{role_name}` → **{delegatee_name}**"

                    # Extended chain links
                    chain_links = sorted(root.get("chain", []), key=lambda x: x.get("depth", 0))
                    for link in chain_links:
                        link_delegator = db["users"].find_one({"_id": link["Delegator_id"]})
                        link_role = db["roles"].find_one({"_id": link["Target_Role_id"]})
                        ln = link_delegator.get("Username", "?") if link_delegator else "?"
                        lr = link_role.get("Role_name", "?") if link_role else "?"
                        chain_display += f" ← `{lr}` ← **{ln}**"

                    st.markdown(chain_display)
                    st.caption(f"Chain depth: {len(chain_links) + 1} | "
                              f"Type: {root.get('Delegation_type', 'N/A')} | "
                              f"Expires: {root.get('End_time', 'N/A')}")
                    st.divider()