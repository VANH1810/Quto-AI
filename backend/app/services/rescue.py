"""Kho cứu hộ (in-memory): tin SOS + đội cứu hộ + logic cử đội gần nhất.

Đội cứu hộ SINH TỰ ĐỘNG 1 đội/xã (đóng tại tâm xã). `assign()` chọn đội RẢNH gần
nhất theo haversine, ước tính quãng đường + ETA (giả định 30 km/h). Mirror Supabase
nếu bật.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.rescue import (RescueRequest, RescueStatus, RescueTeam,
                                RescueTeamCreate, SosCreate, TeamStatus,
                                priority_of)
from app.services import supabase_repo
from app.services.geo_data import (all_communes, get_commune, haversine_km,
                                   nearest_commune, short_name)

_AVG_SPEED_KMH = 30.0


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RescueStore:
    def __init__(self) -> None:
        self._reqs: dict[str, RescueRequest] = {}
        self._teams: dict[str, RescueTeam] = {}
        for commune in all_communes():  # 1 đội/xã
            self._add_team(RescueTeamCreate(
                name=f"Đội cứu hộ {short_name(commune.name)}",
                commune_code=commune.code, base_lat=commune.lat, base_lon=commune.lon,
                phone="0962" + commune.code[:6].ljust(6, "0"), capacity=6))

    # ---- Teams ----
    def _add_team(self, data: RescueTeamCreate) -> RescueTeam:
        tid = "team_" + uuid.uuid4().hex[:8]
        team = RescueTeam(id=tid, **data.model_dump())
        self._teams[tid] = team
        return team

    def add_team(self, data: RescueTeamCreate) -> RescueTeam:
        team = self._add_team(data)
        supabase_repo.mirror(supabase_repo.push_rescue_teams, [team])
        return team

    def teams(self, commune_code: str | None = None) -> list[RescueTeam]:
        items = list(self._teams.values())
        return [t for t in items if t.commune_code == commune_code] if commune_code else items

    def _nearest_available_team(self, lat: float, lon: float) -> RescueTeam | None:
        free = [t for t in self._teams.values() if t.status == TeamStatus.available]
        if not free:
            return None
        return min(free, key=lambda t: haversine_km(lat, lon, t.base_lat, t.base_lon))

    # ---- SOS requests ----
    def create_sos(self, data: SosCreate) -> RescueRequest:
        from app.services.citizens import citizens
        from app.services.shelters import shelters

        full_name, phone, commune_code = data.full_name, data.phone, data.commune_code
        if data.cccd:  # nếu biết CCCD → điền từ DB công dân
            c = citizens.get(data.cccd)
            if c is not None:
                full_name = full_name or c.full_name
                phone = phone or c.phone
                commune_code = commune_code or c.commune_code

        commune = get_commune(commune_code) if commune_code else nearest_commune(data.lat, data.lon)
        shelter = shelters.nearest(commune.code, data.lat, data.lon)

        rid = "sos_" + uuid.uuid4().hex[:10]
        req = RescueRequest(
            id=rid, lat=data.lat, lon=data.lon, danger_type=data.danger_type,
            num_people=data.num_people, full_name=full_name, phone=phone, cccd=data.cccd,
            note=data.note, commune_code=commune.code, commune_name=commune.name,
            priority=priority_of(data.danger_type), status=RescueStatus.pending,
            nearest_shelter_name=shelter.name if shelter else None,
            created_at=_now(), updated_at=_now(),
        )
        self._reqs[rid] = req
        supabase_repo.mirror(supabase_repo.push_rescue_requests, [req])
        return req

    def list_requests(self, status: str | None = None, commune_code: str | None = None,
                      active_only: bool = False) -> list[RescueRequest]:
        items = list(self._reqs.values())
        if status:
            items = [r for r in items if r.status.value == status]
        if commune_code:
            items = [r for r in items if r.commune_code == commune_code]
        if active_only:
            done = {RescueStatus.resolved, RescueStatus.cancelled}
            items = [r for r in items if r.status not in done]
        # ưu tiên cao + mới nhất lên trước
        order = {"critical": 0, "high": 1, "medium": 2}
        return sorted(items, key=lambda r: (order.get(r.priority, 3), r.created_at))

    def get(self, rid: str) -> RescueRequest | None:
        return self._reqs.get(rid)

    def assign(self, rid: str) -> RescueRequest | None:
        """Cử đội cứu hộ rảnh gần nhất tới điểm SOS."""
        req = self._reqs.get(rid)
        if req is None:
            return None
        team = self._nearest_available_team(req.lat, req.lon)
        if team is None:
            raise RuntimeError("Không còn đội cứu hộ rảnh — chờ đội hoàn thành nhiệm vụ khác.")
        dist = haversine_km(req.lat, req.lon, team.base_lat, team.base_lon)
        team.status = TeamStatus.busy
        team.current_request_id = rid
        req.assigned_team_id = team.id
        req.assigned_team_name = team.name
        req.distance_km = dist
        req.eta_min = max(1, round(dist / _AVG_SPEED_KMH * 60))
        req.status = RescueStatus.dispatched
        req.updated_at = _now()
        supabase_repo.mirror(supabase_repo.push_rescue_requests, [req])
        supabase_repo.mirror(supabase_repo.push_rescue_teams, [team])
        return req

    def update_status(self, rid: str, status: RescueStatus) -> RescueRequest | None:
        req = self._reqs.get(rid)
        if req is None:
            return None
        req.status = status
        req.updated_at = _now()
        # Cứu xong / huỷ → giải phóng đội cứu hộ
        if status in (RescueStatus.resolved, RescueStatus.cancelled) and req.assigned_team_id:
            team = self._teams.get(req.assigned_team_id)
            if team is not None:
                team.status = TeamStatus.available
                team.current_request_id = None
                supabase_repo.mirror(supabase_repo.push_rescue_teams, [team])
        supabase_repo.mirror(supabase_repo.push_rescue_requests, [req])
        return req

    def load_request_raw(self, row: dict) -> None:
        """Nạp 1 tin SOS từ Supabase khi khởi động (giữ dashboard qua restart)."""
        self._reqs[row["id"]] = RescueRequest(**row)


rescue = RescueStore()
