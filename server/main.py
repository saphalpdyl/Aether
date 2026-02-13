from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_pools, close_pools
from routes import sessions, events, routers, bngs, plans, customers, services, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pools()
    yield
    close_pools()


app = FastAPI(title="OSS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sessions.router)
app.include_router(events.router)
app.include_router(routers.router)
app.include_router(bngs.router)
app.include_router(plans.router)
app.include_router(customers.router)
app.include_router(services.router)
app.include_router(stats.router)

