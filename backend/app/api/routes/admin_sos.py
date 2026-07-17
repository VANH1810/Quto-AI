from fastapi import APIRouter, Depends, HTTPException
from app.schemas.admin import AdminPublic
from app.schemas.rescue import CommuneMappingStatus, RescueStatus, RescueStatusUpdate
from app.security import get_current_admin
from app.services.admin_scope import commune_codes_for, require_commune_access
from app.services.geo_data import get_commune
from app.services.rescue import rescue

router=APIRouter(prefix="/api/v1/admin/sos",tags=["4 · Console admin"],dependencies=[Depends(get_current_admin)])
def _data(value): return {"data":value}
def _can_see(request, admin): return request.commune_code in set(commune_codes_for(admin)) or (request.commune_code is None and admin.role.value=="province")
@router.get("")
def list_sos(status: str|None=None, search: str|None=None, admin: AdminPublic=Depends(get_current_admin)):
    items=[request for request in rescue.list_requests(status=status) if _can_see(request,admin)]
    if search: items=[request for request in items if search.lower() in f"{request.full_name or ''} {request.note or ''} {request.commune_name or ''}".lower()]
    return _data({"items":[item.model_dump() for item in items],"total":len(items)})
@router.get("/{sos_id}")
def detail(sos_id:str,admin:AdminPublic=Depends(get_current_admin)):
    request=rescue.get(sos_id)
    if request is None: raise HTTPException(404,"Không tìm thấy tin SOS")
    if not _can_see(request,admin): raise HTTPException(403,"Bạn không có quyền truy cập SOS này")
    return _data(request.model_dump())
@router.patch("/{sos_id}/status")
def status(sos_id:str,body:RescueStatusUpdate,admin:AdminPublic=Depends(get_current_admin)):
    request=rescue.get(sos_id)
    if request is None: raise HTTPException(404,"Không tìm thấy tin SOS")
    if not _can_see(request,admin): raise HTTPException(403,"Bạn không có quyền truy cập SOS này")
    try: updated=rescue.update_status(sos_id,body.status,body.note)
    except ValueError as error: raise HTTPException(409,str(error))
    return _data(updated.model_dump())
@router.patch("/{sos_id}/commune")
def confirm_commune(sos_id:str,commune_code:str,admin:AdminPublic=Depends(get_current_admin)):
    request=rescue.get(sos_id); commune=get_commune(commune_code)
    if request is None or commune is None: raise HTTPException(404,"Không tìm thấy SOS hoặc xã")
    if admin.role.value!="province": require_commune_access(admin,commune_code)
    request.commune_code,request.commune_name,request.mapping_status=commune.code,commune.name,CommuneMappingStatus.manually_confirmed
    request.audit.append({"step":"mapping","detail":f"Xác nhận thủ công {commune.name}"})
    return _data(request.model_dump())
