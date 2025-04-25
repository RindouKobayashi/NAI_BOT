from settings import logger, USER_VIBE_TRANSFER_DIR, Globals, copy
from discord.ui import Modal, TextInput, Select
from discord import SelectMenu
import discord
import requests
import json
import base64
import core.dict_annotation as da
from core.checking_params import check_params

class EditModal(Modal, title='Vibe Transfer Edit'):
    def __init__(self, title: str, page: int, update_message, current_info: float = None, current_strength: float = None, view=None):
        super().__init__(title=title)
        self.page = page
        self.update_message = update_message
        self.view = view # Store the parent view

        self.info_extracted = TextInput(
            label="Info Extracted (0-1)",
            placeholder="Enter info extracted value",
            default=str(current_info) if current_info is not None else "",
            required=True,
            max_length=5
        )
        self.add_item(self.info_extracted)

        self.ref_strength = TextInput(
            label="Reference Strength (0-1)",
            placeholder="Enter reference strength value",
            default=str(current_strength) if current_strength is not None else "",
            required=True,
            max_length=5
        )
        self.add_item(self.ref_strength)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            info_value = float(self.info_extracted.value)
            strength_value = float(self.ref_strength.value)

            if not 0 <= info_value <= 1:
                await interaction.followup.send("Info extracted value must be between 0 and 1.", ephemeral=True)
                return
            if not 0 <= strength_value <= 1:
                await interaction.followup.send("Reference strength value must be between 0 and 1.", ephemeral=True)
                return

            user_id = str(interaction.user.id)
            user_file_path = f"{USER_VIBE_TRANSFER_DIR}/{user_id}.json"

            # Load user data from the view
            user_data = self.view.user_data

            preset_data = user_data.get("presets", {}).get(self.view.current_preset_name, [])

            if self.page <= len(preset_data):
                preset_data[self.page - 1]["info_extracted"] = info_value
                preset_data[self.page - 1]["ref_strength"] = strength_value

                user_data["presets"][self.view.current_preset_name] = preset_data # Update the user_data dictionary
                self.view.user_data = user_data # Update the view's user_data

                # Save the updated data
                await self.view.save_json_data()

                await interaction.followup.send("Vibe transfer data updated successfully.", ephemeral=True)
                await self.update_message() # Update the message in the view
            else:
                await interaction.followup.send("Invalid page number.", ephemeral=True)

        except ValueError:
            await interaction.followup.send("Invalid input. Please enter numerical values for info extracted and reference strength.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in EditModal on_submit: {str(e)}")
            await interaction.followup.send(f"An error occurred: `{str(e)}`", ephemeral=True)

class AddModal(Modal, title='Add Vibe Transfer Image'):
    def __init__(self, title: str, update_message, view=None):
        super().__init__(title=title)
        self.update_message = update_message
        self.view = view # Store the parent view

        self.image_url = TextInput(
            label="Image URL",
            placeholder="Enter the URL of the image",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.image_url)

        self.info_extracted = TextInput(
            label="Info Extracted (0-1)",
            placeholder="Enter info extracted value",
            required=True,
            max_length=5
        )
        self.add_item(self.info_extracted)

        self.ref_strength = TextInput(
            label="Reference Strength (0-1)",
            placeholder="Enter reference strength value",
            required=True,
            max_length=5
        )
        self.add_item(self.ref_strength)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            info_value = float(self.info_extracted.value)
            strength_value = float(self.ref_strength.value)
            image_url = self.image_url.value

            if not 0 <= info_value <= 1:
                await interaction.followup.send("Info extracted value must be between 0 and 1.", ephemeral=True)
                return
            if not 0 <= strength_value <= 1:
                await interaction.followup.send("Reference strength value must be between 0 and 1.", ephemeral=True)
                return

            # Download the image
            try:
                response = requests.get(image_url)
                response.raise_for_status() # Raise an exception for bad status codes
                content_type = response.headers.get('Content-Type')
                if 'image' not in content_type:
                    raise ValueError("Invalid image URL")
                image_bytes = response.content
                image_string = base64.b64encode(image_bytes).decode("utf-8")
            except requests.exceptions.RequestException as e:
                await interaction.followup.send(f"Failed to download image from URL: `{str(e)}`", ephemeral=True)
                return

            # Load user data from the view
            user_data = self.view.user_data

            preset_data = user_data.get("presets", {}).get(self.view.current_preset_name, [])

            if len(preset_data) >= 5:
                await interaction.followup.send("This preset already has the maximum of 5 images.", ephemeral=True)
                return

            preset_data.append({
                "image": image_string,
                "info_extracted": info_value,
                "ref_strength": strength_value
            })

            user_data["presets"][self.view.current_preset_name] = preset_data # Update the user_data dictionary
            self.view.user_data = user_data # Update the view's user_data

            # Save the updated data
            await self.view.save_json_data()

            await interaction.followup.send("Vibe transfer image added successfully.", ephemeral=True)
            await self.update_message() # Update the message in the view

        except ValueError:
            await interaction.followup.send("Invalid input. Please enter numerical values for info extracted and reference strength.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in AddModal on_submit: {str(e)}")
            await interaction.followup.send(f"An error occurred: `{str(e)}`", ephemeral=True)


class RemixModal(Modal, title='Remix Parameters'):
    def __init__(self, bundle_data: da.BundleData, parameter_name: str):
        super().__init__(title=f"Edit {parameter_name}")
        self.bundle_data = bundle_data
        self.parameter_name = parameter_name

        current_value = self.bundle_data["checking_params"].get(parameter_name)
        if parameter_name == "dynamic_thresholding":
            current_value = self.bundle_data["checking_params"].get("dynamic_thresholding")
        elif parameter_name == "skip_cfg_above_sigma":
            current_value = self.bundle_data["checking_params"].get("skip_cfg_above_sigma")

        self.param_input = TextInput(
            label=f"New value for {parameter_name}",
            placeholder=f"Enter new value for {parameter_name}",
            default=str(current_value) if current_value is not None else "",
            required=True,
            style=discord.TextStyle.short if parameter_name in ["width", "height", "steps", "seed", "cfg"] else discord.TextStyle.paragraph
        )
        self.add_item(self.param_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            from core.queuehandler import nai_queue # Import here to break circular dependency
            new_value_str = self.param_input.value
            new_value = new_value_str

            # Attempt to convert to appropriate type based on parameter_name
            if self.parameter_name in ["width", "height", "steps", "seed"]:
                new_value = int(new_value_str)
            elif self.parameter_name == "cfg":
                new_value = float(new_value_str)
            elif self.parameter_name in ["quality_toggle", "prompt_conversion_toggle", "upscale", "vibe_transfer_switch", "decrisper", "variety_plus"]:
                 # This case should ideally be handled by the TrueFalseMenu, but adding fallback
                 if new_value_str.lower() == 'true':
                      new_value = True
                 elif new_value_str.lower() == 'false':
                      new_value = False
                 else:
                      raise ValueError(f"Invalid boolean value: {new_value_str}")


            # Update the bundle_data
            new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
            if self.parameter_name == "decrisper":
                new_data["checking_params"]["dynamic_thresholding"] = new_value
            elif self.parameter_name == "variety_plus":
                new_data["checking_params"]["skip_cfg_above_sigma"] = new_value
            else:
                new_data["checking_params"][self.parameter_name] = new_value

            # Store the updated data globally for the view to access
            Globals.select_views_generation_data[new_data["request_id"]] = new_data

            await interaction.followup.send(f"Parameter `{self.parameter_name}` updated to `{new_value_str}`. Press 'Go' to generate.", ephemeral=True)

        except ValueError as ve:
            await interaction.followup.send(f"Invalid input for `{self.parameter_name}`: `{str(ve)}`", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in RemixModal on_submit: {str(e)}")
            await interaction.followup.send(f"An error occurred: `{str(e)}`", ephemeral=True)

class RenamePresetModal(Modal, title='Rename Preset'):
    def __init__(self, title: str, current_name: str, view):
        # Shorten the title to avoid exceeding Discord's 45-character limit for modal titles
        short_title = "Rename Preset"
        super().__init__(title=short_title)
        self.current_name = current_name
        self.view = view

        self.new_name_input = TextInput(
            label="New Preset Name",
            placeholder="Enter the new name for the preset",
            default=current_name,
            required=True,
            max_length=100 # Adjust max length as needed
        )
        self.add_item(self.new_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_name = self.new_name_input.value.strip()

        if not new_name:
            await interaction.followup.send("Preset name cannot be empty.", ephemeral=True)
            return

        user_data = self.view.user_data
        presets = user_data.get("presets", {})

        if new_name in presets and new_name != self.current_name:
            await interaction.followup.send(f"A preset named `{new_name}` already exists.", ephemeral=True)
            return

        if self.current_name in presets:
            # Rename the preset
            presets[new_name] = presets.pop(self.current_name)
            user_data["presets"] = presets
            self.view.user_data = user_data
            self.view.current_preset_name = new_name # Update the view's current preset name

            # Save the updated data
            await self.view.save_json_data()

            await interaction.followup.send(f"Preset `{self.current_name}` successfully renamed to `{new_name}`.", ephemeral=True)
            await self.view.update_message() # Update the message in the view to reflect the new name
        else:
            await interaction.followup.send(f"Preset `{self.current_name}` not found.", ephemeral=True)


class DeletePresetModal(Modal, title='Confirm Delete'):
    def __init__(self, title: str, preset_name: str, view):
        # Shorten the title to avoid exceeding Discord's 45-character limit for modal titles
        short_title = "Delete Preset?"
        super().__init__(title=short_title)
        self.preset_name = preset_name
        self.view = view

        self.confirm_input = TextInput(
            label=f"Type '{preset_name}' to confirm deletion",
            placeholder=f"Type '{preset_name}'",
            required=True,
            max_length=100 # Adjust max length as needed
        )
        self.add_item(self.confirm_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        confirmation = self.confirm_input.value.strip()

        if confirmation != self.preset_name:
            await interaction.followup.send("Confirmation failed. Preset was not deleted.", ephemeral=True)
            return

        user_data = self.view.user_data
        presets = user_data.get("presets", {})

        if self.preset_name in presets:
            del presets[self.preset_name]
            user_data["presets"] = presets
            self.view.user_data = user_data

            # Save the updated data
            await self.view.save_json_data()

            await interaction.followup.send(f"Preset `{self.preset_name}` successfully deleted.", ephemeral=True)

            # Update the view: if the deleted preset was the current one, switch to another preset or show empty
            if self.view.current_preset_name == self.preset_name:
                if user_data["presets"]:
                    # Switch to the first available preset
                    self.view.current_preset_name = list(user_data["presets"].keys())[0]
                    self.view.current_page = 1
                    # Update the preset select dropdown options
                    self.view.children[0].options = [
                        discord.SelectOption(label=name, value=name, default=(name == self.view.current_preset_name))
                        for name in user_data["presets"].keys()
                    ]
                    await self.view.update_message()
                else:
                    # No presets left, update the view to show empty state
                    self.view.current_preset_name = None
                    self.view.current_page = 1
                    # Clear preset select dropdown options
                    self.view.children[0].options = []
                    self.view.children[0].disabled = True # Disable dropdown if no presets
                    await self.view.update_message(content="All vibe transfer presets have been deleted.")
            else:
                 # If a different preset was deleted, just update the preset select dropdown options
                 self.view.children[0].options = [
                    discord.SelectOption(label=name, value=name, default=(name == self.view.current_preset_name))
                    for name in user_data["presets"].keys()
                 ]
                 await self.view.update_message()


        else:
            await interaction.followup.send(f"Preset `{self.preset_name}` not found.", ephemeral=True)
