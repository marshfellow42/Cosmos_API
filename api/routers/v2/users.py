from fastapi import APIRouter, HTTPException, Depends, Query
from ...dependencies import check_uid_exists, check_api_key, to_e164_br
from typing import Annotated
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