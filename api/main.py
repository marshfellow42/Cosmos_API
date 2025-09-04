from fastapi import FastAPI, HTTPException, Request, Depends, Query, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from firebase_admin import credentials, db, auth
import firebase_admin

from typing import Annotated

import phonenumbers
from phonenumbers import PhoneNumberFormat


from datetime import datetime
import os
import random
import string
import uuid
import hashlib
import base64

import vercel_blob

from dotenv import load_dotenv

load_dotenv()

cred_info = {
    "type": os.getenv("TYPE"),
    "project_id": os.getenv("PROJECT_ID"),
    "private_key_id": os.getenv("PRIVATE_KEY_ID"),
    "private_key": os.getenv("PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("CLIENT_EMAIL"),
    "client_id": os.getenv("CLIENT_ID"),
    "auth_uri": os.getenv("AUTH_URI"),
    "token_uri": os.getenv("TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("CLIENT_CERT_URL"),
}

cred = credentials.Certificate(cred_info)
firebase_admin.initialize_app(cred, {"databaseURL": os.getenv("DATABASE_URL")})

ref = db.reference("/")
agenda_ref = ref.child("agendas")
agenda_membros_ref = ref.child("agenda_membros")


def to_e164_br(phone_number):
    try:
        parsed = phonenumbers.parse(phone_number, "BR")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        else:
            return None
    except phonenumbers.NumberParseException:
        return None


def timestamp_formatado(dt: datetime) -> str:
    try:
        return dt.replace(microsecond=0).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de timestamp inválido. Use ISO 8601 (ex: '2025-06-27T14:00:00')",
        )


def check_uid_exists(uid: str):
    try:
        user = auth.get_user(uid)
        print(f"✅ User exists: {user.uid}, email: {user.email}")
        return True
    except auth.UserNotFoundError:
        print("❌ No user found with that UID.")
        return False
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return False


def generate_random_invite_key(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    return "".join(random.choices(chars, k=length))


word = os.getenv("SECRET_API_WORD")
hash_bytes = hashlib.sha256(word.encode()).digest()
API_KEY = base64.urlsafe_b64encode(hash_bytes).rstrip(b"=").decode()
API_KEY_NAME = "api_key"


def get_api_key(api_key: str = Query(default=None, alias=API_KEY_NAME)):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(status_code=403, detail="Chave API não autorizada")


# Size limits
PHOTO_LIMIT = 5 * 1024**2
VIDEO_LIMIT = 50 * 1024**2
DOCUMENT_LIMIT = 10 * 1024**2


def get_file_category(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "photo"
    elif content_type.startswith("video/"):
        return "video"
    elif content_type in {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
    }:
        return "document"
    return "unknown"


def get_size_limit(category: str) -> int:
    return {"photo": PHOTO_LIMIT, "video": VIDEO_LIMIT, "document": DOCUMENT_LIMIT}.get(
        category, 0
    )


STANDARD_RESPONSES = {
    400: {"description": "Bad Request"},
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    404: {"description": "Not Found"},
    413: {"description": "Request Entity Too Large"},
    500: {"description": "Internal Server Error"},
}

tags_metadata = [
    {
        "name": "Usuários",
        "description": "Operações com os usuários",
    },
    {
        "name": "Agenda",
        "description": "Operações com a agenda",
    },
    {
        "name": "S3",
        "description": "Operações com o bucket S3",
    },
]

app = FastAPI(title="Cosmos API", openapi_tags=tags_metadata, version="1.0.0")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/testFirebase", responses=STANDARD_RESPONSES)
def testar_o_firebase():
    try:
        if ref.get():
            return {"message": "Conectado com successo ao Firebase"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Falha ao se conectar com o Firebase: {str(e)}"
        )


@app.get("/invite/{chave_de_convite_da_agenda}", responses=STANDARD_RESPONSES)
def mandar_um_convite_para_entrar_na_turma_tipo_o_whatsapp(
    chave_de_convite_da_agenda: str, request: Request
):
    agenda_node = agenda_ref.order_by_child("chave_de_convite").equal_to(
        chave_de_convite_da_agenda
    )
    agenda_data = agenda_node.get()

    if not agenda_data:
        raise HTTPException(status_code=404, detail="Essa agenda não existe")

    for key, val in agenda_data.items():
        return {
            "id": key,
            "uid_da_agenda": key,
            "nome_agenda": val.get("nome_agenda"),
            "chave_de_convite": val.get("chave_de_convite"),
            "firstCreated": val.get("firstCreated"),
        }

    # Detecta o dispositivo
    user_agent = request.headers.get("user-agent", "").lower()

    # Deep link do seu app (Expo deve estar configurado com "scheme": "cosmos")
    deep_link_url = "cosmos://home"

    # URL da Play Store (o pacote deve bater com o app.json do Expo)
    play_store_url = "https://play.google.com/store/apps/details?id=com.luar6.cosmos"

    if "android" in user_agent:
        intent_url = "intent://home#Intent;scheme=cosmos;package=com.luar6.cosmos;end"
        return RedirectResponse(intent_url)

    elif "iphone" in user_agent or "ipad" in user_agent:
        return RedirectResponse(deep_link_url)

    # Fallback para outros dispositivos (desktop, etc)
    return RedirectResponse(play_store_url)


@app.get("/getAllUsers", tags=["Usuários"], responses=STANDARD_RESPONSES)
def conseguir_todos_os_usuarios_logado_com_o_email_normal_no_firebase(
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
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


@app.post("/add/user", tags=["Usuários"], responses=STANDARD_RESPONSES)
async def criar_um_usuario_com_email_e_senha(
    email: str,
    password: str,
    display_name: str,
    phone_number: str | None = None,
    photo_url: str | None = None,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
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


@app.delete("/delete/user", tags=["Usuários"], responses=STANDARD_RESPONSES)
async def deletar_um_usuario_com_o_uid(
    uid_do_usuario: str, api_key: Annotated[str | None, Depends(get_api_key)] = None
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


@app.patch("/update/user", tags=["Usuários"], responses=STANDARD_RESPONSES)
async def atualizar_os_dados_de_um_usuário(
    uid_do_usuario: Annotated[str, Query(...)],
    email: Annotated[str | None, Query()] = None,
    password: Annotated[str | None, Query()] = None,
    display_name: Annotated[str | None, Query()] = None,
    phone_number: Annotated[str | None, Query()] = None,
    photo_url: Annotated[str | None, Query()] = None,
    disabled: Annotated[bool | None, Query()] = None,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
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


@app.get("/getAllAgendas", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def mostrar_todas_as_agendas_criadas(
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    if agenda_ref.get() is None:
        return {"message": "Nenhuma agenda foi criada"}
    else:
        return agenda_ref.get()


@app.get("/getAllAgendasLinkedToUser", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def mostrar_todas_as_agendas_que_o_usuário_faz_parte(
    uid_do_responsavel: str, api_key: Annotated[str | None, Depends(get_api_key)] = None
):
    user_agenda_ids = agenda_membros_ref.child(uid_do_responsavel).get()

    if not user_agenda_ids:
        raise HTTPException(
            status_code=404, detail="O usuário não está ligado a nenhuma agenda"
        )

    agendas = {}
    for agenda_id in user_agenda_ids:
        agenda_data = agenda_ref.child(agenda_id).get()
        if agenda_data:
            agendas[agenda_id] = agenda_data

    return agendas


@app.get("/getAllTarefasFromOneAgenda", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def mostrar_todas_as_tarefas_dentro_de_uma_agenda(
    uid_da_agenda: str, api_key: Annotated[str | None, Depends(get_api_key)] = None
):
    agenda_node = agenda_ref.child(uid_da_agenda).get()

    if not agenda_node:
        raise HTTPException(
            status_code=404, detail=f"A agenda com UID '{uid_da_agenda}' não existe."
        )

    tarefas = agenda_node.get("tarefas")

    if not tarefas:
        raise HTTPException(
            status_code=404, detail=f"A agenda '{uid_da_agenda}' não possui tarefas."
        )

    return tarefas


@app.get("/getAllMembrosFromOneAgenda", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def mostrar_todos_os_membros_dentro_de_uma_agenda(
    uid_da_agenda: str, api_key: Annotated[str | None, Depends(get_api_key)] = None
):
    membros_geral = agenda_membros_ref.get()
    if not membros_geral:
        raise HTTPException(
            status_code=404, detail="Não há membros vinculados a nenhuma agenda."
        )

    membros_da_agenda = {}

    for uid_usuario, agendas in membros_geral.items():
        if uid_da_agenda in agendas:
            role = agendas[uid_da_agenda].get("role", "Desconhecido")
            membros_da_agenda[uid_usuario] = role

    if not membros_da_agenda:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum membro encontrado para a agenda '{uid_da_agenda}'.",
        )

    todos_usuarios = {}
    page = auth.list_users()
    while page:
        for user in page.users:
            todos_usuarios[user.uid] = {
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name,
                "phone_number": user.phone_number or "",
                "photo_url": user.photo_url or "",
            }
        page = page.get_next_page()

    resultado = []
    for uid, role in membros_da_agenda.items():
        usuario_info = todos_usuarios.get(uid)
        if usuario_info:
            usuario_info["role"] = role
            resultado.append(usuario_info)
        else:
            resultado.append(
                {
                    "uid": uid,
                    "role": role,
                    "info": "Usuário não encontrado no Firebase Auth",
                }
            )

    return resultado


@app.post("/add/agenda", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def criar_uma_agenda(
    nome_agenda: str,
    uid_do_responsavel: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    if not check_uid_exists(uid_do_responsavel):
        raise HTTPException(
            status_code=401, detail="Este usuário não existe no banco de dados"
        )

    uid_da_agenda = str(uuid.uuid4())
    agenda_ref.update(
        {
            uid_da_agenda: {
                "nome_agenda": nome_agenda,
                "chave_de_convite": generate_random_invite_key(),
                "firstCreated": timestamp_formatado(datetime.now()),
            }
        }
    )

    agenda_membros_ref.child(uid_do_responsavel).update(
        {uid_da_agenda: {"role": "admin"}}
    )

    return {
        "message": f"A agenda {nome_agenda} com o UID {uid_da_agenda} foi criada com sucesso, com o usuário com o UID {uid_do_responsavel} sendo o responsável por ela"
    }


@app.post("/add/agenda/membro", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def adicionar_um_membro_na_agenda_já_criada(
    uid_da_agenda: str,
    uid_do_membro: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = agenda_ref.child(uid_da_agenda)
    agenda_data = agenda_node.get()

    if not agenda_data:
        raise HTTPException(
            status_code=404, detail=f"A agenda com o UID {uid_da_agenda} não existe"
        )

    if not check_uid_exists(uid_do_membro):
        raise HTTPException(
            status_code=401, detail="Este usuário não existe no banco de dados"
        )

    user = auth.get_user(uid_do_membro)

    agenda_membros_ref.child(user.uid).update({uid_da_agenda: {"role": "user"}})

    return {
        "message": f"O membro {user.display_name} com o UID {user.uid} foi adicionado com sucesso na agenda {agenda_data['nome_agenda']}"
    }


@app.post("/add/agenda/materia", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def criar_uma_materia_na_agenda_já_criada(
    uid_da_agenda: str,
    nome_da_matéria: str,
    nome_do_professor: str | None = None,
    horario_de_inicio_da_materia: str | None = None,
    horario_de_fim_da_materia: str | None = None,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = agenda_ref.child(uid_da_agenda)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404, detail=f"A agenda com o UID {uid_da_agenda} não existe"
        )

    matérias_ref = agenda_node.child("matérias")
    uid = str(uuid.uuid4())
    matérias_ref.update(
        {
            uid: {
                "nome_matéria": nome_da_matéria,
                "professor": nome_do_professor,
                "horario_de_início": horario_de_inicio_da_materia,
                "horário_de_fim": horario_de_fim_da_materia,
            }
        }
    )

    return {
        "message": f"A matéria {nome_da_matéria} com o UID {uid} foi criada com sucesso"
    }


@app.post("/add/agenda/tarefa", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def criar_uma_tarefa_na_agenda_já_criada(
    uid_da_agenda: str,
    nome_da_tarefa: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = agenda_ref.child(uid_da_agenda)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404, detail=f"A agenda com o UID {uid_da_agenda} não existe"
        )

    uid = str(uuid.uuid4())
    tarefa_criada = agenda_node.child("tarefas")
    tarefa_criada.update(
        {
            uid: {
                "nome_da_tarefa": nome_da_tarefa,
                "timestamp": timestamp_formatado(datetime.now()),
            }
        }
    )

    return {"message": f"A tarefa com o UID {uid} foi criada com sucesso."}


@app.post("/add/agenda/evento", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def criar_um_evento_na_agenda_já_criada(
    uid_da_agenda: str,
    nome_do_evento: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = agenda_ref.child(uid_da_agenda)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404, detail=f"A agenda com o UID {uid_da_agenda} não existe"
        )

    uid = str(uuid.uuid4())
    evento_criado = agenda_node.child("eventos")
    evento_criado.update(
        {
            uid: {
                "nome_do_evento": nome_do_evento,
                "timestamp": timestamp_formatado(datetime.now()),
            }
        }
    )

    return {"message": f"O evento com o UID {uid} foi criado com sucesso."}


@app.delete("/delete/agenda", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def deletar_uma_agenda_com_o_uid(
    uid_da_agenda: str, api_key: Annotated[str | None, Depends(get_api_key)] = None
):
    agenda_node = agenda_ref.child(uid_da_agenda)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404, detail=f"A agenda com o UID {uid_da_agenda} não existe"
        )

    agenda_node.delete()

    return {"message": f"A agenda com o UID {uid_da_agenda} foi deletada com sucesso."}


@app.delete("/delete/agenda/membro", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def deletar_um_membro_na_agenda(
    uid_da_agenda: str,
    uid_do_membro: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    membro_node = agenda_membros_ref.child(uid_do_membro).child(uid_da_agenda)
    membro_data = membro_node.get()
    if not membro_data:
        raise HTTPException(
            status_code=404,
            detail=f"Esse usuário com o UID {uid_do_membro} não pertence a agenda com o UID {uid_da_agenda}",
        )

    membro_node.delete()

    return {
        "message": f"O membro com o UID {uid_do_membro} foi removido da agenda com o UID {uid_da_agenda}"
    }


@app.delete("/delete/agenda/materia", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def deletar_uma_materia_com_o_uid(
    uid_da_agenda: str,
    uid_da_materia: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    matéria_node = (
        agenda_ref.child(uid_da_agenda).child("matérias").child(uid_da_materia)
    )
    matéria_data = matéria_node.get()
    if not matéria_data:
        raise HTTPException(
            status_code=404,
            detail=f"A matéria com o UID {uid_da_materia} na agenda {uid_da_agenda} não existe",
        )

    matéria_node.delete()

    return {
        "message": f"A matéria com o UID {uid_da_materia} foi deletada com sucesso."
    }


@app.delete("/delete/agenda/tarefa", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def deletar_uma_tarefa_com_o_uid(
    uid_da_agenda: str,
    uid_da_tarefa: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    tarefa_node = agenda_ref.child(uid_da_agenda).child("tarefas").child(uid_da_tarefa)
    tarefa_data = tarefa_node.get()
    if not tarefa_data:
        raise HTTPException(
            status_code=404,
            detail=f"A tarefa com o UID {uid_da_tarefa} na agenda {uid_da_agenda} não existe",
        )

    tarefa_node.delete()

    return {"message": f"A tarefa com o UID {uid_da_tarefa} foi deletada com sucesso."}


@app.delete("/delete/agenda/evento", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def deletar_um_evento_com_o_uid(
    uid_da_agenda: str,
    uid_do_evento: str,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    evento_node = agenda_ref.child(uid_da_agenda).child("eventos").child(uid_do_evento)
    evento_data = evento_node.get()
    if not evento_data:
        raise HTTPException(
            status_code=404,
            detail=f"O evento com o UID {uid_do_evento} na agenda {uid_da_agenda} não existe",
        )

    evento_node.delete()

    return {"message": f"O evento com o UID {uid_do_evento} foi deletado com sucesso."}


@app.patch("/update/agenda", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def atualizar_os_dados_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    nome_agenda: Annotated[str | None, Query()] = None,
    uid_do_responsavel: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = agenda_ref.child(uid_da_agenda)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404, detail=f"A agenda com o UID {uid_da_agenda} não existe"
        )

    update_data = {}
    if nome_agenda is not None:
        update_data["nome_agenda"] = nome_agenda
    if uid_do_responsavel is not None:
        update_data["uid_do_responsável"] = uid_do_responsavel

    if not update_data:
        raise HTTPException(
            status_code=400, detail="Nenhum dado fornecido para atualização"
        )

    agenda_node.update(update_data)

    return {"message": "Agenda atualizada com sucesso", "dados": update_data}


@app.patch("/update/agenda/materia", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def atualizar_as_matérias_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    uid_da_materia: Annotated[str, Query(...)],
    nome_da_matéria: Annotated[str | None, Query()] = None,
    nome_do_professor: Annotated[str | None, Query()] = None,
    horario_de_inicio_da_materia: Annotated[str | None, Query()] = None,
    horario_de_fim_da_materia: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = (
        agenda_ref.child(uid_da_agenda).child("matérias").child(uid_da_materia)
    )
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404,
            detail=f"A matéria com o UID {uid_da_materia} na agenda {uid_da_agenda} não existe",
        )

    update_data = {}
    if nome_da_matéria is not None:
        update_data["nome_matéria"] = nome_da_matéria
    if nome_do_professor is not None:
        update_data["professor"] = nome_do_professor
    if horario_de_inicio_da_materia is not None:
        update_data["horario_de_início"] = horario_de_inicio_da_materia
    if horario_de_fim_da_materia is not None:
        update_data["horario_de_fim"] = horario_de_fim_da_materia

    if not update_data:
        raise HTTPException(
            status_code=400, detail="Nenhum dado fornecido para atualização"
        )

    agenda_node.update(update_data)

    return {"message": "Agenda atualizada com sucesso", "dados": update_data}


@app.patch("/update/agenda/tarefa", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def atualizar_as_tarefas_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    uid_da_tarefa: Annotated[str, Query(...)],
    nome_da_tarefa: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = agenda_ref.child(uid_da_agenda).child("tarefas").child(uid_da_tarefa)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404,
            detail=f"A tarefa com o UID {uid_da_tarefa} na agenda {uid_da_agenda} não existe",
        )

    timestamp_definido = timestamp_formatado(datetime.now())

    update_data = {}
    if nome_da_tarefa is not None:
        update_data["nome_da_tarefa"] = nome_da_tarefa
    if timestamp_definido is not None:
        update_data["timestamp"] = timestamp_definido

    if not update_data:
        raise HTTPException(
            status_code=400, detail="Nenhum dado fornecido para atualização"
        )

    agenda_node.update(update_data)

    return {"message": "Agenda atualizada com sucesso", "dados": update_data}


@app.patch("/update/agenda/evento", tags=["Agenda"], responses=STANDARD_RESPONSES)
async def atualizar_os_eventos_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    uid_do_evento: Annotated[str, Query(...)],
    nome_do_evento: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
):
    agenda_node = agenda_ref.child(uid_da_agenda).child("eventos").child(uid_do_evento)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404,
            detail=f"O evento com o UID {uid_do_evento} na agenda {uid_da_agenda} não existe",
        )

    timestamp_definido = timestamp_formatado(datetime.now())

    update_data = {}
    if nome_do_evento is not None:
        update_data["nome_do_evento"] = nome_do_evento
    if timestamp_definido is not None:
        update_data["timestamp"] = timestamp_definido

    if not update_data:
        raise HTTPException(
            status_code=400, detail="Nenhum dado fornecido para atualização"
        )

    agenda_node.update(update_data)

    return {"message": "Agenda atualizada com sucesso", "dados": update_data}


@app.get("/blob/getAll", tags=["S3"], responses=STANDARD_RESPONSES)
def list_all_blobs(api_key: Annotated[str | None, Depends(get_api_key)] = None):
    return vercel_blob.list()


@app.post("/blob/uploadFile", tags=["S3"], responses=STANDARD_RESPONSES)
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    api_key: Annotated[str | None, Depends(get_api_key)] = None,
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


@app.delete("/blob/deleteFile", tags=["S3"], responses=STANDARD_RESPONSES)
async def delete_blob(
    url: str, api_key: Annotated[str | None, Depends(get_api_key)] = None
):
    try:
        vercel_blob.delete(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": url}
