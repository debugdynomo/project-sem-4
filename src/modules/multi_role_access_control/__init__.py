# Re-export canonical backend functions only.
# Dead legacy files (rbac_core, audit_logger, core_schema) have been removed.
# New functions (evaluate_access, get_role_permissions, get_upcoming_expirations)
# will be added in a later commit once they are implemented.

from .schema import init_delegations_collection
from .auth_service import login_user
from .admin_service import assign_role_to_user, revoke_role_from_user

__all__ = [
    "init_delegations_collection",
    "login_user",
    "assign_role_to_user",
    "revoke_role_from_user",
]
