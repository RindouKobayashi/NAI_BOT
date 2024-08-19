from settings import logger, USER_VIBE_TRANSFER_DIR, Globals, copy
from discord.ui import Modal, TextInput, Select
from discord import SelectMenu
import discord
import requests
import json
import base64
import core.dict_annotation as da

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

class RemixModal(Modal):
    def __init__(self, bundle_data: da.BundleData, label: str):
        super().__init__(title="Remix", timeout=120)
        self.bundle_data = bundle_data
        self.label = label
        self.placeholder = f"Edit {label}"

        if self.label in ["positive", "negative"]: # Checking for string
            self.add_item(TextInput(label=self.label, 
                                    style=discord.TextStyle.long, 
                                    default=self.bundle_data['checking_params'][self.label][:4000],
                                    min_length=1,
                                    max_length=4000,
                                    required=True)
                                    )
        elif label in ["width", "height", "steps", "seed"]: # Checking for int
            self.add_item(TextInput(label=self.label, 
                                    style=discord.TextStyle.short, 
                                    default=self.bundle_data['checking_params'][self.label],
                                    min_length=1,
                                    max_length=4000, 
                                    required=False)
                                    )
        elif label in ["cfg"]: # Checking for float
            self.add_item(TextInput(label=self.label, 
                                    style=discord.TextStyle.short, 
                                    default=str(self.bundle_data['checking_params'][self.label]), 
                                    required=False)
                                    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            new_data = da.deep_copy_bundle_data(self.bundle_data)
            new_data["number_of_tries"] = 1
            if self.label in ["positive", "negative"]: # FOR STRING
                new_data['checking_params'][self.label] = self.children[0].value
            elif self.label in ["width", "height", "steps", "seed"]: # FOR INT
                new_data['checking_params'][self.label] = int(self.children[0].value)
            elif self.label in ["cfg"]: # FOR FLOAT
                new_data['checking_params'][self.label] = float(self.children[0].value)
            #Globals.select_views[self.bundle_data["request_id"]] = self.bundle_data
            Globals.select_views_generation_data[new_data["request_id"]] = new_data
            await interaction.edit_original_response(content="`Edit successful, if done editing, press button to submit.`")

        except Exception as e:
            await interaction.edit_original_response(content=f"`An error occurred: {str(e)}`")