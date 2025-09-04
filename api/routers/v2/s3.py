from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from ...dependencies import check_api_key, get_file_category, get_size_limit
import vercel_blob
from typing import Annotated

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