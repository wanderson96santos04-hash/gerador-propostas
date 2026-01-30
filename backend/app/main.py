from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes import router as app_router
from app.auth.routes import router as auth_router

app = FastAPI()

# Templates
templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Rotas
app.include_router(auth_router)
app.include_router(app_router)
