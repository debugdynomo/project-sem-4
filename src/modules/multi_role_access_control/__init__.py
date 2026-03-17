# Re-export canonical backend functions only.
# Dead legacy files (rbac_core, audit_logger, core_schema) have been removed.

from .schema import init_delegations_collection
from .delegations import create_delegation, get_role_permissions, evaluate_access
from .auth_service import login_user
from .admin_service import assign_role_to_user, revoke_role_from_user, get_upcoming_expirations

__all__ = [
    "init_delegations_collection",
    "create_delegation",
    "get_role_permissions",
    "evaluate_access",
    "login_user",
    "assign_role_to_user",
    "revoke_role_from_user",
    "get_upcoming_expirations",
]
