"""
permission_matrix.py — Persisted Role × Permission matrix with snapshots and diff.

Stores matrix snapshots in a `permission_matrix` collection for auditing
permission drift over time.
"""
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
    except Exception:
        return val


def _resolve_inherited_permissions(role_doc, all_roles_map):
    """
    Walk the Parent_Role_id chain and collect all permission IDs (direct + inherited).
    Returns (set_of_perm_ids, list_of_inheritance_sources).
    """
    perm_ids = set()
    sources = {}  # perm_id -> source_role_name
    visited = set()

    current = role_doc
    while current and str(current["_id"]) not in visited:
        visited.add(str(current["_id"]))
        for pid in current.get("Permissions", []):
            if str(pid) not in sources:
                sources[str(pid)] = current.get("Role_name", "Unknown")
            perm_ids.add(pid)
        parent_id = current.get("Parent_Role_id")
        if parent_id:
            current = all_roles_map.get(str(parent_id))
        else:
            current = None

    return perm_ids, sources


@audit_action(action="BUILD_PERMISSION_MATRIX", target_entity="permission_matrix")
def build_permission_matrix(db, admin_id: str = None) -> str:
    """
    Generates the full Role × Permission matrix with inheritance resolution
    and stores it as a snapshot document in the `permission_matrix` collection.

    Returns the inserted snapshot ID.
    """
    roles = list(db["roles"].find({}))
    permissions = list(db["permissions"].find({}))

    all_roles_map = {str(r["_id"]): r for r in roles}
    perm_name_map = {str(p["_id"]): p.get("Permission_name", str(p["_id"])) for p in permissions}

    matrix = []
    for role in roles:
        perm_ids, sources = _resolve_inherited_permissions(role, all_roles_map)

        row = {
            "role_name": role.get("Role_name", "Unknown"),
            "role_id": str(role["_id"]),
            "level": role.get("Level", 99),
            "permissions": {}
        }

        for p in permissions:
            pid_str = str(p["_id"])
            perm_name = p.get("Permission_name", pid_str)
            has_perm = p["_id"] in perm_ids

            row["permissions"][perm_name] = {
                "granted": has_perm,
                "source": sources.get(pid_str, None) if has_perm else None,
                "direct": has_perm and sources.get(pid_str) == role.get("Role_name"),
                "inherited": has_perm and sources.get(pid_str) != role.get("Role_name")
            }

        matrix.append(row)

    snapshot = {
        "timestamp": datetime.utcnow(),
        "created_by": safe_objectid(admin_id) if admin_id else None,
        "role_count": len(roles),
        "permission_count": len(permissions),
        "matrix": matrix
    }

    result = db["permission_matrix"].insert_one(snapshot)
    return str(result.inserted_id)


def get_latest_matrix(db) -> dict:
    """Retrieves the most recent permission matrix snapshot."""
    snapshot = db["permission_matrix"].find_one(
        sort=[("timestamp", -1)]
    )
    return snapshot


def get_matrix_history(db, limit: int = 10) -> list:
    """Returns recent matrix snapshots (metadata only, no full matrix)."""
    return list(db["permission_matrix"].find(
        {},
        {"matrix": 0}  # exclude the heavy matrix field
    ).sort("timestamp", -1).limit(limit))


def compare_matrices(db, matrix_id_1: str, matrix_id_2: str) -> dict:
    """
    Diff two matrix snapshots to detect permission drift.
    Returns a dict with added, removed, and changed entries.
    """
    m1 = db["permission_matrix"].find_one({"_id": safe_objectid(matrix_id_1)})
    m2 = db["permission_matrix"].find_one({"_id": safe_objectid(matrix_id_2)})

    if not m1 or not m2:
        return {"error": "One or both matrix snapshots not found."}

    # Build lookup: role_name -> {perm_name -> granted}
    def _flatten(matrix_doc):
        flat = {}
        for row in matrix_doc.get("matrix", []):
            role = row.get("role_name")
            flat[role] = {}
            for perm_name, info in row.get("permissions", {}).items():
                flat[role][perm_name] = info.get("granted", False)
        return flat

    flat1 = _flatten(m1)
    flat2 = _flatten(m2)

    all_roles = set(list(flat1.keys()) + list(flat2.keys()))
    all_perms = set()
    for perms in list(flat1.values()) + list(flat2.values()):
        all_perms.update(perms.keys())

    changes = []
    for role in sorted(all_roles):
        for perm in sorted(all_perms):
            old_val = flat1.get(role, {}).get(perm, False)
            new_val = flat2.get(role, {}).get(perm, False)
            if old_val != new_val:
                changes.append({
                    "role": role,
                    "permission": perm,
                    "old": "✅" if old_val else "❌",
                    "new": "✅" if new_val else "❌",
                    "change": "GRANTED" if new_val else "REVOKED"
                })

    return {
        "snapshot_1": {"id": matrix_id_1, "timestamp": m1.get("timestamp")},
        "snapshot_2": {"id": matrix_id_2, "timestamp": m2.get("timestamp")},
        "total_changes": len(changes),
        "changes": changes
    }
