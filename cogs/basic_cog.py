import discord
import settings
import asyncio
from settings import logger
from discord import app_commands
from discord.ext import commands

class basic(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        

    @app_commands.command(name="sync", description="Force sync")
    async def sync(self, interaction: discord.Interaction):
        logger.info(f"COMMAND 'SYNC' USED BY: {interaction.user} ({interaction.user.id})")
        # Check if user is owner of bot
        if interaction.user.id != 125331697867816961:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        await interaction.response.send_message("Syncing...", ephemeral=True, delete_after=30)
        await self.bot.tree.sync()
        await interaction.edit_original_response(content="Synced")

    @app_commands.command(name="ping", description="Ping the bot")
    async def ping(self, interaction: discord.Interaction):
        logger.info(f"COMMAND 'PING' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"Pong! ``{round(self.bot.latency * 1000)}ms``", delete_after=10)

    @app_commands.command(name="help", description="Show a list of commands")
    async def help(self, interaction: discord.Interaction):
        """Show a list of commands"""
        logger.info(f"COMMAND 'HELP' USED BY: {interaction.user} ({interaction.user.id})")
        # send list of commands
        command_lists = [f"``{command.name}`` - ``{command.description}``" for command in self.bot.tree.walk_commands()]
        commands_str = "\n".join(command_lists)
        embed = discord.Embed(
            title="Available Commands",
            description=commands_str,
            timestamp=discord.utils.utcnow(),
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="shutdown", description="Shutdown the bot")
    async def shutdown(self, interaction: discord.Interaction, time: int = 30):
        """Shutdown the bot"""
        logger.info(f"COMMAND 'SHUTDOWN' USED BY: {interaction.user} ({interaction.user.id})")
        # Check if user is owner of bot
        if interaction.user.id != 125331697867816961:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        await interaction.response.send_message(f"Shutting down in ``{time}`` seconds...")
        for second in range(time, -10, -1):
            await interaction.edit_original_response(content=f"Shutting down in ``{second}`` seconds...")
            await asyncio.sleep(1)
            if second == 0:
                await interaction.edit_original_response(content="Shutting down...")
                break
        channel = self.bot.get_channel(interaction.channel.id)
        await interaction.delete_original_response()
        #message = await interaction.edit_original_response(content="Bye bye world!")
        #await message.add_reaction("<:agony:1161203375598223370>")
        message = await channel.send(f"Bye bye world!")
        message = await message.add_reaction("<:agony:1161203375598223370>")
        await self.bot.close()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Check if reaction is 🗑️, if it's in certain channel and message by bot, if yes, delete it"""

        # Check if bot is reacting
        if payload.user_id == self.bot.user.id:
            return
        
        # Check payload.message's mentions
        message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
        if not message.mentions:
            return
        
        # Original command author
        original_user = message.mentions[0]

        # Check if it's the original command author
        if original_user.id != payload.user_id:
            return

        # Check if it's in the correct channel (replace with your actual channel ID)
        if payload.channel_id != 1261084844230705182:
            return

        # Check if reaction is 🗑️
        if payload.emoji.name != "🗑️":
            return
        
        # Delete message
        await message.delete()

        

    

async def setup(bot: commands.Bot):
    await bot.add_cog(basic(bot))
    logger.info("COG LOADED: basic - COG FILE: basic_cog.py")