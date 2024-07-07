import discord
import settings
from discord.ext import commands
from settings import logger



# Discord Bot Permission
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def run():
    
    @bot.event
    async def on_ready():
        logger.info(f"User: {bot.user} (ID: {bot.user.id})")

        # load cogs from cog 
        for cof_file in settings.COGS_DIR.glob("*.py"):
            if cof_file.name != "__init__.py":
                await bot.load_extension(f"cogs.{cof_file.name[:-3]}")

        # Change presence 
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="you"))


    bot.run(settings.DISCORD_API_TOKEN, root_logger=True)

if __name__ == "__main__":
    run()