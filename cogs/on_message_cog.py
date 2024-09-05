import discord
import settings
from settings import logger
from discord.ext import commands

class ON_MESSAGE(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.author.id == self.bot.owner_id:
            return
        # Check if talking in database_2
        if message.channel.id == settings.DATABASE_CHANNEL_2_ID:
            await message.reply("**Please do not talk in the database, stooopid**", mention_author=True, delete_after=10)
            await message.delete()


async def setup(bot: commands.Bot):
    await bot.add_cog(ON_MESSAGE(bot))
    logger.info("COG LOADED: ON_MESSAGE - COG FILE: on_message_cog.py")