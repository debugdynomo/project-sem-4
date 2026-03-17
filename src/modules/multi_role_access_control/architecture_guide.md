# Step 1: MongoDB Schema & NoSQL Optimization

## JSON Document Structures

### `users` Collection
**Purpose:** Stores user authentication details and assigned roles. Optimization: `assigned_roles` is an embedded array of ObjectIds referencing the `roles` collection for M:N relationships.
```json
{
  "_id": ObjectId("65e4a3b8..."),
  "username": "dr_smith",
  "password_hash": "$2b$12$eImiTXuWv...",
  "email": "smith@hospital.org",
  "status": "Active",
  "assigned_roles": [
    ObjectId("65e4b1c2...") // Direct Role (e.g., Lead Doctor)
  ]
}
```

### `roles` Collection
**Purpose:** Defines roles, hierarchical inheritance, and M:N relationships to permissions.
```json
{
  "_id": ObjectId("65e4b1c2..."),
  "role_name": "Lead Doctor",
  "description": "Supervisor of the cardiology ward",
  "level": 3,
  "parent_role_id": ObjectId("65e4b1a1..."), // Inherits from "Doctor" role
  "permissions": [
    ObjectId("65e4c5d3..."), // e.g., "approve_leave"
    ObjectId("65e4c5d4...")  // e.g., "override_prescription"
  ]
}
```

### `permissions` Collection
**Purpose:** A flat list of specific access granularities.
```json
{
  "_id": ObjectId("65e4c5d3..."),
  "permission_name": "approve_leave",
  "description": "Can approve subordinate time off requests."
}
```

### `audit_logs` Collection
**Purpose:** An immutable ledger of actions taken by users or triggered automatically.
```json
{
  "_id": ObjectId("65e4d8ef..."),
  "user_id": ObjectId("65e4a3b8..."), // The user who performed the action
  "action": "GRANT_ROLE",
  "target_entity": ObjectId("65e4e9f0..."), // e.g., the user they granted a role to
  "timestamp": ISODate("2026-03-17T12:00:00Z"),
  "ip_address": "192.168.1.50",
  "status": "Success",
  "details": {
    "granted_role_id": "65e4b1c2..."
  }
}
```

---

# Step 3: Secure Audit Logging (DB-Level via Atlas Triggers)

To guarantee database integrity regardless of what application inserts or updates the database, use MongoDB Atlas Database Triggers. 

## Trigger Configuration (JSON)
Use this configuration in the Atlas UI or via the Atlas Admin API to set up the trigger.

```json
{
    "name": "Audit_Role_Assignments_Trigger",
    "type": "DATABASE",
    "config": {
        "operation_types": ["UPDATE"],
        "database": "CDSS_G41",
        "collection": "users",
        "full_document": true,
        "full_document_before_change": true,
        "match": {
            // Only fire the trigger if the 'assigned_roles' array was modified.
            "updateDescription.updatedFields.assigned_roles": { "$exists": true }
        }
    },
    "function_name": "logRoleAssignmentChanged",
    "disabled": false
}
```

## JavaScript Function (`logRoleAssignmentChanged`)
This is the serverless JavaScript function that executes inside MongoDB Atlas when the trigger fires.

```javascript
exports = function(changeEvent) {
    // Access the targeted collection
    const auditLogsCollection = context.services.get("mongodb-atlas").db("CDSS_G41").collection("audit_logs");
    
    // Extract metadata from the Database Event
    const targetUserId = changeEvent.documentKey._id;
    const oldRoles = changeEvent.fullDocumentBeforeChange ? changeEvent.fullDocumentBeforeChange.assigned_roles : [];
    const newRoles = changeEvent.fullDocument ? changeEvent.fullDocument.assigned_roles : [];
    
    // Safety check: sometimes the 'assigned_roles' field might be modified without changing its value 
    // (though uncommon if 'match' is configured properly).
    // A robust trigger calculates the difference to determine if a role was added or removed.
    const addedRoles = newRoles.filter(role => !oldRoles.includes(role));
    const removedRoles = oldRoles.filter(role => !newRoles.includes(role));
    
    if (addedRoles.length === 0 && removedRoles.length === 0) {
        return; // No real change happened
    }

    // Construct the un-forgeable audit log entry directly at the database level
    const auditDoc = {
        action: "DB_TRIGGER_ROLE_MODIFICATION",
        target_entity: targetUserId, // The user whose roles changed
        timestamp: new Date(),
        status: "Success",
        details: {
            roles_added: addedRoles,
            roles_removed: removedRoles,
            event_id: changeEvent._id,   // Correlate with Atlas logs if needed
            trigger_name: context.environment.values.triggerName // Optional: if provided in variables
        }
    };
    
    // IMPORTANT: DB Triggers cannot reliably capture the 'ip_address' or the 'user_id' 
    // of the person who executed the query. It only captures that a change occurred.
    // For who executed the change, rely on the App-Level `@audit_action` decorator 
    // constructed in `audit_logger.py`, and correlate by timestamp or target_entity.

    // Insert the log
    return auditLogsCollection.insertOne(auditDoc)
        .then(result => console.log(`Successfully logged role modification for User ${targetUserId}. Log ID: ${result.insertedId}`))
        .catch(err => console.error(`Failed to log role modification: ${err}`));
};
```
