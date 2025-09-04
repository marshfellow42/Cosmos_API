from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.v1 import (
    default as default_v1,
    agenda as agenda_v1,
    users as users_v1,
    s3 as s3_v1,
)
from .routers.v2 import (
    default as default_v2,
    agenda as agenda_v2,
    users as users_v2,
    s3 as s3_v2,
)

# Versioned tags for Swagger UI
tags_metadata = [
    # V1 tags
    {"name": "V1: Usuários", "description": "Operações com os usuários (v1)"},
    {"name": "V1: Agenda", "description": "Operações com a agenda (v1)"},
    {"name": "V1: S3", "description": "Operações com o bucket S3 (v1)"},
    {"name": "V1: Default", "description": "Operações padrão (v1)"},

    # V2 tags
    {"name": "V2: Usuários", "description": "Operações com os usuários (v2)"},
    {"name": "V2: Agenda", "description": "Operações com a agenda (v2)"},
    {"name": "V2: S3", "description": "Operações com o bucket S3 (v2)"},
    {"name": "V2: Default", "description": "Operações padrão (v2)"},
]

app = FastAPI(title="Cosmos API", openapi_tags=tags_metadata, version="2.0.0")

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- V1 Routers ---
app.include_router(default_v1.router, tags=["V1: Default"])
app.include_router(users_v1.router, tags=["V1: Usuários"])
app.include_router(agenda_v1.router, tags=["V1: Agenda"])
app.include_router(s3_v1.router, tags=["V1: S3"])

# --- V2 Routers ---
app.include_router(default_v2.router, prefix="/v2", tags=["V2: Default"])
app.include_router(users_v2.router, prefix="/v2", tags=["V2: Usuários"])
app.include_router(agenda_v2.router, prefix="/v2", tags=["V2: Agenda"])
app.include_router(s3_v2.router, prefix="/v2", tags=["V2: S3"])
