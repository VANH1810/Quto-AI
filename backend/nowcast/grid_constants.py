LAT0: float = 22.58
LON0: float = 102.12
DLAT: float = 0.04
DLON: float = 0.04
GRID_SHAPE: tuple[int, int] = (40, 38)

_LAT_LAST = LAT0 - (GRID_SHAPE[0] - 1) * DLAT
_LON_LAST = LON0 + (GRID_SHAPE[1] - 1) * DLON
assert _LAT_LAST < LAT0, "row 0 must be the northernmost row"
assert 21.0 <= _LAT_LAST < LAT0 <= 22.6, "latitude window must stay inside Dien Bien"
assert 102.1 <= LON0 < _LON_LAST <= 103.62, "longitude window must stay inside Dien Bien"
