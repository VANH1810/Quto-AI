"use client";

import { useEffect, useMemo } from "react";
import L, { type Layer } from "leaflet";
import { Circle, GeoJSON, MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import type { Feature, Geometry, Polygon } from "geojson";
import type { CommuneAlert, CommuneGeoJSON, CommuneProperties, DashboardData, ProvinceGeoJSON, RiskFilter, SelectedPlace, UserPosition } from "@/types";
import { RISK_META } from "@/utils/risk";

interface MapCanvasProps extends DashboardData {
  filter: RiskFilter;
  selection: SelectedPlace | null;
  userPosition: UserPosition | null;
  focusPoint: [number, number] | null;
  focusZoom: number;
  onSelect: (place: SelectedPlace) => void;
}

const communeIcon = L.divIcon({ className: "map-marker commune-marker", html: "<span><i></i></span>", iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -13] });
const shelterIcon = L.divIcon({ className: "map-marker shelter-marker", html: "<span aria-hidden='true'>⌂</span>", iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -16] });
const userIcon = L.divIcon({ className: "map-marker user-marker", html: "<span><i></i></span>", iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -16] });

function FocusController({ point, zoom }: { point: [number, number] | null; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    if (point) map.flyTo(point, zoom, { duration: 0.8 });
  }, [map, point, zoom]);
  return null;
}

function ProvinceViewport({ boundary }: { boundary: ProvinceGeoJSON }) {
  const map = useMap();
  useEffect(() => {
    const bounds = L.geoJSON(boundary).getBounds();
    if (!bounds.isValid()) return;
    map.setMaxBounds(bounds.pad(0.04));
    map.fitBounds(bounds, { padding: [18, 18], animate: false });
    map.setMinZoom(map.getZoom());
  }, [boundary, map]);
  return null;
}

function createOutsideMask(boundary: ProvinceGeoJSON): Feature<Polygon> {
  const provinceRings = boundary.features.flatMap((feature) => {
    if (feature.geometry.type === "Polygon") return [feature.geometry.coordinates[0]];
    return feature.geometry.coordinates.map((polygon) => polygon[0]);
  });
  const coordinates = provinceRings.flat();
  const longitudes = coordinates.map(([longitude]) => longitude);
  const latitudes = coordinates.map(([, latitude]) => latitude);
  const west = Math.min(...longitudes) - 0.75;
  const east = Math.max(...longitudes) + 0.75;
  const south = Math.min(...latitudes) - 0.75;
  const north = Math.max(...latitudes) + 0.75;
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [
        [[west, south], [east, south], [east, north], [west, north], [west, south]],
        ...provinceRings,
      ],
    },
  };
}

function escapeHtml(value: string) {
  return value.replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character] ?? character);
}

export default function MapCanvas({ provinceBoundary, boundaries, alerts, shelters, communeCenters, filter, selection, userPosition, focusPoint, focusZoom, onSelect }: MapCanvasProps) {
  const alertsByCommune = useMemo(() => new Map(alerts.map((alert) => [alert.communeCode, alert])), [alerts]);
  const outsideMask = useMemo(() => createOutsideMask(provinceBoundary), [provinceBoundary]);

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
    <MapContainer center={[21.68, 103.0]} zoom={8} minZoom={7} maxZoom={15} maxBoundsViscosity={1} zoomControl={false} className="leaflet-map">
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <GeoJSON
        data={outsideMask}
        interactive={false}
        style={{ fillColor: "#e8eef0", fillOpacity: 0.88, color: "transparent", weight: 0, fillRule: "evenodd" }}
      />
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

      {communeCenters.map((commune) => {
        const alert = alertsByCommune.get(commune.code);
        if (!alert || (filter !== "all" && alert.hazard !== filter)) return null;
        return (
          <Marker key={commune.code} position={[commune.lat, commune.lon]} icon={communeIcon} eventHandlers={{ click: () => onSelect({ type: "commune", id: commune.code }) }}>
            <Popup><div className="marker-popup"><small>Trung tâm xã</small><strong>{commune.name}</strong><span style={{ color: RISK_META[alert.riskLevel].color }}>Cấp {alert.riskLevel} · {alert.hazardLabel}</span><p>{alert.recommendedActions[0]}</p></div></Popup>
          </Marker>
        );
      })}

      {shelters.map((shelter) => (
        <Marker key={shelter.id} position={[shelter.lat, shelter.lon]} icon={shelterIcon} eventHandlers={{ click: () => onSelect({ type: "shelter", id: shelter.id }) }}>
          <Popup><div className="marker-popup"><small>Điểm trú ẩn</small><strong>{shelter.name}</strong><span>{shelter.address}</span><p>Sức chứa dự kiến: {shelter.capacity} người</p></div></Popup>
        </Marker>
      ))}

      {userPosition && (
        <>
          <Circle center={[userPosition.lat, userPosition.lon]} radius={userPosition.accuracy} pathOptions={{ color: "#176b87", fillColor: "#4ab3d2", fillOpacity: 0.14, weight: 1 }} />
          <Marker position={[userPosition.lat, userPosition.lon]} icon={userIcon} eventHandlers={{ click: () => onSelect({ type: "user", id: "current" }) }}>
            <Popup><div className="marker-popup"><small>Vị trí hiện tại</small><strong>Vị trí của bạn</strong><span>Độ chính xác khoảng {Math.round(userPosition.accuracy)} m</span><p>Nhấn để xem điểm trú ẩn gần nhất.</p></div></Popup>
          </Marker>
        </>
      )}
      <FocusController point={focusPoint} zoom={focusZoom} />
      <ProvinceViewport boundary={provinceBoundary} />
    </MapContainer>
  );
}
