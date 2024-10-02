import discord
from discord.ext import commands
from settings import logger
from core import wd_tagger

if __name__ != "__main__":
    logger.info(f"CONTEXT MENU LOADED: {__name__}")

def contextmenu(bot: commands.Bot):
    @bot.tree.context_menu(name="Show join date")
    async def show_join_date(interaction: discord.Interaction, user: discord.User):
        logger.info(f"CONTEXTMENU 'SHOW_JOIN_DATE' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"`{user.name}` joined on `{user.created_at.strftime('%Y-%m-%d %H:%M:%S')}`", ephemeral=True)

    @bot.tree.context_menu(name="Classify image")
    async def classify_image(interaction: discord.Interaction, message: discord.Message):
        logger.info(f"CONTEXTMENU 'CLASSIFY_IMAGE' USED BY: {interaction.user} ({interaction.user.id})")
        if message.attachments:
            await interaction.response.send_message("Classifying image...", delete_after=10)
            confidence_levels_dict = {}
            for attachment in message.attachments:
                if attachment.content_type.startswith("image"):
                    confidence_levels, highest_confidence_level, nsfw = wd_tagger.predict(attachment.url)
                    confidence_levels_dict[attachment.url] = {
                        "confidence_levels": confidence_levels,
                        "nsfw": nsfw
                    }

            if confidence_levels_dict:
            
                for attachment, sub_dict in confidence_levels_dict.items():
                    embed = discord.Embed(
                        title=f"Image Classification = {'NSFW' if sub_dict['nsfw'] else 'SFW'}",
                        description=f"Confidence levels for {attachment}",
                    )
                    embed.set_image(url=attachment)
                    embed.add_field(
                        name="Confidence Levels",
                        value="\n".join(f"{key}: `{value}`" for key, value in sub_dict['confidence_levels'].items()),
                        inline=False
                    )
                    message = await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message("No image found in message", ephemeral=True)