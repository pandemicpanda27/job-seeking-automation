import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    app = FastAPI()

    app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")

    templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return templates.TemplateResponse("pages/index.html", {"request": request})
    
    @app.get("/api/jobs")
    async def get_jobs():
        return JSONResponse({"jobs": []})

    @app.get("/style.css")
    async def serve_style():
        css_path = os.path.join(base_dir, "static/style.css")
        return FileResponse(css_path)

    @app.get("/script.js")
    async def serve_script():
        js_path = os.path.join(base_dir, "static/script.js")
        return FileResponse(js_path)

    return app

app = create_app()

# to run this file use command -> uvicorn main:app --reload
