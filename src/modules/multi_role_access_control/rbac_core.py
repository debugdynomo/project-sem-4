def get_effective_permissions(db, user_id: str) -> list:
    """
    Retrieves a flattened, deduplicated list of all effective permissions for a user.
    Uses MongoDB's $graphLookup for recursive role hierarchy resolution to prevent
    infinite loops via maxDepth.
    """
    from bson.objectid import ObjectId
    
    pipeline = [
        # 1. Match the specific user
        {
            "$match": {
                "_id": ObjectId(user_id) if isinstance(user_id, str) else user_id
            }
        },
        # 2. Lookup direct roles to get the Initial Role Documents
        {
            "$lookup": {
                "from": "roles",
                "localField": "assigned_roles",
                "foreignField": "_id",
                "as": "direct_roles"
            }
        },
        # 3. Use $graphLookup on roles to recursively fetch parent/inherited roles
        {
            "$graphLookup": {
                "from": "roles",
                "startWith": "$direct_roles.parent_role_id",
                "connectFromField": "parent_role_id",
                "connectToField": "_id",
                "as": "inherited_roles",
                "maxDepth": 10  # Prevent infinite loops from circular dependencies
            }
        },
        # 4. Combine direct roles and inherited roles using $setUnion
        {
            "$project": {
                "all_roles": {
                    "$setUnion": ["$direct_roles", "$inherited_roles"]
                }
            }
        },
        # 5. Extract just the permission IDs from all roles
        {
            "$project": {
                "all_permission_ids": {
                    "$reduce": {
                        "input": "$all_roles",
                        "initialValue": [],
                        "in": { "$setUnion": ["$$value", "$$this.permissions"] }
                    }
                }
            }
        },
        # 6. Perform standard $lookup to resolve Permission IDs to true strings
        {
            "$lookup": {
                "from": "permissions",
                "localField": "all_permission_ids",
                "foreignField": "_id",
                "as": "resolved_permissions"
            }
        },
        # 7. Final Projection: Array of permission_name strings
        {
            "$project": {
                "effective_permissions": "$resolved_permissions.permission_name"
            }
        }
    ]
    
    # Execute Aggregation
    cursor = db["users"].aggregate(pipeline)
    result = list(cursor)
    
    if result and "effective_permissions" in result[0]:
        return result[0]["effective_permissions"]
        
    return []
