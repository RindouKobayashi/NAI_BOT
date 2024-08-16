import pathlib
import os
import discord
import logging
import asyncio
import csv
import uuid
import copy

from dotenv import load_dotenv
from logging.config import dictConfig

load_dotenv()
branch = os.getenv("GITHUB_BRANCH", 'main')
if branch == 'dev':
    DISCORD_API_TOKEN = os.getenv("DISCORD_API_TOKEN_TEST")
    TO_DATABASE = False
else:
    DISCORD_API_TOKEN = os.getenv("DISCORD_API_TOKEN")
    TO_DATABASE = True
NAI_EMAIL = os.getenv("NAI_EMAIL")
NAI_PASSWORD = os.getenv("NAI_PASSWORD")
NAI_API_TOKEN = os.getenv("NAI_API_TOKEN")

BASE_DIR = pathlib.Path(__file__).parent
COGS_DIR = BASE_DIR / "cogs"
DATABASE_DIR = BASE_DIR / "database"
USER_VIBE_TRANSFER_DIR = DATABASE_DIR / "user_vibe_transfer"

CHANNEL_ID_TEST = 1188501454806339685
SERVER_ID_TEST = 1157816835975151706

IMAGE_GEN_BOT_CHANNEL = 1261084844230705182
ANIMEAI_SERVER = 1024739383124963429

DATABASE_CHANNEL_ID = 1268976168233599117

BOT_OWNER_ID = 125331697867816961

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)-10s - %(asctime)s - %(module)-15s : %(message)s",
        },
        "standard": {
            "format": "%(levelname)-10s - %(name)-15s : %(message)s",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "console2": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/infos.log",
            "formatter": "verbose",
            "mode": "w",
            "encoding": "utf-8",
        },        
    },
    "loggers": {
        "bot": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "discord": {
            "handlers": ["console2", "file"],
            "level": "INFO",
            "propagate": False
        }
    }
}

logger = logging.getLogger("bot")

dictConfig(LOGGING_CONFIG)

AUTOCOMPLETE_DATA = []

with open("danbooru.csv", newline="", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        keyword = row[0].strip()
        # remove _ from keyword
        keyword = keyword.replace("_", " ")
        AUTOCOMPLETE_DATA.append(keyword)  # Store just the keyword

#logger.info(f"AUTOCOMPLETE_DATA: {AUTOCOMPLETE_DATA}")

class Globals:
    remix_views = {}
    select_views = {}
    select_views_generation_data = {}