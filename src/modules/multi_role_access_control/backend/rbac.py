from bson import ObjectId
from bson.errors import InvalidId

def get_effective_permissions(user_id, db):
    """
    Given a User's ID, recursively fetches all permissions from their directly 
    assigned roles and all inherited roles using MongoDB's $graphLookup.
    
    This fulfills the "DBMS Concepts" requirement for the G41 system dealing
    with complex data logic and recursive hierarchies.
    """
    
    if db is None:
        return []

    # Ensure user_id is an ObjectId
    if isinstance(user_id, str):
        try:
            user_id = ObjectId(user_id)
        except InvalidId:
            return []
    elif not isinstance(user_id, ObjectId):
        return []

    from datetime import datetime
    now = datetime.utcnow()

    pipeline = [
        # 1. Match the specific User
        {
            "$match": { "_id": user_id }
        },
        # 2. Normalize Assigned_Roles so empty/null users safely return []
        {
            "$project": {
                "Assigned_Roles": {"$ifNull": ["$Assigned_Roles", []]}
            }
        },
        # 2.5. Fetch active Delegations where Delegatee_id == user_id
        {
            "$lookup": {
                "from": "delegations",
                "let": { "user": "$_id" },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$Delegatee_id", "$$user"]},
                                    {"$eq": ["$Status", "Active"]},
                                    {"$lte": ["$Start_time", "$$NOW"]},
                                    {"$lt": ["$$NOW", "$End_time"]}
                                ]
                            }
                        }
                    }
                ],
                "as": "Active_Delegations"
            }
        },
        # Combine user's Assigned_Roles and Target_Role_id from Active_Delegations
        {
            "$project": {
                "combined_roles": {
                    "$setUnion": [
                        {"$map": {
                            "input": "$Assigned_Roles",
                            "as": "r",
                            "in": {
                                "$cond": {
                                    "if": {"$eq": [{"$type": "$$r"}, "object"]},
                                    "then": "$$r.role_id",
                                    "else": "$$r"
                                }
                            }
                        }},
                        {"$map": {"input": "$Active_Delegations", "as": "d", "in": "$$d.Target_Role_id"}}
                    ]
                }
            }
        },
        # 3. Use $lookup for direct role docs (using combined_roles)
        {
            "$lookup": {
                "from": "roles",
                "localField": "combined_roles",
                "foreignField": "_id",
                "as": "Direct_Roles"
            }
        },
        # 4. Use $graphLookup to fetch parent inherited roles recursively
        # The 'roles' collection holds documents where Parent_Role_id points to another role's _id
        {
            "$graphLookup": {
                "from": "roles",
                "startWith": "$Direct_Roles.Parent_Role_id",
                "connectFromField": "Parent_Role_id",
                "connectToField": "_id",
                "as": "Inherited_Roles",
                "depthField": "depth",
                "maxDepth": 10
            }
        },
        # 5. Merge direct + inherited role docs and flatten permission ids with deduping
        {
            "$project": {
                "All_Roles": {"$concatArrays": ["$Direct_Roles", "$Inherited_Roles"]}
            }
        },
        {
            "$project": {
                "Permission_Ids": {
                    "$reduce": {
                        "input": "$All_Roles.Permissions",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", {"$ifNull": ["$$this", []]}]}
                    }
                }
            }
        },
        # 6. Resolve actual permission documents using standard $lookup against permissions
        {
            "$lookup": {
                "from": "permissions",
                "localField": "Permission_Ids",
                "foreignField": "_id",
                "as": "Permission_Docs"
            }
        },
        # 7. Keep a clean list of permission names
        {
            "$project": {
                "_id": 0,
                "Effective_Permissions": {
                    "$setUnion": [{"$ifNull": ["$Permission_Docs.Permission_name", []]}, []]
                }
            }
        }
    ]

    result = list(db.users.aggregate(pipeline))
    
    # If the user has no roles or no permissions, the result might be empty
    if not result:
        return []
    
    # Return the clean list of permission strings (e.g., ["READ_PATIENT_DATA", "EDIT_PATIENT_DATA"])
    return result[0].get("Effective_Permissions", [])


def get_active_roles(user_id, db):
    """
    Returns a list of all role names (direct + inherited) for a user.
    Useful for checking hierarchy (e.g. is this user a 'Lead Doctor'?)
    """
    if db is None:
        return []

    # Ensure user_id is an ObjectId
    if isinstance(user_id, str):
        try:
            user_id = ObjectId(user_id)
        except InvalidId:
            return []
    elif not isinstance(user_id, ObjectId):
        return []

    from datetime import datetime
    now = datetime.utcnow()

    pipeline = [
        # 1. Match the specific User
        {
            "$match": { "_id": user_id }
        },
        # 2. Normalize Assigned_Roles
        {
            "$project": {
                "Assigned_Roles": {"$ifNull": ["$Assigned_Roles", []]}
            }
        },
        # 2.5. Fetch active Delegations
        {
            "$lookup": {
                "from": "delegations",
                "let": { "user": "$_id" },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$Delegatee_id", "$$user"]},
                                    {"$eq": ["$Status", "Active"]},
                                    {"$lte": ["$Start_time", "$$NOW"]},
                                    {"$lt": ["$$NOW", "$End_time"]}
                                ]
                            }
                        }
                    }
                ],
                "as": "Active_Delegations"
            }
        },
        # Combine
        {
            "$project": {
                "combined_roles": {
                    "$setUnion": [
                        {"$map": {
                            "input": "$Assigned_Roles",
                            "as": "r",
                            "in": {
                                "$cond": {
                                    "if": {"$eq": [{"$type": "$$r"}, "object"]},
                                    "then": "$$r.role_id",
                                    "else": "$$r"
                                }
                            }
                        }},
                        {"$map": {"input": "$Active_Delegations", "as": "d", "in": "$$d.Target_Role_id"}}
                    ]
                }
            }
        },
        # 3. Lookup direct roles
        {
            "$lookup": {
                "from": "roles",
                "localField": "combined_roles",
                "foreignField": "_id",
                "as": "Direct_Roles"
            }
        },
        # 4. GraphLookup inherited roles
        {
            "$graphLookup": {
                "from": "roles",
                "startWith": "$Direct_Roles.Parent_Role_id",
                "connectFromField": "Parent_Role_id",
                "connectToField": "_id",
                "as": "Inherited_Roles",
                "depthField": "depth",
                "maxDepth": 10
            }
        },
        # 5. Project all role names
        {
            "$project": {
                "All_Role_Names": {
                    "$setUnion": [
                        "$Direct_Roles.Role_name",
                        "$Inherited_Roles.Role_name"
                    ]
                }
            }
        }
    ]

    result = list(db.users.aggregate(pipeline))
    if not result:
        return []
    
    return result[0].get("All_Role_Names", [])
