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


@router.get("/getAllAgendas")
async def mostrar_todas_as_agendas_criadas(
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
):
    if agenda_ref.get() is None:
        return {"message": "Nenhuma agenda foi criada"}
    else:
        return agenda_ref.get()


@router.get("/getAllAgendasLinkedToUser")
async def mostrar_todas_as_agendas_que_o_usuário_faz_parte(
    uid_do_responsavel: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.get("/getAllTarefasFromOneAgenda")
async def mostrar_todas_as_tarefas_dentro_de_uma_agenda(
    uid_da_agenda: str, api_key: Annotated[str | None, Depends(check_api_key)] = None
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


@router.get("/getAllMembrosFromOneAgenda")
async def mostrar_todos_os_membros_dentro_de_uma_agenda(
    uid_da_agenda: str, api_key: Annotated[str | None, Depends(check_api_key)] = None
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


@router.post("/add/agenda")
async def criar_uma_agenda(
    nome_agenda: str,
    uid_do_responsavel: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.post("/add/agenda/membro")
async def adicionar_um_membro_na_agenda_já_criada(
    uid_da_agenda: str,
    uid_do_membro: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.post("/add/agenda/materia")
async def criar_uma_materia_na_agenda_já_criada(
    uid_da_agenda: str,
    nome_da_matéria: str,
    nome_do_professor: str | None = None,
    horario_de_inicio_da_materia: str | None = None,
    horario_de_fim_da_materia: str | None = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.post("/add/agenda/tarefa")
async def criar_uma_tarefa_na_agenda_já_criada(
    uid_da_agenda: str,
    nome_da_tarefa: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.post("/add/agenda/evento")
async def criar_um_evento_na_agenda_já_criada(
    uid_da_agenda: str,
    nome_do_evento: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.delete("/delete/agenda")
async def deletar_uma_agenda_com_o_uid(
    uid_da_agenda: str, api_key: Annotated[str | None, Depends(check_api_key)] = None
):
    agenda_node = agenda_ref.child(uid_da_agenda)
    agenda_data = agenda_node.get()
    if not agenda_data:
        raise HTTPException(
            status_code=404, detail=f"A agenda com o UID {uid_da_agenda} não existe"
        )

    agenda_node.delete()

    return {"message": f"A agenda com o UID {uid_da_agenda} foi deletada com sucesso."}


@router.delete("/delete/agenda/membro")
async def deletar_um_membro_na_agenda(
    uid_da_agenda: str,
    uid_do_membro: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.delete("/delete/agenda/materia")
async def deletar_uma_materia_com_o_uid(
    uid_da_agenda: str,
    uid_da_materia: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.delete("/delete/agenda/tarefa")
async def deletar_uma_tarefa_com_o_uid(
    uid_da_agenda: str,
    uid_da_tarefa: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.delete("/delete/agenda/evento")
async def deletar_um_evento_com_o_uid(
    uid_da_agenda: str,
    uid_do_evento: str,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.patch("/update/agenda")
async def atualizar_os_dados_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    nome_agenda: Annotated[str | None, Query()] = None,
    uid_do_responsavel: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.patch("/update/agenda/materia")
async def atualizar_as_matérias_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    uid_da_materia: Annotated[str, Query(...)],
    nome_da_matéria: Annotated[str | None, Query()] = None,
    nome_do_professor: Annotated[str | None, Query()] = None,
    horario_de_inicio_da_materia: Annotated[str | None, Query()] = None,
    horario_de_fim_da_materia: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.patch("/update/agenda/tarefa")
async def atualizar_as_tarefas_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    uid_da_tarefa: Annotated[str, Query(...)],
    nome_da_tarefa: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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


@router.patch("/update/agenda/evento")
async def atualizar_os_eventos_da_agenda(
    uid_da_agenda: Annotated[str, Query(...)],
    uid_do_evento: Annotated[str, Query(...)],
    nome_do_evento: Annotated[str | None, Query()] = None,
    api_key: Annotated[str | None, Depends(check_api_key)] = None,
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
