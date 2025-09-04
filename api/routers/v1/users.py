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


@router.get("/getAllUsers")
def conseguir_todos_os_usuarios_logado_com_o_email_normal_no_firebase(
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
):
    users = []
    page = auth.list_users()
    while page:
        for user in page.users:
            users.append(
                {
                    "uid": user.uid,
                    "email": user.email,
                    "passwordHash": user.password_hash,
                    "passwordSalt": user.password_salt,
                    "display_name": user.display_name,
                    "phone_number": user.phone_number or "",
                    "photo_url": user.photo_url or "",
                }
            )
        page = page.get_next_page()
    return users


@router.post("/add/user")
async def criar_um_usuario_com_email_e_senha(
    email: str,
    password: str,
    display_name: str,
    phone_number: str | None = None,
    photo_url: str | None = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
):
    user = auth.create_user(
        email=email,
        email_verified=False,
        phone_number=to_e164_br(phone_number),
        password=password,
        display_name=display_name,
        photo_url=photo_url,
        disabled=False,
    )

    return {"message": "Criado um usuário com sucesso. UID: {0}".format(user.uid)}


@router.delete("/delete/user")
async def deletar_um_usuario_com_o_uid(
    uid_do_usuario: Annotated[str | None, Depends(check_uid_exists)] = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
):
    if check_uid_exists(uid_do_usuario):
        auth.delete_user(uid_do_usuario)
        return {
            "message": f"O usuário com o UID {uid_do_usuario} foi deletado com sucesso."
        }
    else:
        raise HTTPException(
            status_code=400, detail="Este usuário não existe no banco de dados"
        )


@router.patch("/update/user")
async def atualizar_os_dados_de_um_usuário(
    uid_do_usuario: Annotated[str, Query(...)],
    email: Annotated[str | None, Query()] = None,
    password: Annotated[str | None, Query()] = None,
    display_name: Annotated[str | None, Query()] = None,
    phone_number: Annotated[str | None, Query()] = None,
    photo_url: Annotated[str | None, Query()] = None,
    disabled: Annotated[bool | None, Query()] = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
):
    if not check_uid_exists(uid_do_usuario):
        raise HTTPException(
            status_code=404, detail="Este usuário não existe no banco de dados"
        )

    try:
        update_data = {}
        if email is not None:
            update_data["email"] = email
        if phone_number is not None:
            update_data["phone_number"] = to_e164_br(phone_number)
        if password is not None:
            update_data["password"] = password
        if display_name is not None:
            update_data["display_name"] = display_name
        if photo_url is not None:
            update_data["photo_url"] = photo_url
        if disabled is not None:
            update_data["disabled"] = disabled

        user = auth.update_user(uid_do_usuario, **update_data)

        return {"message": f"Usuário {user.uid} atualizado com sucesso."}

    except auth.AuthError as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao atualizar o usuário: {str(e)}"
        )
