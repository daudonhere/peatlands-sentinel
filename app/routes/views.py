from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(include_in_schema=False)


@router.get("/")
async def dashboard_view(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "Peatlands Sentinel",
            "initial_coords": [102.5, 0.5],
            "initial_zoom": 9,
        },
    )
