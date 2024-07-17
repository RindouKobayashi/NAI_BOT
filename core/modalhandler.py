from settings import logger, USER_VIBE_TRANSFER_DIR
from discord.ui import Modal, TextInput
import discord
import requests
import json
import base64


class EditModal(Modal):
    def __init__(self, title: str, page: int, update_message):
        super().__init__(title=title)
        self.page = page
        self.update_message = update_message

        self.add_item(TextInput(label="Image URL", style=discord.TextStyle.short, placeholder="Image URL", required=False))
        self.add_item(TextInput(label="Info Extracted Value", style=discord.TextStyle.short, placeholder="0.0 to 1.0", required=False))
        self.add_item(TextInput(label="Reference Strength", style=discord.TextStyle.short, placeholder="0.0 to 1.0", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            image_string = None
            info_extracted = None
            ref_strength = None

            # Handle image URL
            if self.children[0].value:
                response = requests.get(self.children[0].value)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type')
                
                if 'image' not in content_type:
                    raise ValueError("Invalid image URL")
                
                image_bytes = response.content
                image_string = base64.b64encode(image_bytes).decode("utf-8")
            
            # Handle info_extracted and ref_strength
            if self.children[1].value:
                info_extracted = float(self.children[1].value)
                if not 0 <= info_extracted <= 1:
                    raise ValueError("Info Extracted value must be between 0 and 1")

            if self.children[2].value:
                ref_strength = float(self.children[2].value)
                if not 0 <= ref_strength <= 1:
                    raise ValueError("Reference Strength value must be between 0 and 1")
            
            # Update the JSON file
            with open(f"{USER_VIBE_TRANSFER_DIR}/{interaction.user.id}.json", "r+") as f:
                vibe_transfer_data = json.load(f)
                current_data = vibe_transfer_data[self.page-1]
                
                if image_string is not None:
                    current_data["image"] = image_string
                if info_extracted is not None:
                    current_data["info_extracted"] = info_extracted
                if ref_strength is not None:
                    current_data["ref_strength"] = ref_strength
                
                vibe_transfer_data[self.page-1] = current_data
                f.seek(0)
                json.dump(vibe_transfer_data, f, indent=4)
                f.truncate()
            
            if self.update_message:
                await self.update_message()
            
            await interaction.edit_original_response(content="`Edit successful!`")

        except requests.RequestException:
            await interaction.edit_original_response(content="`Invalid image URL. Please enter a valid image URL.`")
        except ValueError as e:
            await interaction.edit_original_response(content=f"`{str(e)}`")
        except Exception as e:
            await interaction.edit_original_response(content=f"`An error occurred: {str(e)}`")

class AddModal(Modal):
    def __init__(self, title: str, update_message):
        super().__init__(title=title)
        self.update_message = update_message
        self.add_item(TextInput(label="Image URL", style=discord.TextStyle.short, placeholder="Image URL", required=True))
        self.add_item(TextInput(label="Info Extracted Value", style=discord.TextStyle.short, placeholder="0.0 to 1.0", required=True))
        self.add_item(TextInput(label="Reference Strength", style=discord.TextStyle.short, placeholder="0.0 to 1.0", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            # Check if image_url is valid
            response = requests.get(self.children[0].value)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type')
            if 'image' not in content_type:
                raise ValueError("`Invalid image URL`")
            
            image_bytes = response.content
            image_string = base64.b64encode(image_bytes).decode("utf-8")

            info_extracted = float(self.children[1].value)
            ref_strength = float(self.children[2].value)

            if not 0 <= info_extracted <= 1 or not 0 <= ref_strength <= 1:
                raise ValueError("`Info Extracted and Reference Strength must be between 0 and 1`")

            # Add image to database
            with open(f"{USER_VIBE_TRANSFER_DIR}/{interaction.user.id}.json", "r+") as f:
                vibe_transfer_data = json.load(f)
                vibe_transfer_data.append({
                    "image": image_string,
                    "info_extracted": info_extracted,
                    "ref_strength": ref_strength
                })
                f.seek(0)
                json.dump(vibe_transfer_data, f, indent=4)
                f.truncate()

            if self.update_message:
                await self.update_message()
            
            await interaction.edit_original_response(content="`New entry added successfully!`")

        except requests.RequestException:
            await interaction.edit_original_response(content="`Invalid image URL. Please enter a valid image URL.`")
        except ValueError as e:
            await interaction.edit_original_response(content=f"`{str(e)}`")
        except Exception as e:
            await interaction.edit_original_response(content=f"`An error occurred: {str(e)}`")
