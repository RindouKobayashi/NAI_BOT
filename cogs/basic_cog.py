import discord
import settings
import asyncio
import aiohttp
import subprocess
import sys
import os
from pathlib import Path
from settings import logger, AUTOCOMPLETE_DATA
from discord import app_commands
from core.shutdown_utils import shutdown_tasks
from discord.ext import commands
import json
from core.viewhandler import Globals
import settings

# Build a list of discord.Object instances
_allowed_guilds = [discord.Object(id=guild_id) for guild_id in settings.DEVELOPER_SERVERS_LIST]

class BASIC(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sync", description="Force sync")
    @app_commands.guilds(*_allowed_guilds)
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
    @app_commands.guilds(*_allowed_guilds)
    async def shutdown(self, interaction: discord.Interaction, time: int = 30, reason:str = None, restart: bool = False, update: bool = False):
        """Shutdown the bot"""
        logger.warning(f"COMMAND 'SHUTDOWN' USED BY: {interaction.user} ({interaction.user.id})")
        # Check if user is owner of bot
        if interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        if time <= 1:
            await interaction.response.send_message("Time must be greater than 1 second.", ephemeral=True)
            return
        if not restart and not update:
            await interaction.response.send_message(f"Shutting down in {time} seconds. Reason: `{reason if reason else 'No reason provided.'}`", ephemeral=True, delete_after=time-1)
        else:
            await interaction.response.send_message(f"Restarting in {time} seconds. Reason: `{reason if reason else 'No reason provided.'}`", ephemeral=True, delete_after=time-1)
        # Check for active views and notify users
        active_views_messages = []
        if Globals.select_views_generation_data:
            for request_id, bundle_data in Globals.select_views_generation_data.items():
                if isinstance(bundle_data, dict) and "message" in bundle_data and bundle_data["message"] is not None:
                    active_views_messages.append(bundle_data["message"])
        if Globals.remix_views:
             for request_id, view in Globals.remix_views.items():
                 if hasattr(view, 'bundle_data') and isinstance(view.bundle_data, dict) and "message" in view.bundle_data and view.bundle_data["message"] is not None:
                     active_views_messages.append(view.bundle_data["message"])

        # Create reply_content
        reply_content = ""

        # Check if restart or update is requested
        if restart or update:
            reply_content = f"{interaction.user.mention} Bot is restarting. Reason: `{reason if reason else 'No reason provided.'}`"

        else:
            reply_content = f"{interaction.user.mention} Bot is shutting down. Reason: `{reason if reason else 'No reason provided.'}`"

        # Check if there are active views and notify users
        if active_views_messages:
            reply_content += "\n-# Message will self-destruct upon bot shutdown."
            # Use a set to avoid replying to the same message multiple times
            unique_messages = set(active_views_messages)
            for message in unique_messages:
                try:
                    message: discord.Message
                    await message.reply(reply_content, delete_after=time-1)
                except Exception as e:
                    logger.error(f"Failed to reply to message {message.id} for shutdown notification: {e}")

        if update:
            logger.info("Attempting git pull for update...")
            try:
                # Execute git pull command
                # Note: This command will be executed in the current working directory: c:/Users/User/OneDrive/Desktop/NAI_BOT
                # If your git repository is in a different directory, you'll need to adjust the command
                # e.g., `cd /path/to/your/repo && git pull`
                git_pull_result = await asyncio.create_subprocess_shell(
                    "git pull",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await git_pull_result.communicate()
                # close the subprocess
                await git_pull_result.wait()

                if git_pull_result.returncode == 0:
                    logger.info("Git pull successful.")
                    if stdout:
                        logger.debug(f"Git pull stdout:\n{stdout.decode().strip()}")
                else:
                    logger.error(f"Git pull failed with return code {git_pull_result.returncode}.")
                    if stdout:
                        logger.error(f"Git pull stdout:\n{stdout.decode().strip()}")
                    if stderr:
                        logger.error(f"Git pull stderr:\n{stderr.decode().strip()}")

            except FileNotFoundError:
                logger.error("Git command not found. Is Git installed and in your PATH?")
            except Exception as e:
                logger.error(f"An error occurred during git pull: {e}")

        await asyncio.sleep(time)

        if restart:
            try:
                logger.info("Attempting to restart bot...")
                # Get the absolute path to restart.py using pathlib for cross-platform compatibility
                restart_script = Path(__file__).parent.parent / "restart.py"
                
                # Execute restart script with the current venv Python
                env = os.environ.copy()
                # Log the Python interpreter being used
                logger.debug(f"Using Python interpreter: {sys.executable}")
                subprocess.Popen(
                    [sys.executable, str(restart_script)],
                    env=env
                )
                logger.debug("Restart script executed successfully")
            except Exception as e:
                logger.error(f"Failed to restart bot: {e}")
                logger.exception("Full traceback:")

        # Small delay to ensure restart process starts
        if restart:
            await asyncio.sleep(1)
        
        # Close the bot
        await self.bot.close()


    @app_commands.command(name="how_to_vibe_transfer", description="How to vibe transfer")
    async def vibe_transfer(self, interaction: discord.Interaction):
        """How to vibe transfer"""
        logger.info(f"COMMAND 'How_to_vibe_transfer' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"For vibe transfer: please use vibe_transfer command. You are allowed 5 images with their values. All of these will be stored as base64 strings and corresponding values in json. When using nai command, you can use vibe_transfer_switch to true to auto retrieve your own vibe transfer data.", ephemeral=True)


    @app_commands.command(name="whois", description="Get information about a user")
    @app_commands.guilds(*_allowed_guilds)
    async def whois(self, interaction: discord.Interaction, user: discord.User = None):
        """Get information about a user"""
        logger.info(f"COMMAND 'WHOIS' USED BY: {interaction.user} ({interaction.user.id})")
        if user is None:
            user = interaction.user
        
        # Create embed to display information
        embed = discord.Embed(
            title=f"Information about {user.name}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="ID", value=f"`{user.id}`", inline=False)
        embed.add_field(name="Created Account On: ", value=f"`{user.created_at.strftime('%Y-%m-%d %H:%M:%S')}`", inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="feedback", description="Send feedback/suggestions to the bot owner")
    async def feedback(self, interaction: discord.Interaction, feedback: str):
        """Send feedback to the bot owner"""
        logger.info(f"COMMAND 'FEEDBACK' USED BY: {interaction.user} ({interaction.user.id})")
        # Send feedback to the bot owner via dm
        bot_owner = self.bot.get_user(settings.BOT_OWNER_ID)
        await bot_owner.send(f"Feedback from {interaction.user} : `{feedback}`\nLink to person: [{interaction.user.display_name}](<https://discord.com/users/{interaction.user.id}>) ")
        await interaction.response.send_message("Thank you for your feedback!", ephemeral=True, delete_after=20)

    @app_commands.command(name="status", description="Get the bot's status")
    @app_commands.guilds(*_allowed_guilds)
    async def status(self, interaction: discord.Interaction):
        """Get the bot's status"""
        logger.info(f"COMMAND 'STATUS' USED BY: {interaction.user} ({interaction.user.id})")
        if interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        # Get the bot's status
        # aline the status
        status = {
            "uptime": f"{round((discord.utils.utcnow() - self.bot.start_time).total_seconds() / 60)} minutes",
            "latency": f"{round(self.bot.latency * 1000)} ms",
            "guilds": len(self.bot.guilds),
            "users": len(set(self.bot.get_all_members())),
            "cogs": len(self.bot.cogs),
            "version": self.bot.current_version,
        }
        # Get application info
        app_info = await self.bot.application_info()
        status["installed_users"] = app_info.approximate_user_install_count
        status["installed_guilds"] = app_info.approximate_guild_count
        await interaction.response.send_message(f"Bot Status:\n```json\n{json.dumps(status, indent=4)}\n```", ephemeral=True)

    @app_commands.command(name="logs", description="Get the bot's logs")
    @app_commands.guilds(*_allowed_guilds)
    async def logs(self, interaction: discord.Interaction, lines: int = 0):
        """Get the bot's logs"""
        logger.info(f"COMMAND 'LOGS' USED BY: {interaction.user} ({interaction.user.id})")
        if interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        # Read the log file
        log_file_path = "logs/infos.log"

        # if lines is 0 or less, send the whole log as file
        if lines <= 0:
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as f:
                    log_content = f.read()
                await interaction.response.send_message(file=discord.File(log_file_path, filename="logs.txt"), ephemeral=True)
            else:
                await interaction.response.send_message("Log file not found.", ephemeral=True)

        else:
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as f:
                    lines_content = f.readlines()
                # Get the last 'lines' lines
                last_lines = ''.join(lines_content[-lines:])
                await interaction.response.send_message(f"```{last_lines}```", ephemeral=True)
            else:
                await interaction.response.send_message("Log file not found.", ephemeral=True)
        

        
    

async def setup(bot: commands.Bot):
    await bot.add_cog(BASIC(bot))
