exports = async function (changeEvent) {
  const serviceName = "atlas_service";
  const databaseName = "CDSS_G41";
  const auditCollectionName = "audit_logs";

  const db = context.services.get(serviceName).db(databaseName);
  const auditLogs = db.collection(auditCollectionName);

  const namespace = changeEvent.ns || {};
  const operationType = changeEvent.operationType;
  const docKey = changeEvent.documentKey || {};
  const fullDoc = changeEvent.fullDocument || null;

  const collection = namespace.coll;
  if (!["users", "roles"].includes(collection)) {
    return;
  }

  const now = new Date();

  const auditDoc = {
    User_id: null,
    Action: `DB_${operationType.toUpperCase()}_${collection.toUpperCase()}`,
    Target_Entity: collection,
    Timestamp: now,
    IP_Address: "atlas-trigger",
    Status: "SUCCESS",
    Details: {
      operationType,
      documentId: docKey._id || null,
      updatedFields: changeEvent.updateDescription
        ? changeEvent.updateDescription.updatedFields
        : null,
      removedFields: changeEvent.updateDescription
        ? changeEvent.updateDescription.removedFields
        : null,
      source: "atlas_db_trigger",
      snapshot: fullDoc,
    },
  };

  await auditLogs.insertOne(auditDoc);
};

