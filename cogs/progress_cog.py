import discord
import aiohttp
import settings
import io
import base64
from PIL import Image
from settings import logger
from discord.ext import commands

class progress(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot





async def setup(bot: commands.Bot):
    await bot.add_cog(progress(bot))
    logger.info("COG LOADED: progress - COG FILE: progress_cog.py")