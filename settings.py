import pathlib
import os
import discord
import logging
import asyncio
import csv
import uuid
import copy
import random

from dotenv import load_dotenv
from logging.config import dictConfig

load_dotenv()

branch = os.getenv("GITHUB_BRANCH", 'main')

CHANGELOG = "Added model `nai-diffusion-4-5-curated`"
    
if branch == 'dev':
    DISCORD_API_TOKEN = os.getenv("DISCORD_API_TOKEN_TEST")
    TO_DATABASE = False
else:
    DISCORD_API_TOKEN = os.getenv("DISCORD_API_TOKEN")
    TO_DATABASE = True
NAI_EMAIL = os.getenv("NAI_EMAIL")
NAI_PASSWORD = os.getenv("NAI_PASSWORD")
NAI_API_TOKEN = os.getenv("NAI_API_TOKEN")

HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
WD_TAGGER_URL = "SmolRabbit/wd-tagger"

BASE_DIR = pathlib.Path(__file__).parent
COGS_DIR = BASE_DIR / "cogs"
DATABASE_DIR = BASE_DIR / "database"
USER_VIBE_TRANSFER_DIR = DATABASE_DIR / "user_vibe_transfer"
USER_NAI_PRESETS_DIR = DATABASE_DIR / "user_nai_presets"
USER_NAI_PRESETS_DIR.mkdir(exist_ok=True)

# Stats directories
STATS_DIR = DATABASE_DIR / "stats"
USER_STATS_DIR = STATS_DIR / "user_stats"
GLOBAL_STATS_DIR = STATS_DIR / "global_stats"
STATS_DIR.mkdir(exist_ok=True)
USER_STATS_DIR.mkdir(exist_ok=True)
GLOBAL_STATS_DIR.mkdir(exist_ok=True)

STATS_JSON = DATABASE_DIR / "stats.json"

CHANNEL_ID_TEST = 1188501454806339685
SERVER_ID_TEST = 1157816835975151706

IMAGE_GEN_BOT_CHANNEL = 1261084844230705182
SFW_IMAGE_GEN_BOT_CHANNEL = 1280389884745482313
ANIMEAI_SERVER = 1024739383124963429

DATABASE_CHANNEL_ID = 1268976168233599117 # Private channel
DATABASE_CHANNEL_2_ID = 1281127284857634826 # Slightly public channel

PROJECT_AI_SERVER = 930499730843250783

BOT_OWNER_ID = 125331697867816961

SERVER_WHITELIST = [SERVER_ID_TEST, ANIMEAI_SERVER, 1125398871904891072, 1295481194301100173, PROJECT_AI_SERVER, 1321349223232569477]

# Define custom formatter for colored console output
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[94m',    # Blue
        'INFO': '\033[92m',     # Green
        'WARNING': '\033[93m',  # Yellow
        'ERROR': '\033[91m',    # Red
        'CRITICAL': '\033[95m', # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)-10s - %(asctime)s - %(module)-15s : %(message)s",
        },
        "standard": {
            "format": "%(levelname)-10s - %(name)-15s : %(message)s",
        },
        "colored": {
            "()": ColoredFormatter,
            "format": "%(levelname)-10s - %(name)-15s : %(message)s",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "colored",
            "stream": "ext://sys.stdout",
        },
        "console2": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "colored",
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
