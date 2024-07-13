import pathlib
import os
import discord
import logging
import asyncio

from dotenv import load_dotenv
from logging.config import dictConfig

load_dotenv()

DISCORD_API_TOKEN = os.getenv("DISCORD_API_TOKEN")
NAI_EMAIL = os.getenv("NAI_EMAIL")
NAI_PASSWORD = os.getenv("NAI_PASSWORD")
NAI_API_TOKEN = os.getenv("NAI_API_TOKEN")

BASE_DIR = pathlib.Path(__file__).parent
COGS_DIR = BASE_DIR / "cogs"
DATABASE_DIR = BASE_DIR / "database"

CHANNEL_ID_TEST = 1188501454806339685
SERVER_ID_TEST = 1157816835975151706

CHANNEL_ID = 1261084844230705182
SERVER_ID = 1024739383124963429

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