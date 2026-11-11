from dotenv import load_dotenv
import os
import logging
load_dotenv(dotenv_path=".env", override=True)
 
 
from fastapi import FastAPI
from src.utils.db import Base , engine 
from src.tasks.models  import TaskModel
from src.tasks.router  import task_routes
from src.user.router import user_routes
from src.frontend.router import router as frontend_router
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
 
from google import genai

 
from fastapi import FastAPI, Request, Response
from src.utils.db import Base, engine 
from src.tasks.models import TaskModel
from src.tasks.router import task_routes
from src.user.router import user_routes
from src.frontend.router import router as frontend_router
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from src.utils.logging_config import configure_application_logging
import mimetypes
import os
mimetypes.init()
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
# when our application run then our application start connection in database 
# 
Base.metadata.create_all(engine)
app=FastAPI(title="This is my Task Management Applications")
logger = logging.getLogger(__name__)

@app.on_event("startup")
def setup_application_logging():
    configure_application_logging()
 
from fastapi import Request, Response
 
class HTTPSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        # Only force HTTPS scheme when deployed in production (not on localhost)
        if "localhost" not in host and "127.0.0.1" not in host:
            request.scope["scheme"] = "https"
        response = await call_next(request)
        return response

app.add_middleware(HTTPSMiddleware)


# app.add_middleware(HTTPSMiddleware) # Commented out because it breaks local CSS loading by forcing HTTPS links

@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        import traceback
        logger.exception("Unhandled exception while handling %s %s", request.method, request.url.path)
        return Response(content=f"Global Error: {str(e)}\n\n{traceback.format_exc()}", media_type="text/plain", status_code=500)

# Mount Static Files
# Here we change the static path to the dynamic path 
 # Fix for potential MIME type issues on Linux
mimetypes.add_type('text/css', '.css')

# Get absolute path
script_dir = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(script_dir, "static")

# Mount
app.mount("/static", StaticFiles(directory=static_path), name="static")

# app.mount("/static", StaticFiles(directory="static"), name="static")

# include routes are used to register the routes in the main routes 
app.include_router(frontend_router)
app.include_router(task_routes)
# Here we connect the userRoutes Here 
app.include_router(user_routes)



def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    # Apply BearerAuth globally (all endpoints)
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method.setdefault("security", []).append({"BearerAuth": []})
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
