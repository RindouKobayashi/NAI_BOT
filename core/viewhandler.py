import discord
from discord.ui import View, Button
from settings import USER_VIBE_TRANSFER_DIR, logger, DATABASE_DIR
import base64
import json
import os
from core.nai_utils import base64_to_image

class PaginationView(View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction
        self.current_page: int = 1

    async def send(self):
        #await self.interaction.response.send_message(view=self, delete_after=180)
        self.message = await self.interaction.original_response()
        await self.update_message()

    async def create_embed(self):
        embed = discord.Embed(
            title="Vibe Transfer Data",
            description=f"Image {self.current_page}/5",
            color=discord.Color.blurple()
        )
        vibe_transfer_data =  await self.get_json_data()
        if self.current_page <= len(vibe_transfer_data):
            # convert base64 string to image
            image = base64_to_image(vibe_transfer_data[self.current_page - 1]["image"])
            file = discord.File(image, filename="image.png")
            embed.set_image(url="attachment://image.png")
            embed.add_field(name=f"Info Extracted: ", value=f"{vibe_transfer_data[self.current_page - 1]['info_extracted']}", inline=True)
            embed.add_field(name=f"Reference Strength: ", value=f"{vibe_transfer_data[self.current_page - 1]['ref_strength']}", inline=True)
        else:
            file = discord.File(f"{DATABASE_DIR}/No-image-found.jpg", filename="image.png")
            embed.set_image(url="attachment://image.png")
            embed.add_field(name="Info Extracted: ", value="No data found", inline=True)
            embed.add_field(name="Reference Strength: ", value="No data found", inline=True)
        embed.set_footer(text=f"Requested by {self.interaction.user}", icon_url=self.interaction.user.display_avatar.url)
        return embed, file
    
    async def update_message(self):
        self.update_buttons()
        embed, file = await self.create_embed()
        await self.interaction.edit_original_response(embed=embed, view=self, attachments=[file])
    
    async def get_json_data(self):
        # Check if file exists
        if not os.path.exists(f"{USER_VIBE_TRANSFER_DIR}/{self.interaction.user.id}.json"):
            return None
        with open(f"{USER_VIBE_TRANSFER_DIR}/{self.interaction.user.id}.json", "r") as f:
            return json.load(f)
        
    def update_buttons(self):
        if self.current_page == 1:
            self.goto_first.disabled = True
            self.goto_previous.disabled = True
        else:
            self.goto_first.disabled = False
            self.goto_previous.disabled = False

        if self.current_page == 5:
            self.goto_next.disabled = True
            self.goto_last.disabled = True
        else:
            self.goto_next.disabled = False
            self.goto_last.disabled = False

    @discord.ui.button(emoji="⏪",
                        style=discord.ButtonStyle.primary,
                        label="First Page")
    async def goto_first(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        self.current_page = 1
        await self.update_message()

    @discord.ui.button(emoji="⬅️",
                       style=discord.ButtonStyle.primary,
                       label="Previous Page")
    async def goto_previous(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message()

    @discord.ui.button(emoji="➡️",
                       style=discord.ButtonStyle.primary,
                       label="Next Page")
    async def goto_next(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message()

    @discord.ui.button(emoji="⏩",
                        style=discord.ButtonStyle.primary,
                        label="Last Page")
    async def goto_last(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        self.current_page = 5
        await self.update_message()