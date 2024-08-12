import discord
import settings
import asyncio
import aiohttp
from settings import logger, AUTOCOMPLETE_DATA
from discord import app_commands
from discord.ext import commands

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

    @app_commands.command(name="how_to_vibe_transfer", description="How to vibe transfer")
    async def vibe_transfer(self, interaction: discord.Interaction):
        """How to vibe transfer"""
        logger.info(f"COMMAND 'How_to_vibe_transfer' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"For vibe transfer: please use vibe_transfer command. You are allowed 5 images with their values. All of these will be stored as base64 strings and corresponding values in json. When using nai command, you can use vibe_transfer_switch to true to auto retrieve your own vibe transfer data.", ephemeral=True)


    """
    # A test command that check against AUTOCOMPLETE_DATA
    @app_commands.command(name="search", description="Search with multiple independent terms")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.send_message(f"You searched for: {query}")

    @search.autocomplete('query')
    async def search_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        def search_current_term(query):
            terms = query.split(',')
            current_term = terms[-1].strip().lower()
            
            if not current_term:
                return []

            results = [
                item for item in AUTOCOMPLETE_DATA
                if item.lower().startswith(current_term)
            ]
    
            return results[:25]  # Limit to 25 results as per Discord's limit

        results = await asyncio.to_thread(search_current_term, current)
        
        # Prepare the choices, including the parts of the query that are already typed
        prefix = ','.join(current.split(',')[:-1]).strip()
        if prefix:
            prefix += ', '
        
        valid_choices = [
            app_commands.Choice(name=f"{prefix}{item}"[:100], value=f"{prefix}{item}")
            for item in results
            if len(item) > 0  # Ensure item is not empty
        ]
        
        return valid_choices
    """

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

        
        


    

async def setup(bot: commands.Bot):
    await bot.add_cog(BASIC(bot))
    logger.info("COG LOADED: BASIC - COG FILE: basic_cog.py")