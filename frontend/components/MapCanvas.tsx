"use client";

import { useEffect, useMemo } from "react";
import L, { type Layer } from "leaflet";
import { Circle, GeoJSON, MapContainer, Marker, Pane, Popup, TileLayer, useMap } from "react-leaflet";
import type { Feature, Geometry, Polygon } from "geojson";
import type { CommuneAlert, CommuneGeoJSON, CommuneProperties, Coordinates, DashboardData, ProvinceGeoJSON, RiskFilter, SelectedPlace, UserPosition } from "@/types";
import { googleMapsDirectionsUrl } from "@/utils/directions";
import { representativePointFromFeature } from "@/utils/geo";
import { RISK_META } from "@/utils/risk";
import { SHELTER_KIND_LABELS } from "@/utils/shelter";

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

function ProvinceViewport({ boundary, hasActiveMarkers }: { boundary: ProvinceGeoJSON; hasActiveMarkers: boolean }) {
  const map = useMap();

  useEffect(() => {
    const bounds = L.geoJSON(boundary).getBounds();
    if (!bounds.isValid()) return;

    const container = map.getContainer();
    let animationFrame: number | null = null;

    const fitProvince = () => {
      animationFrame = null;
      if (container.clientWidth === 0 || container.clientHeight === 0) return;

      map.invalidateSize({ animate: false, pan: false });
      if (hasActiveMarkers) return;
      const padding = getResponsivePadding(container);

      // Clear the previous responsive minimum before recalculating for the new size.
      map.setMinZoom(0);
      map.fitBounds(bounds, { ...padding, animate: false });
      map.setMinZoom(map.getZoom());
      map.setMaxBounds(bounds);
    };

    const scheduleFit = () => {
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(fitProvince);
    };

    const resizeObserver = new ResizeObserver(scheduleFit);
    resizeObserver.observe(container);
    window.addEventListener("resize", scheduleFit);
    scheduleFit();

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", scheduleFit);
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    };
  }, [boundary, hasActiveMarkers, map]);

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
        bounds.extend(L.circle([userPosition.lat, userPosition.lon], { radius: userPosition.accuracy }).getBounds());
      }
      map.fitBounds(bounds, { ...getResponsivePadding(container), maxZoom: 12, animate: false });
    };

    const scheduleFit = () => {
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(fitMarkers);
    };

    const resizeObserver = new ResizeObserver(scheduleFit);
    resizeObserver.observe(container);
    window.addEventListener("resize", scheduleFit);
    scheduleFit();

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", scheduleFit);
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

export default function MapCanvas({ provinceBoundary, boundaries, alerts, shelters, filter, selection, userPosition, routeOrigin, onSelect }: MapCanvasProps) {
  const alertsByCommune = useMemo(() => new Map(alerts.map((alert) => [alert.communeCode, alert])), [alerts]);
  const outsideMask = useMemo(() => createOutsideMask(provinceBoundary), [provinceBoundary]);
  const provinceBounds = useMemo(() => L.geoJSON(provinceBoundary).getBounds(), [provinceBoundary]);
  const approximateLocation = useMemo(() => {
    if (userPosition || selection?.type !== "commune") return null;
    const feature = boundaries.features.find((item) => item.properties.code === selection.id);
    if (!feature) return null;
    return { ...representativePointFromFeature(feature), code: feature.properties.code, name: feature.properties.name };
  }, [boundaries, selection, userPosition]);

  function onEachFeature(feature: Feature<Geometry, CommuneProperties>, layer: Layer) {
    const alert = alertsByCommune.get(feature.properties.code);
    if (!alert) return;
    const risk = RISK_META[alert.riskLevel];
    layer.on({ click: () => onSelect({ type: "commune", id: feature.properties.code }) });
    layer.bindPopup(
      `<div class="polygon-popup"><small>${escapeHtml(risk.label)}</small><strong>${escapeHtml(feature.properties.name)}</strong><span>${escapeHtml(alert.hazardLabel)} · ${escapeHtml(alert.headline)}</span><b>Xem hướng dẫn an toàn →</b></div>`,
      { closeButton: false, offset: [0, -4] },
    );
  }

  return (
    <MapContainer bounds={provinceBounds} maxBounds={provinceBounds} maxZoom={13} maxBoundsViscosity={1} zoomSnap={0.25} zoomDelta={0.5} zoomControl={false} className="leaflet-map">
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Pane name="outside-province-mask" style={{ zIndex: 350, pointerEvents: "none" }}>
        <GeoJSON
          data={outsideMask}
          interactive={false}
          style={{ fillColor: "#68757b", fillOpacity: 0.58, color: "transparent", weight: 0, fillRule: "evenodd" }}
        />
      </Pane>
      <GeoJSON
        key={`${filter}-${selection?.type}-${selection?.id}`}
        data={boundaries as CommuneGeoJSON}
        onEachFeature={onEachFeature}
        style={(feature) => {
          const code = feature?.properties?.code as string;
          const alert = alertsByCommune.get(code) as CommuneAlert | undefined;
          const matches = filter === "all" || alert?.hazard === filter;
          const active = selection?.type === "commune" && selection.id === code;
          const color = alert ? RISK_META[alert.riskLevel].color : "#94a3b8";
          return { fillColor: matches ? color : "#cbd5e1", fillOpacity: matches ? (active ? 0.84 : 0.67) : 0.12, color: active ? "#102c3c" : "#ffffff", weight: active ? 3 : 1.5, opacity: matches ? 0.95 : 0.45 };
        }}
      />
      <GeoJSON
        data={provinceBoundary}
        interactive={false}
        style={{ fillOpacity: 0, color: "#123b4a", opacity: 0.9, weight: 2.5 }}
      />

      {shelters.map((shelter) => (
        <Marker key={shelter.id} position={[shelter.lat, shelter.lon]} icon={shelterIcon} eventHandlers={{ click: () => onSelect({ type: "shelter", id: shelter.id }) }}>
          <Popup>
            <div className="marker-popup">
              <small>{SHELTER_KIND_LABELS[shelter.kind]}</small>
              <strong>{shelter.name}</strong>
              <span>{shelter.communeName}</span>
              <span>{shelter.address}</span>
              <p>Tọa độ: {shelter.lat}, {shelter.lon}</p>
              <a
                className="marker-directions"
                href={googleMapsDirectionsUrl(shelter, routeOrigin)}
                target="_blank"
                rel="noopener noreferrer"
              >
                Xem đường đi đến điểm trú ẩn
              </a>
            </div>
          </Popup>
        </Marker>
      ))}

      {userPosition && (
        <>
          <Circle center={[userPosition.lat, userPosition.lon]} radius={userPosition.accuracy} pathOptions={{ color: "#176b87", fillColor: "#4ab3d2", fillOpacity: 0.14, weight: 1 }} />
          <Marker position={[userPosition.lat, userPosition.lon]} icon={userIcon} eventHandlers={{ click: () => onSelect({ type: "user", id: "current" }) }}>
            <Popup><div className="marker-popup"><small>Vị trí hiện tại</small><strong>Vị trí của bạn</strong><span>Độ chính xác khoảng {Math.round(userPosition.accuracy)} m</span><p>Chọn để xem điểm trú ẩn gần nhất.</p></div></Popup>
          </Marker>
        </>
      )}

      {approximateLocation && (
        <Marker
          position={[approximateLocation.lat, approximateLocation.lon]}
          icon={approximateIcon}
          eventHandlers={{ click: () => onSelect({ type: "commune", id: approximateLocation.code }) }}
        >
          <Popup><div className="marker-popup"><small>Vị trí gần đúng</small><strong>{approximateLocation.name}</strong><span>Tính trực tiếp từ polygon GeoJSON của xã.</span><p>Điểm đại diện được bảo đảm nằm trong địa giới.</p></div></Popup>
        </Marker>
      )}

      <ProvinceViewport boundary={provinceBoundary} hasActiveMarkers={Boolean(shelters.length || userPosition)} />
      <ActiveMarkersViewport shelters={shelters} userPosition={userPosition} approximateLocation={approximateLocation} />
    </MapContainer>
  );
}
