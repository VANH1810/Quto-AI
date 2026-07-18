"""Point-in-polygon commune resolver backed by the checked-in administrative GeoJSON.

Coordinates are always (latitude, longitude) at the API boundary and converted
to GeoJSON's (longitude, latitude) only inside this module.
"""
from __future__ import annotations
import json
from pathlib import Path
from app.services.geo_data import all_communes

_GEOJSON = Path(__file__).resolve().parents[3] / "frontend" / "public" / "data" / "dien-bien-communes.geojson"

def _on_segment(x: float, y: float, a: list[float], b: list[float]) -> bool:
    cross = (x-a[0])*(b[1]-a[1]) - (y-a[1])*(b[0]-a[0])
    return abs(cross) < 1e-9 and min(a[0],b[0])-1e-9 <= x <= max(a[0],b[0])+1e-9 and min(a[1],b[1])-1e-9 <= y <= max(a[1],b[1])+1e-9
def _covers_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside=False
    for i,a in enumerate(ring):
        b=ring[(i+1)%len(ring)]
        if _on_segment(x,y,a,b): return True
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: inside=not inside
    return inside
def _covers_geometry(x: float,y: float,geometry: dict) -> bool:
    polygons = [geometry["coordinates"]] if geometry["type"]=="Polygon" else geometry["coordinates"]
    return any(poly and _covers_ring(x,y,poly[0]) and not any(_covers_ring(x,y,hole) for hole in poly[1:]) for poly in polygons)
def resolve_commune_from_coordinates(latitude: float, longitude: float):
    if not -90 <= latitude <= 90: raise ValueError("latitude phải nằm trong khoảng -90 đến 90")
    if not -180 <= longitude <= 180: raise ValueError("longitude phải nằm trong khoảng -180 đến 180")
    if not _GEOJSON.exists(): return None
    by_name={commune.name:commune for commune in all_communes()}
    for feature in json.loads(_GEOJSON.read_text(encoding="utf-8"))["features"]:
        if _covers_geometry(longitude, latitude, feature["geometry"]):
            return by_name.get(feature["properties"].get("name"))
    return None
