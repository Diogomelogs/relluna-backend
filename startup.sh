#!/bin/bash
python -m pip install --upgrade pip
pip install -r requirements.txt
gunicorn -k uvicorn.workers.UvicornWorker main:app --bind=0.0.0.0:8000
