import discord
import settings
import asyncio
import aiohttp
from settings import logger, AUTOCOMPLETE_DATA
from discord import app_commands
from discord.ext import commands
import json

class BASIC(commands.Cog):
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
    async def shutdown(self, interaction: discord.Interaction, time: int = 30, reason:str = None):
        """Shutdown the bot"""
        logger.info(f"COMMAND 'SHUTDOWN' USED BY: {interaction.user} ({interaction.user.id})")
        # Check if user is owner of bot
        if interaction.user.id != 125331697867816961:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        await interaction.response.send_message("Shutting down...", ephemeral=True, delete_after=time)
        await asyncio.sleep(time)
        from main import shutdown_tasks
        await shutdown_tasks()
        await self.bot.close()

    @app_commands.command(name="how_to_vibe_transfer", description="How to vibe transfer")
    async def vibe_transfer(self, interaction: discord.Interaction):
        """How to vibe transfer"""
        logger.info(f"COMMAND 'How_to_vibe_transfer' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"For vibe transfer: please use vibe_transfer command. You are allowed 5 images with their values. All of these will be stored as base64 strings and corresponding values in json. When using nai command, you can use vibe_transfer_switch to true to auto retrieve your own vibe transfer data.", ephemeral=True)


    @app_commands.command(name="whois", description="Get information about a user")
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

    @app_commands.command(name="installed_users", description="List all installed users")
    async def installed_users(self, interaction: discord.Interaction):
        """List all installed users"""
        if interaction.user.id != 125331697867816961:
            await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=True)
            return
        logger.info(f"COMMAND 'INSTALLED_USERS' USED BY: {interaction.user} ({interaction.user.id})")
        url = "https://discord.com/api/v10/applications/@me"

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bot {settings.DISCORD_API_TOKEN}"
            }
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    install_users = data.get("approximate_user_install_count")
                    await interaction.response.send_message(f"Installed users: {install_users}")
                else:
                    await interaction.response.send_message(f"Failed to get installed users. Status code: {response.status}", ephemeral=True)

    @app_commands.command(name="feedback", description="Send feedback/suggestions to the bot owner")
    async def feedback(self, interaction: discord.Interaction, feedback: str):
        """Send feedback to the bot owner"""
        logger.info(f"COMMAND 'FEEDBACK' USED BY: {interaction.user} ({interaction.user.id})")
        # Send feedback to the bot owner via dm
        bot_owner = self.bot.get_user(settings.BOT_OWNER_ID)
        await bot_owner.send(f"Feedback from {interaction.user} : `{feedback}`\nLink to person: [{interaction.user.display_name}](<https://discord.com/users/{interaction.user.id}>) ")
        await interaction.response.send_message("Thank you for your feedback!", ephemeral=True, delete_after=20)

    @app_commands.command(name="stats", description="Shows how much NAI generations you have done")
    async def stats(self, interaction: discord.Interaction, ephemeral: bool = True):
        """Shows how much NAI generations you have done"""
        logger.info(f"COMMAND 'STATS' USED BY: {interaction.user} ({interaction.user.id})")
        # Get stats from json file
        with open(settings.STATS_JSON, "r") as f:
            stats = json.load(f)
        # Sort users by generation count to determine ranking
        sorted_users = sorted(stats.items(), key=lambda x: int(x[1]), reverse=True)
        
        # Find user's rank
        user_stats = stats.get(str(interaction.user.id), 0)
        user_rank = None
        for index, (user_id, count) in enumerate(sorted_users, 1):
            if user_id == str(interaction.user.id):
                user_rank = index
                break
        
        # Get info about next rank
        rank_text = ""
        if user_rank:
            rank_text = f" (Rank `#{user_rank}`)"
            if user_rank > 1:  # If not rank 1, show generations needed for next rank
                next_rank_user, next_rank_count = sorted_users[user_rank - 2]  # -2 because rank is 1-based and we want previous index
                if int(next_rank_count) == int(user_stats):
                    rank_text += f"\nYou are tied for rank `#{user_rank - 1}`. You need `1` more generation to overtake!"
                else:
                    gens_needed = int(next_rank_count) - int(user_stats) + 1
                    rank_text += f"\nYou need `{gens_needed}` more generations to overtake rank `#{user_rank - 1}`"
        
        await interaction.response.send_message(f"You have done `{user_stats}` NAI generations{rank_text}.", ephemeral=ephemeral)
        


    

async def setup(bot: commands.Bot):
    await bot.add_cog(BASIC(bot))
