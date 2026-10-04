"""
Configurações do projeto Polis.

Nada de segredo (chave secreta, senha de banco etc) fica escrito aqui —
tudo isso vem de variáveis de ambiente, lidas do arquivo .env em
desenvolvimento e definidas direto no painel do host (Railway/Render) em
produção. Veja o .env.example na raiz do projeto.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

_INSECURE_DEV_KEY = "django-insecure-troque-isso-antes-de-ir-pra-producao"
SECRET_KEY = os.environ.get("SECRET_KEY", _INSECURE_DEV_KEY)

# DEBUG=True só em desenvolvimento local. Em produção, defina DEBUG=False
# nas variáveis de ambiente do host.
DEBUG = os.environ.get("DEBUG", "True") == "True"

if not DEBUG and SECRET_KEY == _INSECURE_DEV_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Defina SECRET_KEY no ambiente quando DEBUG=False.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps do jogo
    "accounts",
    "core",  # motor do jogo: tempo, ticks, (futuro) Action Registry e auditoria
    "players",  # estado do jogador: energia, QoL, saúde, nutrição, burnout
    "skills",  # Inteligência, Físico e Carisma (design/01) e Especialização (02 §13)
    "geography",  # Estado → Cidade → Bairro → Lote, zoneamento e recursos (design/08)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "polis.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "polis.wsgi.application"


# Banco de dados.
# Em desenvolvimento local, sem DATABASE_URL configurada, cai pra sqlite
# (zero configuração pra começar). Em produção, defina DATABASE_URL com a
# string de conexão do Postgres (o Railway/Render já geram isso sozinhos).
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_USER_MODEL = "accounts.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Motor de tempo (core) ---------------------------------------------
# O tempo do jogo é o tempo real (segundos, dias e meses de calendário), na
# PRÓPRIA time zone do jogo, nunca na do usuário. Só a velocidade é acelerável.
POLIS_GAME_TIMEZONE = os.environ.get("POLIS_GAME_TIMEZONE", TIME_ZONE)

# Segundos REAIS que duram 1 dia de JOGO. 86400 = tempo real (produção).
# Bot Test: 600 (1 dia = 10 min, design/21 §21.3). Só vale ao criar o relógio do
# mundo; depois o valor vive no banco (`manage.py world_clock set-speed`).
POLIS_REAL_SECONDS_PER_GAME_DAY = int(os.environ.get("POLIS_REAL_SECONDS_PER_GAME_DAY", "86400"))
