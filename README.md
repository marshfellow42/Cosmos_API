# Cosmos API

A API do nosso aplicativo Cosmos

Para rodar, primeiro você precisa instalar o [uv](https://docs.astral.sh/uv/getting-started/installation/)

Depois de baixar o uv na sua máquina, só rodar o comando na pasta do seu projeto
```bash
uv sync
```

E depois só rodar ele
```bash
uv run fastapi dev main.py
```

Para checar se tudo deu certo, é só checar a UI do Swagger
```
http://localhost:8000/docs
```