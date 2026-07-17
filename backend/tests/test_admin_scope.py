"""Regression tests for server-side admin commune scope (stdlib unittest)."""

from __future__ import annotations

import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.schemas.admin import AdminCreate, AdminRole
from app.services.admin_scope import commune_codes_for, require_commune_access
from app.services.admins import admins
from app.security import create_access_token, get_current_admin


class AdminScopeUnitTests(unittest.TestCase):
    def _admin(self, communes: list[str]):
        record = admins.create(AdminCreate(email=f"scope-{len(admins.all())}@example.test", password="123456",
                                           full_name="Cán bộ test", age=30, phone="0900000000",
                                           role=AdminRole.commune, communes=communes), mirror=False)
        return admins.to_public(record)

    def test_admin_with_one_commune(self):
        self.assertEqual(commune_codes_for(self._admin(["sin_thau"])), ("sin_thau",))

    def test_admin_with_many_communes_deduplicates_association(self):
        self.assertEqual(commune_codes_for(self._admin(["sin_thau", "nam_ke", "sin_thau", " "])),
                         ("sin_thau", "nam_ke"))

    def test_admin_with_no_communes_has_empty_scope(self):
        self.assertEqual(commune_codes_for(self._admin([])), ())

    def test_out_of_scope_commune_is_forbidden(self):
        with self.assertRaises(HTTPException) as context:
            require_commune_access(self._admin(["sin_thau"]), "nam_ke")
        self.assertEqual(context.exception.status_code, 403)

    def test_token_for_a_user_that_is_not_an_admin_is_rejected(self):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_access_token("citizen@example.test"))
        with self.assertRaises(HTTPException) as context:
            get_current_admin(credentials)
        self.assertEqual(context.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
