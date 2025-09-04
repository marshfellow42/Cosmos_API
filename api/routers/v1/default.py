from fastapi import APIRouter, HTTPException
from ...firebase_config import ref

router = APIRouter(
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        413: {"description": "Request Entity Too Large"},
        500: {"description": "Internal Server Error"},
    }
)


@router.get("/")
def read_root():
    return {"Hello": "World"}


@router.get("/testFirebase")
def testar_o_firebase():
    try:
        if ref.get():
            return {"message": "Conectado com successo ao Firebase"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Falha ao se conectar com o Firebase: {str(e)}"
        )
