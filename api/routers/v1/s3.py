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


@router.get("/blob/getAll")
def list_all_blobs(api_key: Annotated[str | None, Depends(check_api_key)] = None):
    return vercel_blob.list()


@router.post("/blob/uploadFile")
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
):
    content = await file.read()
    category = get_file_category(file.content_type)
    size_limit = get_size_limit(category)
    if category == "unknown":
        raise HTTPException(status_code=400, detail="Tipo de arquivo não suportado.")
    if len(content) > size_limit:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo do tipo {category.capitalize()} muito grande. Tamanho máximo: {size_limit // (1024**2)} MB",
        )
    resp = vercel_blob.put(file.filename, content, verbose=False)
    return {"filename": file.filename, "category": category, "url": resp.get("url")}


@router.delete("/blob/deleteFile")
async def delete_blob(
    url: str, api_key: Annotated[str | None, Depends(check_api_key)] = None
):
    try:
        vercel_blob.delete(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": url}
