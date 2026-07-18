"use client";

import { memo, useCallback, useEffect, useMemo, useRef } from "react";
import L, { type Layer } from "leaflet";
import { GeoJSON, MapContainer, Marker, Pane, Popup, TileLayer, useMap } from "react-leaflet";
import type { Feature, Geometry, Polygon } from "geojson";
import type { CommuneAlert, CommuneGeoJSON, CommuneProperties, Coordinates, DashboardData, ProvinceGeoJSON, RiskFilter, SelectedPlace, Shelter, UserPosition } from "@/types";
import { googleMapsDirectionsUrl } from "@/utils/directions";
import { collectionContainsCoordinates, representativePointFromFeature } from "@/utils/geo";
import { RISK_META } from "@/utils/risk";
import { formatShelterCapacity, SHELTER_KIND_LABELS } from "@/utils/shelter";

interface MapCanvasProps extends DashboardData {
  filter: RiskFilter;
  selection: SelectedPlace | null;
  userPosition: UserPosition | null;
  routeOrigin: Coordinates | null;
  onSelect: (place: SelectedPlace) => void;
}

const shelterIcon = L.divIcon({ className: "map-marker shelter-marker", html: "<span aria-hidden='true'>⌂</span>", iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -16] });
const userIcon = L.divIcon({ className: "map-marker user-marker", html: "<span><i></i></span>", iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -16] });
const approximateIcon = L.divIcon({ className: "map-marker approximate-marker", html: "<span><i></i></span>", iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -16] });
const OUTSIDE_MASK_STYLE = { fillColor: "#68757b", fillOpacity: 0.58, color: "transparent", weight: 0, fillRule: "evenodd" as const };
const PROVINCE_BOUNDARY_STYLE = { fillOpacity: 0, color: "#123b4a", opacity: 0.9, weight: 2.5 };
const MAP_MAX_ZOOM = 13;

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}

function getResponsivePadding(container: HTMLElement) {
  const { clientWidth: width, clientHeight: height } = container;
  const horizontal = clamp(Math.round(width * 0.035), 12, 36);

  if (width <= 480) {
    return {
      paddingTopLeft: L.point(horizontal, clamp(Math.round(height * 0.13), 48, 60)),
      paddingBottomRight: L.point(horizontal, clamp(Math.round(height * 0.12), 44, 62)),
    };
  }

  if (width <= 860) {
    return {
      paddingTopLeft: L.point(horizontal, clamp(Math.round(height * 0.12), 50, 68)),
      paddingBottomRight: L.point(horizontal, clamp(Math.round(height * 0.09), 36, 54)),
    };
  }

  return {
    paddingTopLeft: L.point(horizontal, clamp(Math.round(height * 0.1), 52, 72)),
    paddingBottomRight: L.point(horizontal, clamp(Math.round(height * 0.055), 24, 40)),
  };
}

function ProvinceViewport({ bounds, hasActiveMarkers }: { bounds: L.LatLngBounds; hasActiveMarkers: boolean }) {
  const map = useMap();

  useEffect(() => {
    if (!bounds.isValid()) return;

    const container = map.getContainer();
    let animationFrame: number | null = null;
    let dragAnimationFrame: number | null = null;

    const constrainViewport = () => {
      animationFrame = null;
      if (container.clientWidth === 0 || container.clientHeight === 0) return;

      map.invalidateSize({ animate: false, pan: false });
      const padding = getResponsivePadding(container);
      const totalPadding = padding.paddingTopLeft.add(padding.paddingBottomRight);

      // The minimum zoom is recalculated from the real province bounding box so
      // resizing cannot expose a wider region. Layers and the map instance stay mounted.
      map.setMinZoom(0);
      map.setMaxBounds(bounds);
      map.setMaxZoom(MAP_MAX_ZOOM);
      const minimumZoom = Math.min(MAP_MAX_ZOOM, map.getBoundsZoom(bounds, false, totalPadding));
      map.setMinZoom(minimumZoom);

      if (!hasActiveMarkers) {
        map.fitBounds(bounds, { ...padding, maxZoom: MAP_MAX_ZOOM, animate: false });
      } else if (map.getZoom() < minimumZoom) {
        map.setZoom(minimumZoom, { animate: false });
      }

      map.panInsideBounds(bounds, { animate: false });
    };

    const scheduleConstraint = () => {
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(constrainViewport);
    };

    const returnToValidViewport = () => {
      if (map.getZoom() < map.getMinZoom()) map.setZoom(map.getMinZoom(), { animate: true });
      if (map.getZoom() > MAP_MAX_ZOOM) map.setZoom(MAP_MAX_ZOOM, { animate: true });
      map.panInsideBounds(bounds, { animate: true, duration: 0.2 });
    };

    const constrainDuringDrag = () => {
      if (dragAnimationFrame !== null) return;
      dragAnimationFrame = requestAnimationFrame(() => {
        dragAnimationFrame = null;
        map.panInsideBounds(bounds, { animate: false, noMoveStart: true });
      });
    };

    const resizeObserver = new ResizeObserver(scheduleConstraint);
    resizeObserver.observe(container);
    map.on("drag", constrainDuringDrag);
    map.on("dragend zoomend", returnToValidViewport);
    scheduleConstraint();

    return () => {
      resizeObserver.disconnect();
      map.off("drag", constrainDuringDrag);
      map.off("dragend zoomend", returnToValidViewport);
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      if (dragAnimationFrame !== null) cancelAnimationFrame(dragAnimationFrame);
    };
  }, [bounds, hasActiveMarkers, map]);

  return null;
}

function ActiveMarkersViewport({
  shelters,
  userPosition,
  approximateLocation,
}: {
  shelters: DashboardData["shelters"];
  userPosition: UserPosition | null;
  approximateLocation: Coordinates | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (!shelters.length && !userPosition) return;

    const container = map.getContainer();
    let animationFrame: number | null = null;

    const fitMarkers = () => {
      animationFrame = null;
      if (container.clientWidth === 0 || container.clientHeight === 0) return;

      map.invalidateSize({ animate: false, pan: false });
      const points = shelters.map((shelter) => L.latLng(shelter.lat, shelter.lon));
      if (userPosition) points.push(L.latLng(userPosition.lat, userPosition.lon));
      else if (approximateLocation) points.push(L.latLng(approximateLocation.lat, approximateLocation.lon));
      if (!points.length) return;

      const bounds = L.latLngBounds(points);
      if (userPosition) {
        if (userPosition.accuracy > 0) {
          bounds.extend(L.latLng(userPosition.lat, userPosition.lon).toBounds(userPosition.accuracy * 2));
        }
      }
      map.fitBounds(bounds, { ...getResponsivePadding(container), maxZoom: 12, animate: false });
    };

    const scheduleFit = () => {
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(fitMarkers);
    };

    const resizeObserver = new ResizeObserver(scheduleFit);
    resizeObserver.observe(container);
    scheduleFit();

    return () => {
      resizeObserver.disconnect();
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    };
  }, [approximateLocation, map, shelters, userPosition]);

  return null;
}

function createOutsideMask(boundary: ProvinceGeoJSON): Feature<Polygon> {
  const provinceRings = boundary.features.flatMap((feature) =>
    feature.geometry.type === "Polygon"
      ? feature.geometry.coordinates
      : feature.geometry.coordinates.flatMap((polygon) => polygon),
  );

  // A Web Mercator world shell plus every real province ring creates an
  // even-odd mask: the province is a transparent hole and any genuine holes
  // in its geometry remain masked. No estimated province rectangle is used.
  const webMercatorWorld = [
    [-180, -85.05112878],
    [180, -85.05112878],
    [180, 85.05112878],
    [-180, 85.05112878],
    [-180, -85.05112878],
  ];

  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [
        webMercatorWorld,
        ...provinceRings,
      ],
    },
  };
}

function escapeHtml(value: string) {
  return value.replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character] ?? character);
}

const CommuneRiskLayer = memo(function CommuneRiskLayer({ boundaries, alertsByCommune, filter, selection, onSelect }: {
  boundaries: CommuneGeoJSON;
  alertsByCommune: Map<string, CommuneAlert>;
  filter: RiskFilter;
  selection: SelectedPlace | null;
  onSelect: (place: SelectedPlace) => void;
}) {
  const layerRef = useRef<L.GeoJSON<CommuneProperties> | null>(null);
  const getCommuneStyle = useCallback((feature?: Feature<Geometry, CommuneProperties>) => {
    const code = feature?.properties.code ?? "";
    const alert = alertsByCommune.get(code);
    const matches = filter === "all" || alert?.hazard === filter;
    const active = selection?.type === "commune" && selection.id === code;
    const color = alert ? RISK_META[alert.riskLevel].color : "#94a3b8";
    return { fillColor: matches ? color : "#cbd5e1", fillOpacity: matches ? (active ? 0.84 : 0.67) : 0.12, color: active ? "#102c3c" : "#ffffff", weight: active ? 3 : 1.5, opacity: matches ? 0.95 : 0.45 };
  }, [alertsByCommune, filter, selection]);
  const styleRef = useRef(getCommuneStyle);
  styleRef.current = getCommuneStyle;
  const stableStyle = useCallback((feature?: Feature<Geometry, CommuneProperties>) => styleRef.current(feature), []);
  const onEachFeature = useCallback((feature: Feature<Geometry, CommuneProperties>, layer: Layer) => {
    const alert = alertsByCommune.get(feature.properties.code);
    if (!alert) return;
    const risk = RISK_META[alert.riskLevel];
    layer.on({ click: () => onSelect({ type: "commune", id: feature.properties.code }) });
    layer.bindPopup(
      `<div class="polygon-popup"><small>${escapeHtml(risk.label)}</small><strong>${escapeHtml(feature.properties.name)}</strong><span>${escapeHtml(alert.hazardLabel)} · ${escapeHtml(alert.headline)}</span><b>Xem hướng dẫn an toàn →</b></div>`,
      { className: "map-popup", closeButton: true, offset: [0, -4] },
    );
  }, [alertsByCommune, onSelect]);

  useEffect(() => {
    layerRef.current?.setStyle(getCommuneStyle);
  }, [getCommuneStyle]);

  return <GeoJSON ref={layerRef} data={boundaries} onEachFeature={onEachFeature} style={stableStyle} />;
});

const StaticMapLayers = memo(function StaticMapLayers({ outsideMask, provinceBoundary }: { outsideMask: Feature<Polygon>; provinceBoundary: ProvinceGeoJSON }) {
  return <>
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    <Pane name="outside-province-mask" style={{ zIndex: 350, pointerEvents: "none" }}>
      <GeoJSON data={outsideMask} interactive={false} style={OUTSIDE_MASK_STYLE} />
    </Pane>
    <GeoJSON data={provinceBoundary} interactive={false} style={PROVINCE_BOUNDARY_STYLE} />
  </>;
});

const ShelterMarker = memo(function ShelterMarker({ shelter, routeOrigin, onSelect }: { shelter: Shelter; routeOrigin: Coordinates | null; onSelect: (place: SelectedPlace) => void }) {
  const position = useMemo<[number, number]>(() => [shelter.lat, shelter.lon], [shelter.lat, shelter.lon]);
  const eventHandlers = useMemo(() => ({ click: () => onSelect({ type: "shelter", id: shelter.id }) }), [onSelect, shelter.id]);
  const directionsUrl = useMemo(() => googleMapsDirectionsUrl(shelter, routeOrigin), [routeOrigin, shelter]);
  return <Marker position={position} icon={shelterIcon} eventHandlers={eventHandlers}>
    <Popup className="map-popup"><div className="marker-popup"><small>{SHELTER_KIND_LABELS[shelter.kind]}</small><strong>{shelter.name}</strong><span className="marker-popup-address">{shelter.address}</span><span className="marker-popup-capacity">Sức chứa {formatShelterCapacity(shelter)}</span><p>Tọa độ: {shelter.lat}, {shelter.lon}</p><a className="marker-directions" href={directionsUrl} target="_blank" rel="noopener noreferrer">Xem đường đi đến điểm trú ẩn</a></div></Popup>
  </Marker>;
});

const UserLocationLayer = memo(function UserLocationLayer({ position, onSelect }: { position: UserPosition; onSelect: (place: SelectedPlace) => void }) {
  const center = useMemo<[number, number]>(() => [position.lat, position.lon], [position.lat, position.lon]);
  const eventHandlers = useMemo(() => ({ click: () => onSelect({ type: "user", id: "current" }) }), [onSelect]);
  return <>
    <Marker position={center} icon={userIcon} eventHandlers={eventHandlers}>
      <Popup><div className="marker-popup"><small>Vị trí hiện tại</small><strong>Vị trí của bạn</strong><span>Tọa độ: {position.lat}, {position.lon}</span><p>Chọn để xem điểm trú ẩn gần nhất.</p></div></Popup>
    </Marker>
  </>;
});

const ApproximateLocationMarker = memo(function ApproximateLocationMarker({ location, onSelect }: { location: Coordinates & { code: string; name: string }; onSelect: (place: SelectedPlace) => void }) {
  const position = useMemo<[number, number]>(() => [location.lat, location.lon], [location.lat, location.lon]);
  const eventHandlers = useMemo(() => ({ click: () => onSelect({ type: "commune", id: location.code }) }), [location.code, onSelect]);
  return <Marker position={position} icon={approximateIcon} eventHandlers={eventHandlers}><Popup><div className="marker-popup"><small>Vị trí gần đúng</small><strong>{location.name}</strong><span>Tính trực tiếp từ polygon GeoJSON của xã.</span><p>Điểm đại diện được bảo đảm nằm trong địa giới.</p></div></Popup></Marker>;
});

function MapCanvas({ provinceBoundary, boundaries, alerts, shelters, filter, selection, userPosition, routeOrigin, onSelect }: MapCanvasProps) {
  const alertsByCommune = useMemo(() => new Map(alerts.map((alert) => [alert.communeCode, alert])), [alerts]);
  const outsideMask = useMemo(() => createOutsideMask(provinceBoundary), [provinceBoundary]);
  const provinceBounds = useMemo(() => L.geoJSON(provinceBoundary).getBounds(), [provinceBoundary]);
  const boundedUserPosition = useMemo(
    () => userPosition && collectionContainsCoordinates(provinceBoundary, userPosition) ? userPosition : null,
    [provinceBoundary, userPosition],
  );
  const approximateLocation = useMemo(() => {
    if (boundedUserPosition || selection?.type !== "commune") return null;
    const feature = boundaries.features.find((item) => item.properties.code === selection.id);
    if (!feature) return null;
    return { ...representativePointFromFeature(feature), code: feature.properties.code, name: feature.properties.name };
  }, [boundaries, boundedUserPosition, selection]);

  return <MapContainer preferCanvas bounds={provinceBounds} maxBounds={provinceBounds} maxZoom={MAP_MAX_ZOOM} maxBoundsViscosity={1} inertia={false} bounceAtZoomLimits={false} zoomSnap={0.25} zoomDelta={0.5} zoomControl={false} className="leaflet-map">
    <StaticMapLayers outsideMask={outsideMask} provinceBoundary={provinceBoundary} />
    <CommuneRiskLayer boundaries={boundaries} alertsByCommune={alertsByCommune} filter={filter} selection={selection} onSelect={onSelect} />
    {shelters.map((shelter) => <ShelterMarker key={shelter.id} shelter={shelter} routeOrigin={routeOrigin} onSelect={onSelect} />)}
    {boundedUserPosition && <UserLocationLayer position={boundedUserPosition} onSelect={onSelect} />}
    {approximateLocation && <ApproximateLocationMarker location={approximateLocation} onSelect={onSelect} />}
    <ProvinceViewport bounds={provinceBounds} hasActiveMarkers={Boolean(shelters.length || boundedUserPosition)} />
    <ActiveMarkersViewport shelters={shelters} userPosition={boundedUserPosition} approximateLocation={approximateLocation} />
  </MapContainer>;
}

export default memo(MapCanvas);
