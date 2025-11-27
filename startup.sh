#!/bin/bash

# Fail fast
set -e

# Garante que estamos na raiz do código
cd /home/site/wwwroot

# Só para diagnóstico (não quebra se falhar)
echo "Conteúdo de /home/site/wwwroot:"
ls -R

# Sobe a API FastAPI usando Gunicorn + UvicornWorker
# OBS: o módulo é api.main:app (porque seu main.py está dentro da pasta api)
gunicorn -k uvicorn.workers.UvicornWorker \
  -w 4 \
  -b 0.0.0.0:8000 \
  api.main:app
