@echo off
REM ====================================================
REM  CodeNova - run AI (FastAPI:8001) + Web (Django:8000)
REM ====================================================

REM --- conda env names (edit these) ---
set AI_ENV=apichat
set WEB_ENV=apichat

set ROOT=%~dp0

start "CodeNova-AI 8001" cmd /k "cd /d %ROOT%ai && call conda activate %AI_ENV% && uvicorn main:app --reload --port 8001"

start "CodeNova-Web 8000" cmd /k "cd /d %ROOT%web && call conda activate %WEB_ENV% && python manage.py runserver 0.0.0.0:8000"
