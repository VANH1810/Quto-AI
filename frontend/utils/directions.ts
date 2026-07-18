import type { Coordinates } from "@/types";

function coordinatePair(point: Coordinates): string {
  return `${point.lat},${point.lon}`;
}

export function googleMapsDirectionsUrl(destination: Coordinates, origin: Coordinates | null): string {
  const destinationParameter = `destination=${coordinatePair(destination)}`;
  const originParameter = origin ? `&origin=${coordinatePair(origin)}` : "";
  return `https://www.google.com/maps/dir/?api=1&${destinationParameter}${originParameter}&travelmode=driving`;
}
