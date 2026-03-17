from functools import wraps
from datetime import datetime

def audit_action(action_name: str):
    """
    Python decorator that automatically logs a function call to the audit_logs collection.
    Requires that the decorated function returns a dictionary containing 
    'user_id' and 'target_entity', or accepts them as kwargs.
    Expects the first argument of the decorated function to be the 'db' connection.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(db, *args, **kwargs):
            # 1. Execute the actual function
            try:
                result = func(db, *args, **kwargs)
                status = "Success"
            except Exception as e:
                result = {"error": str(e)}
                status = "Failed"
                raise e # Re-raise after logging
            finally:
                # 2. Extract context for logging
                user_id = kwargs.get('user_id') or (result.get('user_id') if isinstance(result, dict) else None)
                target_entity = kwargs.get('target_entity') or (result.get('target_entity') if isinstance(result, dict) else None)
                ip_address = kwargs.get('ip_address', '127.0.0.1')
                
                # 3. Construct and insert the Audit Log document
                audit_doc = {
                    "user_id": user_id,
                    "action": action_name,
                    "target_entity": target_entity,
                    "timestamp": datetime.utcnow(),
                    "ip_address": ip_address,
                    "status": status,
                    "details": result if isinstance(result, dict) else str(result)
                }
                
                # Insert asynchronously if possible in a real app, but synchronous here
                db["audit_logs"].insert_one(audit_doc)
                
            return result
        return wrapper
    return decorator
