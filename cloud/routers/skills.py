"""SkillMarket REST API router."""
from fastapi import APIRouter, Request, Query, HTTPException
from shared.protocol import format_api_response

router = APIRouter(prefix="/skills", tags=["skills"])

def _get_skill_market(request: Request = None):
    """Get SkillMarket — app.state first, then module global fallback."""
    if request:
        sm = getattr(request.app.state, 'skill_market', None)
        if sm:
            return sm
    import sys
    mod = sys.modules.get('__main__') or sys.modules.get('cloud.main')
    sm = getattr(mod, '_skill_market', None) if mod else None
    if not sm: raise HTTPException(503, "SkillMarket not initialized")
    return sm

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

@router.get("/stats")
async def skill_stats(request: Request):
    return format_api_response(True, data=_get_skill_market(request).get_stats())
