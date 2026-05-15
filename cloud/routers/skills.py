"""SkillMarket REST API router — v1.12.0 (uses app.state)."""
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

router = APIRouter(prefix="/skills", tags=["skills"])

def _get_skill_market(request: Request = None):
    if request and hasattr(request.app.state, "skill_market"):
        sm = request.app.state.skill_market
        if sm: return sm
    from cloud.main import _skill_market
    if not _skill_market: raise HTTPException(503, "SkillMarket not initialized")
    return _skill_market

# ⚠️ /stats must be BEFORE /{skill_id} to avoid route conflict
@router.get("/stats")
async def skill_stats(request: Request):
    sm = _get_skill_market(request)
    return format_api_response(True, data=sm.get_stats())

@router.post("/")
async def publish_skill(request: Request):
    body = await request.json()
    sid = _get_skill_market(request).publish(body)
    return format_api_response(True, data={"skill_id": sid})

@router.get("/")
async def list_skills(request: Request, category: str = Query(None), tags: str = Query(None),
                      search: str = Query(None), limit: int = Query(100), offset: int = Query(0)):
    tag_list = tags.split(",") if tags else None
    sm = _get_skill_market(request)
    skills = sm.list_skills(category=category, tags=tag_list, search=search, limit=limit, offset=offset)
    return format_api_response(True, data={"skills": skills, "count": len(skills)})

@router.get("/{skill_id}")
async def get_skill(skill_id: str, request: Request):
    s = _get_skill_market(request).get_skill(skill_id)
    if not s: return format_api_response(False, error="Not found")
    return format_api_response(True, data=s)

@router.post("/{skill_id}/download")
async def download_skill(skill_id: str, request: Request):
    s = _get_skill_market(request).download(skill_id)
    if not s: return format_api_response(False, error="Not found")
    return format_api_response(True, data=s)
