from fastapi import FastAPI

from app.routers import plans

app = FastAPI()
app.include_router(plans.router)
