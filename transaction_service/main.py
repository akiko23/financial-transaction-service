from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from transaction_service.controllers.metrics import router as metrics_router
from transaction_service.controllers.middlewares.metrics_middleware import RequestCountMiddleware
from transaction_service.controllers.middlewares.rate_limiting_middleware import RateLimitMiddleware
from transaction_service.controllers.transactions import router as transactions_router
from transaction_service.di import setup_di


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    yield

    await app_.container.close()


def create_app(ioc_container: AsyncContainer):
    application = FastAPI(title="Transaction Service", version="1.0.0", lifespan=lifespan)

    setup_dishka(container=ioc_container, app=application)
    application.container = ioc_container

    application.add_middleware(RequestCountMiddleware)
    application.add_middleware(RateLimitMiddleware, ioc_container=ioc_container)

    application.include_router(transactions_router, prefix="/api/v1")
    application.include_router(metrics_router)

    @application.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return application


container = setup_di()
app = create_app(container)

# frontend
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="static/")

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
