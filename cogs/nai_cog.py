import discord
from settings import logger
from discord import app_commands
from discord.ext import commands

class nai(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @app_commands.command(name="nai", description="Nai")
    async def nai(self, interaction: discord.Interaction):
        pass



async def setup(bot: commands.Bot):
    await bot.add_cog(nai(bot))
    logger.info("COG LOADED: nai - COG FILE: nai_cog.py")