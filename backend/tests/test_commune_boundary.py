import unittest
from app.services.commune_boundary import resolve_commune_from_coordinates

class CommuneBoundaryTests(unittest.TestCase):
    def test_point_inside_sin_thau_maps(self): self.assertEqual(resolve_commune_from_coordinates(22.3958973,102.274572).code,"sin_thau")
    def test_outside_polygon_is_unmapped(self): self.assertIsNone(resolve_commune_from_coordinates(0,0))
    def test_invalid_latitude_is_rejected(self):
        with self.assertRaises(ValueError): resolve_commune_from_coordinates(91,102)
    def test_lat_lon_are_not_reversed(self):
        with self.assertRaises(ValueError): resolve_commune_from_coordinates(102.274572,22.3958973)
