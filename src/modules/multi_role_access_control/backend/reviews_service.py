from datetime import datetime
from bson import ObjectId
from backend.audit import audit_action

def safe_objectid(val):
    if not val:
        return None
    if isinstance(val, ObjectId):
        return val
    try:
        return ObjectId(val)
    except:
        return val

@audit_action(action="CREATE_REVIEW_CAMPAIGN", target_entity="access_reviews")
def create_review_campaign(db, admin_id: str, title: str, deadline: datetime) -> str:
    """
    Creates a new recertification campaign for all users and their permanent roles.
    """
    reviews = []
    users = db["users"].find({})
    for user in users:
        for r in user.get("Assigned_Roles", []):
            role_id = r.get("role_id") if isinstance(r, dict) else r
            reviews.append({
                "user_id": user["_id"],
                "role_id": role_id,
                "status": "Pending",
                "reviewed_by": None,
                "review_date": None
            })
            
    campaign_doc = {
        "title": title,
        "deadline": deadline,
        "created_by": safe_objectid(admin_id),
        "created_at": datetime.utcnow(),
        "status": "Active",
        "reviews": reviews
    }
    result = db["access_reviews"].insert_one(campaign_doc)
    return str(result.inserted_id)

@audit_action(action="CERTIFY_ACCESS", target_entity="access_reviews")
def certify_access(db, admin_id: str, campaign_id: str, user_id: str, role_id: str) -> bool:
    """Approves a user's role in a campaign."""
    result = db["access_reviews"].update_one(
        {
            "_id": safe_objectid(campaign_id), 
            "reviews.user_id": safe_objectid(user_id), 
            "reviews.role_id": safe_objectid(role_id)
        },
        {"$set": {
            "reviews.$.status": "Approved",
            "reviews.$.reviewed_by": safe_objectid(admin_id),
            "reviews.$.review_date": datetime.utcnow()
        }}
    )
    return result.modified_count > 0

@audit_action(action="REVOKE_ACCESS_REVIEW", target_entity="access_reviews")
def revoke_access_review(db, admin_id: str, campaign_id: str, user_id: str, role_id: str) -> bool:
    """Revokes a user's role during a review. Also removes it from the user document."""
    result = db["access_reviews"].update_one(
        {
            "_id": safe_objectid(campaign_id), 
            "reviews.user_id": safe_objectid(user_id), 
            "reviews.role_id": safe_objectid(role_id)
        },
        {"$set": {
            "reviews.$.status": "Revoked",
            "reviews.$.reviewed_by": safe_objectid(admin_id),
            "reviews.$.review_date": datetime.utcnow()
        }}
    )
    # Remove from user's assigned roles
    from admin_service import revoke_role_from_user
    role_doc = db["roles"].find_one({"_id": safe_objectid(role_id)})
    if role_doc:
        revoke_role_from_user(db, admin_id, str(user_id), role_doc["Role_name"])
        
    return result.modified_count > 0

def get_active_campaigns(db) -> list:
    return list(db["access_reviews"].find({"status": "Active"}).sort("created_at", -1))

@audit_action(action="PROCESS_EXPIRED_CAMPAIGNS", target_entity="access_reviews")
def process_expired_campaigns(db, system_admin_id: str) -> int:
    """
    Finds active campaigns past their deadline. For any 'Pending' reviews,
    automatically revokes the user's role and marks the campaign as 'Completed'.
    Returns the number of campaigns processed.
    """
    now = datetime.utcnow()
    expired_campaigns = list(db["access_reviews"].find(
        {"status": "Active", "deadline": {"$lt": now}}
    ))
    
    processed = 0
    for c in expired_campaigns:
        campaign_id = str(c["_id"])
        
        for r in c.get("reviews", []):
            if r.get("status") == "Pending":
                # Auto-revoke
                try:
                    revoke_access_review(db, system_admin_id, campaign_id, str(r["user_id"]), str(r["role_id"]))
                except Exception:
                    pass
        
        # Mark campaign as Completed
        db["access_reviews"].update_one(
            {"_id": safe_objectid(campaign_id)},
            {"$set": {"status": "Completed"}}
        )
        processed += 1
        
    return processed
