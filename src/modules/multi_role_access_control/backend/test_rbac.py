import unittest
from backend.rbac import get_effective_permissions
from backend.database import get_db_connection

class TestRBAC(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """
        Connect to DB and optionally seed it.
        Because PyMongo interacts directly with Atlas, we assume `seed_db.py`
        has been run independently or we run it here.
        """
        cls.db = get_db_connection()
        print("Test Suite Initialized connected to", cls.db.name)

    def test_admin_permissions(self):
        # In a real test, dynamically query the admin user we seeded
        admin_user = self.db.users.find_one({"Username": "admin_alice"})
        if admin_user:
            perms = get_effective_permissions(admin_user["_id"], self.db)
            
            # Admin inherits EVERYTHING from Lead_Doctor -> Doctor -> Patient (plus direct Admin perms)
            # The exact count depends on the seeding script
            self.assertIn("DELETE_PATIENT_DATA", perms)
            self.assertIn("APPROVE_DELEGATION", perms)
            self.assertIn("READ_PATIENT_DATA", perms)
            print(f"Admin Permissions: {perms}")

    def test_doctor_permissions(self):
        doctor_user = self.db.users.find_one({"Username": "dr_bob"})
        if doctor_user:
            perms = get_effective_permissions(doctor_user["_id"], self.db)
            
            # Doctor should NOT have admin permissions or APPROVE_DELEGATION
            self.assertNotIn("DELETE_PATIENT_DATA", perms)
            self.assertNotIn("APPROVE_DELEGATION", perms)
            
            # But should have EDIT and READ
            self.assertIn("EDIT_PATIENT_DATA", perms)
            self.assertIn("READ_PATIENT_DATA", perms)
            print(f"Doctor Permissions: {perms}")

    def test_invalid_user(self):
        """Ensure safe failure for a non-existent user."""
        from bson import ObjectId
        fake_id = ObjectId()
        perms = get_effective_permissions(fake_id, self.db)
        self.assertEqual(len(perms), 0)
        self.assertIsInstance(perms, list)

    def test_malformed_user_id(self):
        """Malformed ObjectId strings should not crash aggregation."""
        perms = get_effective_permissions("not-an-object-id", self.db)
        self.assertEqual(perms, [])

if __name__ == '__main__':
    unittest.main()
