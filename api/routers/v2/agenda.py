from fastapi import APIRouter, HTTPException, Depends, Query
from ...firebase_config import agenda_ref, agenda_membros_ref
from ...dependencies import (
    check_uid_exists,
    check_api_key,
    timestamp_formatado,
    generate_random_invite_key,
)
from typing import Annotated
from datetime import datetime
import uuid
from firebase_admin import auth

router = APIRouter(
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        413: {"description": "Request Entity Too Large"},
        500: {"description": "Internal Server Error"},
    },
)