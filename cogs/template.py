import discord
from discord.ext import commands
from discord import app_commands
import settings # Assuming settings.py is used for configuration/logging

# Cog File Naming Convention: [cog_name]_cog.py
# The bot loads files ending with '_cog.py' from the 'cogs' directory.
# The extension name used for loading is the filename without the '.py' extension.

# Define your cog class, inheriting from commands.Cog
class TemplateCog(commands.Cog):
    """
    A template cog for demonstrating how to structure a cog.
    Replace 'TemplateCog' with the desired name for your cog.
    """
    def __init__(self, bot: commands.Bot):
        # Store the bot instance
        self.bot = bot
        # You can initialize other attributes here
        # For example: self.some_value = 0
        # Or load data: self.data = self.load_data()

        # If you have tasks that need to run periodically, start them here
        # Example: self.my_task.start()

    # Clean up tasks when the cog is unloaded
    def cog_unload(self):
        # If you have tasks, cancel them here
        # Example: self.my_task.cancel()
        pass # Replace with actual cleanup if needed

    # Example of a simple application command (slash command)
    @app_commands.command(name="template", description="A template command")
    @app_commands.describe(
        # Describe your command parameters here
        # param_name="Description of the parameter"
        example_param="An example parameter"
    )
    # You can add choices or autocompletes here if needed
    # @app_commands.choices(...)
    # @app_commands.autocomplete(...)
    async def template_command(self, interaction: discord.Interaction, example_param: str):
        """
        This is the docstring for your command.
        It should explain what the command does.
        """
        # Log the command usage (optional, but good practice)
        settings.logger.info(f"COMMAND 'TEMPLATE' USED BY: {interaction.user} ({interaction.user.id})")

        # Defer the response if the command might take time
        await interaction.response.defer()

        try:
            # Your command logic goes here
            response_message = f"Hello, {interaction.user.display_name}! You provided: `{example_param}`"

            # Send the response
            await interaction.followup.send(response_message)

        except Exception as e:
            # Handle any errors that occur
            settings.logger.error(f"Error in template command: {str(e)}")
            await interaction.followup.send(f"An error occurred: `{str(e)}`", ephemeral=True)

    # Example of a task that runs periodically (optional)
    # @tasks.loop(minutes=5) # Runs every 5 minutes
    # async def my_task(self):
    #     """This task does something periodically."""
    #     settings.logger.info("Running my_task...")
    #     # Your task logic here
    #     pass

    # This runs before the task starts, ensuring the bot is ready
    # @my_task.before_loop
    # async def before_my_task(self):
    #     await self.bot.wait_until_ready()


# The setup function is required for the bot to load the cog
async def setup(bot: commands.Bot):
    """
    Adds the TemplateCog to the bot.
    """
    await bot.add_cog(TemplateCog(bot))
