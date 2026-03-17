from pymongo import ASCENDING
from pymongo.collection import Collection

def init_delegations_collection(db) -> Collection:
    """
    Initializes the `delegations` collection and creates necessary indexes.
    Run this once during application startup or deployment.
    """
    delegations_col = db["delegations"]
    
    # 1. TTL Index: Automatically drops the document from the collection
    # exactly when the 'end_time' is reached. (Runs every 60s natively in MongoDB)
    delegations_col.create_index(
        [("end_time", ASCENDING)],
        expireAfterSeconds=0, 
        name="ttl_end_time_removal"
    )
    
    # 2. Compound Index: Optimizes the frequent queries used by the gatekeeper
    # when evaluating a user's active delegations during login or action.
    delegations_col.create_index(
        [("delegatee_id", ASCENDING), ("status", ASCENDING), ("start_time", ASCENDING)],
        name="idx_active_delegations_lookup"
    )
    
    print("Delegations collection initialized with TTL and Lookup indexes.")
    return delegations_col
