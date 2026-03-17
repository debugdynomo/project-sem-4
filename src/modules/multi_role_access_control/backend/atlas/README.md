# Atlas Trigger Assets (G41)

These files define DB-level audit logging independent of the Python backend.

## Files

- `triggers/g41_audit_trigger.js`: trigger function body
- `triggers/g41_audit_trigger.config.json`: trigger configuration template

## How to use

1. In MongoDB Atlas App Services, create a new **Database Trigger**.
2. Use values from `triggers/g41_audit_trigger.config.json`.
3. Paste `triggers/g41_audit_trigger.js` in the trigger function editor.
4. Set your cluster/service names (`atlas_service`, database name, etc.).
5. Enable the trigger.

The trigger listens to `insert` and `update` events on `users` and `roles` and writes independent audit entries into `audit_logs`.

