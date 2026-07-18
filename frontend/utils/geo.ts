import type { Feature, MultiPolygon, Polygon, Position } from "geojson";
import type { CommuneProperties, Coordinates } from "@/types";

export function haversineKm(from: Coordinates, to: Coordinates): number {
  const radius = 6371;
  const radians = (value: number) => (value * Math.PI) / 180;
  const dLat = radians(to.lat - from.lat);
  const dLon = radians(to.lon - from.lon);
  const lat1 = radians(from.lat);
  const lat2 = radians(to.lat);
  const a = Math.sin(dLat / 2) ** 2 + Math.sin(dLon / 2) ** 2 * Math.cos(lat1) * Math.cos(lat2);
  return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

type PolygonCoordinates = Polygon["coordinates"];

function pointOnSegment(longitude: number, latitude: number, start: Position, end: Position) {
  const cross = (latitude - start[1]) * (end[0] - start[0]) - (longitude - start[0]) * (end[1] - start[1]);
  if (Math.abs(cross) > 1e-10) return false;

  const dot = (longitude - start[0]) * (end[0] - start[0]) + (latitude - start[1]) * (end[1] - start[1]);
  if (dot < 0) return false;

  const squaredLength = (end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2;
  return dot <= squaredLength;
}

function pointInRing(longitude: number, latitude: number, ring: Position[]) {
  let inside = false;

  for (let current = 0, previous = ring.length - 1; current < ring.length; previous = current++) {
    const start = ring[previous];
    const end = ring[current];
    if (pointOnSegment(longitude, latitude, start, end)) return { inside: true, boundary: true };

    if (
      (start[1] > latitude) !== (end[1] > latitude)
      && longitude < ((end[0] - start[0]) * (latitude - start[1])) / (end[1] - start[1]) + start[0]
    ) {
      inside = !inside;
    }
  }

  return { inside, boundary: false };
}

function pointInPolygon(coordinates: Coordinates, rings: PolygonCoordinates) {
  const outer = pointInRing(coordinates.lon, coordinates.lat, rings[0]);
  if (!outer.inside) return false;

  for (const hole of rings.slice(1)) {
    const result = pointInRing(coordinates.lon, coordinates.lat, hole);
    if (result.inside) return false;
  }

  return true;
}

/** Returns true when a coordinate lies inside the commune polygon or on its outer boundary. */
export function featureContainsCoordinates(
  feature: Feature<Polygon | MultiPolygon, CommuneProperties>,
  coordinates: Coordinates,
) {
  const polygons = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
  return polygons.some((rings) => pointInPolygon(coordinates, rings));
}

interface InternalPoint {
  x: number;
  y: number;
  distance: number;
}

function squaredSegmentDistance(x: number, y: number, start: Position, end: Position) {
  const segmentX = end[0] - start[0];
  const segmentY = end[1] - start[1];
  let pointX = x - start[0];
  let pointY = y - start[1];
  const segmentLength = segmentX * segmentX + segmentY * segmentY;

  if (segmentLength > 0) {
    const projection = Math.min(1, Math.max(0, (pointX * segmentX + pointY * segmentY) / segmentLength));
    pointX = x - (start[0] + segmentX * projection);
    pointY = y - (start[1] + segmentY * projection);
  }

  return pointX * pointX + pointY * pointY;
}

function signedDistanceToPolygon(x: number, y: number, rings: PolygonCoordinates) {
  let inside = false;
  let minimumSquaredDistance = Number.POSITIVE_INFINITY;

  for (const ring of rings) {
    for (let current = 0, previous = ring.length - 1; current < ring.length; previous = current++) {
      const start = ring[current];
      const end = ring[previous];
      if ((start[1] > y) !== (end[1] > y) && x < ((end[0] - start[0]) * (y - start[1])) / (end[1] - start[1]) + start[0]) {
        inside = !inside;
      }
      minimumSquaredDistance = Math.min(minimumSquaredDistance, squaredSegmentDistance(x, y, start, end));
    }
  }

  const distance = Math.sqrt(minimumSquaredDistance);
  return inside ? distance : -distance;
}

function areaCentroid(ring: Position[]): [number, number] {
  let areaTwice = 0;
  let longitude = 0;
  let latitude = 0;

  for (let current = 0, previous = ring.length - 1; current < ring.length; previous = current++) {
    const start = ring[previous];
    const end = ring[current];
    const cross = start[0] * end[1] - end[0] * start[1];
    areaTwice += cross;
    longitude += (start[0] + end[0]) * cross;
    latitude += (start[1] + end[1]) * cross;
  }

  if (Math.abs(areaTwice) < Number.EPSILON) return [ring[0][0], ring[0][1]];
  return [longitude / (3 * areaTwice), latitude / (3 * areaTwice)];
}

class Cell {
  readonly distance: number;
  readonly maximum: number;

  constructor(readonly x: number, readonly y: number, readonly halfSize: number, rings: PolygonCoordinates) {
    this.distance = signedDistanceToPolygon(x, y, rings);
    this.maximum = this.distance + this.halfSize * Math.SQRT2;
  }
}

class CellQueue {
  private cells: Cell[] = [];

  get size() {
    return this.cells.length;
  }

  push(cell: Cell) {
    this.cells.push(cell);
    let index = this.cells.length - 1;
    while (index > 0) {
      const parent = Math.floor((index - 1) / 2);
      if (this.cells[parent].maximum >= cell.maximum) break;
      this.cells[index] = this.cells[parent];
      index = parent;
    }
    this.cells[index] = cell;
  }

  pop() {
    const first = this.cells[0];
    const last = this.cells.pop();
    if (!last || this.cells.length === 0) return first;

    let index = 0;
    this.cells[0] = last;
    while (true) {
      const left = index * 2 + 1;
      const right = left + 1;
      let largest = index;
      if (left < this.cells.length && this.cells[left].maximum > this.cells[largest].maximum) largest = left;
      if (right < this.cells.length && this.cells[right].maximum > this.cells[largest].maximum) largest = right;
      if (largest === index) break;
      [this.cells[index], this.cells[largest]] = [this.cells[largest], this.cells[index]];
      index = largest;
    }
    return first;
  }
}

function pointInsidePolygon(rings: PolygonCoordinates): InternalPoint {
  const outerRing = rings[0];
  const longitudes = outerRing.map((point) => point[0]);
  const latitudes = outerRing.map((point) => point[1]);
  const west = Math.min(...longitudes);
  const east = Math.max(...longitudes);
  const south = Math.min(...latitudes);
  const north = Math.max(...latitudes);
  const width = east - west;
  const height = north - south;
  const cellSize = Math.min(width, height);

  const centroid = areaCentroid(outerRing);
  let best = new Cell(centroid[0], centroid[1], 0, rings);
  const boundsCenter = new Cell((west + east) / 2, (south + north) / 2, 0, rings);
  if (boundsCenter.distance > best.distance) best = boundsCenter;

  if (cellSize === 0) return { x: best.x, y: best.y, distance: best.distance };

  const queue = new CellQueue();
  const halfSize = cellSize / 2;
  for (let x = west; x < east; x += cellSize) {
    for (let y = south; y < north; y += cellSize) {
      queue.push(new Cell(x + halfSize, y + halfSize, halfSize, rings));
    }
  }

  const precision = Math.max(cellSize / 200, 0.00001);
  while (queue.size > 0) {
    const cell = queue.pop();
    if (!cell) break;
    if (cell.distance > best.distance) best = cell;
    if (cell.maximum - best.distance <= precision) continue;

    const nextHalfSize = cell.halfSize / 2;
    queue.push(new Cell(cell.x - nextHalfSize, cell.y - nextHalfSize, nextHalfSize, rings));
    queue.push(new Cell(cell.x + nextHalfSize, cell.y - nextHalfSize, nextHalfSize, rings));
    queue.push(new Cell(cell.x - nextHalfSize, cell.y + nextHalfSize, nextHalfSize, rings));
    queue.push(new Cell(cell.x + nextHalfSize, cell.y + nextHalfSize, nextHalfSize, rings));
  }

  return { x: best.x, y: best.y, distance: best.distance };
}

export function representativePointFromFeature(
  feature: Feature<Polygon | MultiPolygon, CommuneProperties>,
): Coordinates {
  const polygons = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
  const representative = polygons
    .map(pointInsidePolygon)
    .sort((first, second) => second.distance - first.distance)[0];

  return { lat: representative.y, lon: representative.x };
}

/**
 * Produces deterministic, separated points that stay inside a commune polygon.
 * `avoid` is used to keep generated fallback points away from sourced shelters.
 */
export function dispersedRepresentativePointsFromFeature(
  feature: Feature<Polygon | MultiPolygon, CommuneProperties>,
  count: number,
  avoid: Coordinates[] = [],
): Coordinates[] {
  if (count <= 0) return [];

  const polygons = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
  const candidates: Array<Coordinates & { clearance: number }> = [];

  for (const rings of polygons) {
    const outerRing = rings[0];
    const longitudes = outerRing.map((point) => point[0]);
    const latitudes = outerRing.map((point) => point[1]);
    const west = Math.min(...longitudes);
    const east = Math.max(...longitudes);
    const south = Math.min(...latitudes);
    const north = Math.max(...latitudes);
    const columns = 12;
    const rows = 12;

    const representative = pointInsidePolygon(rings);
    candidates.push({ lat: representative.y, lon: representative.x, clearance: representative.distance });

    for (let column = 0; column < columns; column += 1) {
      for (let row = 0; row < rows; row += 1) {
        const lon = west + ((column + 0.5) / columns) * (east - west);
        const lat = south + ((row + 0.5) / rows) * (north - south);
        const clearance = signedDistanceToPolygon(lon, lat, rings);
        if (clearance > 0) candidates.push({ lat, lon, clearance });
      }
    }
  }

  const selected: Coordinates[] = [];
  while (selected.length < count && candidates.length > 0) {
    const references = [...avoid, ...selected];
    let bestIndex = 0;
    let bestScore = Number.NEGATIVE_INFINITY;

    for (let index = 0; index < candidates.length; index += 1) {
      const candidate = candidates[index];
      const separation = references.length
        ? Math.min(...references.map((point) => haversineKm(point, candidate)))
        : candidate.clearance * 100;
      const score = separation + candidate.clearance * 4;
      if (score > bestScore) {
        bestScore = score;
        bestIndex = index;
      }
    }

    const [chosen] = candidates.splice(bestIndex, 1);
    selected.push({ lat: Number(chosen.lat.toFixed(6)), lon: Number(chosen.lon.toFixed(6)) });
  }

  return selected;
}
