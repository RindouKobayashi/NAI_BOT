import discord
from discord.ui import View, Button, Select
import settings
from settings import USER_VIBE_TRANSFER_DIR, logger, DATABASE_DIR, uuid, Globals
import base64
import json
import os
import random
from core.modalhandler import EditModal, AddModal, RemixModal, RenamePresetModal, DeletePresetModal # Import new modals
from core.nai_utils import base64_to_image
import core.dict_annotation as da
from core.checking_params import check_params
from core.nai_vars import Nai_vars

class PresetSelect(Select):
    def __init__(self, user_data: dict, initial_preset_name: str):
        self.user_data = user_data
        self.initial_preset_name = initial_preset_name
        options = [
            discord.SelectOption(label=name, value=name)
            for name in user_data.get("presets", {}).keys()
        ]
        # Set the default option if initial_preset_name is provided and exists
        for option in options:
            if option.value == initial_preset_name:
                option.default = True
                break

        super().__init__(placeholder="Select a preset", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_preset_name = self.values[0]
        # Check the type of the parent view to determine the correct action
        if isinstance(self.view, VibeTransferView):
            # If the parent is VibeTransferView, update the message within that view
            self.view.current_preset_name = selected_preset_name
            self.view.current_page = 1 # Reset page when changing preset
            await self.view.update_message()
        elif isinstance(self.view, VibeTransferPresetMenuView):
            # If the parent is VibeTransferPresetMenuView, handle the preset selection
            await self.view.handle_preset_selection(selected_preset_name, interaction)
        else:
            # Should not happen if PresetSelect is only used in these two views
            logger.error(f"PresetSelect used in unexpected view type: {type(self.view)}")
            await interaction.followup.send("An unexpected error occurred.", ephemeral=True)


class VibeTransferView(View):
    def __init__(self, interaction: discord.Interaction, user_data: dict, initial_preset_name: str):
        super().__init__(timeout=600)
        self.interaction = interaction
        self.user_data = user_data
        self.current_preset_name = initial_preset_name
        self.current_page: int = 1

        # Add the preset selection dropdown
        self.add_item(PresetSelect(user_data, initial_preset_name))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original interaction author to interact with the view."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("You are not authorized to use this view.", ephemeral=True)
            return False
        return True

    async def send(self):
        self.message = await self.interaction.original_response()
        await self.update_message()

    async def create_embed(self):
        embed = discord.Embed(
            title=f"Vibe Transfer Data - Preset: `{self.current_preset_name}`",
            description=f"Image {self.current_page}/5",
            color=discord.Color.blurple()
        )
        preset_data = self.user_data.get("presets", {}).get(self.current_preset_name, [])

        if self.current_page <= len(preset_data):
            # convert base64 string to image
            image = base64_to_image(preset_data[self.current_page - 1]["image"])
            file = discord.File(image, filename="image.png")
            embed.set_image(url="attachment://image.png")
            embed.add_field(name=f"Info Extracted: ", value=f"{preset_data[self.current_page - 1]['info_extracted']}", inline=True)
            embed.add_field(name=f"Reference Strength: ", value=f"{preset_data[self.current_page - 1]['ref_strength']}", inline=True)
        else:
            file = discord.File(f"{DATABASE_DIR}/No-image-found.jpg", filename="image.png")
            embed.set_image(url="attachment://image.png")
            embed.add_field(name="Info Extracted: ", value="No data found", inline=True)
            embed.add_field(name="Reference Strength: ", value="No data found", inline=True)
        embed.set_footer(text=f"Requested by {self.interaction.user}", icon_url=self.interaction.user.display_avatar.url)
        return embed, file

    async def update_message(self, content: str = None):
        await self.update_buttons()
        embed, file = await self.create_embed()

        # Update the preset select dropdown options and default
        for item in self.children:
            if isinstance(item, PresetSelect):
                # Regenerate options based on current user_data
                item.options = [
                    discord.SelectOption(label=name, value=name)
                    for name in self.user_data.get("presets", {}).keys()
                ]
                # Set the default option
                for option in item.options:
                    option.default = (option.value == self.current_preset_name)
                # If the current preset was deleted and no presets are left, disable the dropdown
                if not item.options:
                    item.disabled = True
                    item.placeholder = "No presets available"
                else:
                    item.disabled = False
                    item.placeholder = "Select a preset"
                break # Assuming only one PresetSelect

        await self.interaction.edit_original_response(embed=embed, view=self, attachments=[file], content=content)

    async def save_json_data(self):
        user_id = str(self.interaction.user.id)
        user_file_path = f"{USER_VIBE_TRANSFER_DIR}/{user_id}.json"
        os.makedirs(USER_VIBE_TRANSFER_DIR, exist_ok=True) # Ensure directory exists
        with open(user_file_path, "w") as f:
            json.dump(self.user_data, f, indent=4)

    async def delete_current_image(self):
        preset_data = self.user_data.get("presets", {}).get(self.current_preset_name, [])
        if self.current_page <= len(preset_data):
            del preset_data[self.current_page - 1]
            self.user_data["presets"][self.current_preset_name] = preset_data # Update the user_data dictionary
            await self.save_json_data()
            # Adjust current_page if the last image was deleted
            if self.current_page > len(preset_data) and self.current_page > 1:
                self.current_page -= 1


    async def update_buttons(self):
        preset_data = self.user_data.get("presets", {}).get(self.current_preset_name, [])
        num_images = len(preset_data)

        # Navigation buttons
        self.goto_first.disabled = self.current_page == 1
        self.goto_previous.disabled = self.current_page == 1
        self.goto_next.disabled = self.current_page >= num_images or self.current_page == 5 # Limit to 5 images per preset
        self.goto_last.disabled = self.current_page >= num_images or self.current_page == 5 # Limit to 5 images per preset

        # Action buttons
        self.delete.disabled = num_images == 0 or self.current_page > num_images
        self.edit.disabled = num_images == 0 or self.current_page > num_images
        self.new.disabled = num_images >= 5 # Limit to 5 images per preset
        self.rename_preset.disabled = not self.user_data.get("presets") # Disable if no presets exist
        self.delete_preset.disabled = not self.user_data.get("presets") # Disable if no presets exist


    async def check_author(self, interaction: discord.Interaction):
        return interaction.user.id == self.interaction.user.id

    @discord.ui.button(emoji="⏪",
                        style=discord.ButtonStyle.primary,
                        label="First Page", row=1)
    async def goto_first(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not await self.check_author(interaction):
            await interaction.followup.send("You are not authorized to use this button", ephemeral=True)
            return
        else:
            self.current_page = 1
            await self.update_message()

    @discord.ui.button(emoji="⬅️",
                       style=discord.ButtonStyle.primary,
                       label="Previous Page", row=1)
    async def goto_previous(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not await self.check_author(interaction):
            await interaction.followup.send("You are not authorized to use this button", ephemeral=True)
            return
        else:
            self.current_page -= 1
            await self.update_message()

    @discord.ui.button(emoji="➡️",
                       style=discord.ButtonStyle.primary,
                       label="Next Page", row=1)
    async def goto_next(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not await self.check_author(interaction):
            await interaction.followup.send("You are not authorized to use this button", ephemeral=True)
            return
        else:
            self.current_page += 1
            await self.update_message()

    @discord.ui.button(emoji="⏩",
                        style=discord.ButtonStyle.primary,
                        label="Last Page", row=1)
    async def goto_last(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not await self.check_author(interaction):
            await interaction.followup.send("You are not authorized to use this button", ephemeral=True)
            return
        else:
            preset_data = self.user_data.get("presets", {}).get(self.current_preset_name, [])
            self.current_page = len(preset_data) if len(preset_data) <= 5 else 5 # Go to the last image page, max 5
            await self.update_message()

    @discord.ui.button(emoji="🗑️",
                        style=discord.ButtonStyle.danger,
                        label="Delete Image", row=2)
    async def delete(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not await self.check_author(interaction):
            await interaction.followup.send("You are not authorized to use this button", ephemeral=True)
            return
        else:
            await self.delete_current_image()
            await self.update_message(content="Image deleted successfully.")

    @discord.ui.button(emoji="✏️",
                        style=discord.ButtonStyle.secondary,
                        label="Edit Image", row=2)
    async def edit(self, interaction: discord.Interaction, button: Button):
        if not await self.check_author(interaction):
            await interaction.response.send_message("You are not authorized to use this button", ephemeral=True)
            return
        else:
            preset_data = self.user_data.get("presets", {}).get(self.current_preset_name, [])
            if self.current_page <= len(preset_data):
                current_image_data = preset_data[self.current_page - 1]
                modal = EditModal(
                    title=f"Image {self.current_page} Vibe Transfer Edit",
                    page=self.current_page,
                    update_message=self.update_message,
                    current_info=current_image_data.get("info_extracted"),
                    current_strength=current_image_data.get("ref_strength"),
                    view=self # Pass the view to the modal
                )
                await interaction.response.send_modal(modal)
            else:
                 await interaction.response.send_message("No image to edit on this page.", ephemeral=True)


    @discord.ui.button(emoji="🆕",
                        style=discord.ButtonStyle.primary,
                        label="Add Image", row=2)
    async def new(self, interaction: discord.Interaction, button: Button):
        if not await self.check_author(interaction):
            await interaction.response.send_message("You are not authorized to use this button", ephemeral=True)
            return
        else:
            preset_data = self.user_data.get("presets", {}).get(self.current_preset_name, [])
            if len(preset_data) < 5:
                modal = AddModal(
                    title=f"Add Image to Preset `{self.current_preset_name}`",
                    update_message=self.update_message,
                    view=self # Pass the view to the modal
                )
                await interaction.response.send_modal(modal)
            else:
                 await interaction.response.send_message("This preset already has the maximum of 5 images.", ephemeral=True)

    @discord.ui.button(emoji="✏️",
                        style=discord.ButtonStyle.secondary,
                        label="Rename Preset", row=3)
    async def rename_preset(self, interaction: discord.Interaction, button: Button):
        if not await self.check_author(interaction):
            await interaction.response.send_message("You are not authorized to use this button", ephemeral=True)
            return
        else:
            if self.current_preset_name:
                modal = RenamePresetModal(
                    title=f"Rename Preset `{self.current_preset_name}`",
                    current_name=self.current_preset_name,
                    view=self # Pass the view to the modal
                )
                await interaction.response.send_modal(modal)
            else:
                 await interaction.response.send_message("No preset selected to rename.", ephemeral=True)


    @discord.ui.button(emoji="🗑️",
                        style=discord.ButtonStyle.danger,
                        label="Delete Preset", row=3)
    async def delete_preset(self, interaction: discord.Interaction, button: Button):
        if not await self.check_author(interaction):
            await interaction.response.send_message("You are not authorized to use this button", ephemeral=True)
            return
        else:
            if self.current_preset_name:
                # For simplicity, we'll use a confirmation modal. A simple confirmation button could also work.
                modal = DeletePresetModal(
                    title=f"Delete Preset `{self.current_preset_name}`?",
                    preset_name=self.current_preset_name,
                    view=self # Pass the view to the modal
                )
                await interaction.response.send_modal(modal)
            else:
                 await interaction.response.send_message("No preset selected to delete.", ephemeral=True)


    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        embed, file = await self.create_embed()
        message = await self.interaction.edit_original_response(embed=embed, view=self, attachments=[file], content=f"`Timed out, deleting in 10 seconds...`")
        await message.delete(delay=10)

class VibeTransferPresetMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.user_data = {} # Initialize user data

        # Load user data
        user_id = str(self.bundle_data["interaction"].user.id)
        user_file_path = f"{USER_VIBE_TRANSFER_DIR}/{user_id}.json"
        if os.path.exists(user_file_path):
            with open(user_file_path, "r") as f:
                self.user_data = json.load(f)

        # Add the preset selection dropdown
        # Do not set an initial preset name so the dropdown has no default selection
        if self.user_data.get("presets"):
             self.add_item(PresetSelect(self.user_data, None)) # Pass None for initial_preset_name
        else:
             # Add a disabled select if no presets exist
             disabled_select = Select(placeholder="No presets available", options=[], disabled=True)
             self.add_item(disabled_select)


    async def send(self, interaction: discord.Interaction):
        # This view is typically sent as a response to an interaction.
        # The PresetSelect handles the actual selection and updating the message.
        # We just need to send the initial message with the view.
        embed = discord.Embed(
            title="Select a Vibe Transfer Preset",
            description="Choose a preset from the dropdown.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def handle_preset_selection(self, preset_name: str, interaction: discord.Interaction):
        """Handles the selection of a vibe transfer preset."""
        # Retrieve the list of images for the selected preset name
        preset_images_data = self.user_data.get("presets", {}).get(preset_name)

        if isinstance(preset_images_data, list) and preset_images_data:
            # Get the data for the first image in the preset
            image_data = preset_images_data[0]

            # Update the bundle_data in the global storage
            request_id = self.bundle_data["request_id"]
            if request_id in Globals.select_views_generation_data:
                updated_bundle_data = Globals.select_views_generation_data[request_id]

                # Update checking_params with the first image's data
                updated_bundle_data["checking_params"]["vibe_transfer_image"] = image_data.get("image")
                updated_bundle_data["checking_params"]["vibe_transfer_info_extracted"] = image_data.get("info_extracted")
                updated_bundle_data["checking_params"]["vibe_transfer_ref_strength"] = image_data.get("ref_strength")
                updated_bundle_data["checking_params"]["vibe_transfer_switch"] = True # Enable vibe transfer

                Globals.select_views_generation_data[request_id] = updated_bundle_data

                await interaction.followup.send(f"Vibe transfer preset `{preset_name}` applied using the first image. Press 'Go' to generate.", ephemeral=True)

                # Optionally, disable the select menu after selection
                for item in self.children:
                    if isinstance(item, Select):
                        item.disabled = True
                await interaction.edit_original_response(view=self)

            else:
                await interaction.followup.send("Could not find generation data for this request.", ephemeral=True)
        elif isinstance(preset_images_data, list) and not preset_images_data:
             await interaction.followup.send(f"Preset `{preset_name}` is empty.", ephemeral=True)
        else:
            await interaction.followup.send(f"Preset `{preset_name}` not found or data format is incorrect.", ephemeral=True)


class RemixView(View):
    def __init__(self, bundle_data: da.BundleData, forward_channel: discord.TextChannel):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.forward_channel = forward_channel

        if bundle_data["interaction"].channel_id != settings.SFW_IMAGE_GEN_BOT_CHANNEL:
            self.remove_item(self.forward)

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    @discord.ui.button(emoji="♻️",
                        style=discord.ButtonStyle.primary,
                        label="reSeed")
    async def reseed(self, interaction: discord.Interaction, button: Button):
        logger.info(f"reSeed button pressed by {interaction.user.name} ({interaction.user.id})")
        await interaction.response.defer()
        #button.custom_id = self.bundle_data["request_id"]
        new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
        new_data["checking_params"]["seed"] = random.randint(0, 9999999999)
        new_data["params"]["seed"] = new_data["checking_params"]["seed"]
        new_data["request_id"] = str(uuid.uuid4())
        new_data["interaction"] = interaction
        new_data["number_of_tries"] = 2
        new_data["message"] = await interaction.followup.send("♻️ Seeding ♻️")
        from core.queuehandler import nai_queue
        from core.queuehandler import NAIQueue
        nai_queue: NAIQueue
        await nai_queue.add_to_queue(new_data)

    @discord.ui.button(emoji="🎨",
                        style=discord.ButtonStyle.primary,
                        label="reMix")
    async def remix(self, interaction: discord.Interaction, button: Button):
        logger.info(f"reMix button pressed by {interaction.user.name} ({interaction.user.id})")
        await interaction.response.defer()
        #button.custom_id = self.bundle_data["request_id"]
        new_data: da.BundleData = self.bundle_data.copy()
        new_data["request_id"] = str(uuid.uuid4())
        new_data["interaction"] = interaction
        new_data["reference_message"] = self.bundle_data["message"]
        new_data["message"] = await interaction.followup.send("🎨 Mixing 🎨", ephemeral=True)
        Globals.select_views[new_data["request_id"]] = SelectMenuView(new_data)
        await Globals.select_views[new_data["request_id"]].send()

        #from core.queuehandler import nai_queue
        #await nai_queue.add_to_queue(new_data)

    @discord.ui.button(emoji="↪",
                        style=discord.ButtonStyle.primary,
                        label="Forward")
    async def forward(self, interaction: discord.Interaction, button: Button):
        logger.info(f"Forward button pressed by {interaction.user.name} ({interaction.user.id})")
        await interaction.response.defer()
        reply_content = interaction.message.content
        reply_content += f"\n[View Request]({interaction.message.jump_url})"
        attachment = await interaction.message.attachments[0].to_file()
        await self.forward_channel.send(content=reply_content, file=attachment, allowed_mentions=discord.AllowedMentions.none())
        await self.bundle_data["message"].remove_attachments()
        await interaction.message.edit(content=f"{interaction.message.content}\nForwarded to {self.forward_channel.mention}")
        # Disable forward button
        button.disabled = True
        await self.send()

    async def on_timeout(self):
        self.stop()
        Globals.remix_views.pop(self.bundle_data["request_id"])
        message = self.bundle_data["message"]
        try:
            for child in self.children:
                child: Button | discord.ui.Select
                child.disabled = True
            #self.reseed.disabled = True
            #self.remix.disabled = True
            await message.edit(view=self)
        except discord.NotFound:
            # Message has already been deleted
            pass
        except discord.HTTPException as e:
            logger.error(f"Failed to edit message on timeout: {e}")
            pass

class SMEAMenu(discord.ui.Select):
    def __init__(self, bundle_data: da.BundleData):
        self.bundle_data = bundle_data
        options = [
            discord.SelectOption(
                label="SMEA",
                value="SMEA",
                description="SMEA",
            ),
            discord.SelectOption(
                label="SMEA+DYN",
                value="SMEA+DYN",
                description="SMEA+DYN",
            ),
            discord.SelectOption(
                label="None",
                value="None",
                description="None",
            ),
        ]
        super().__init__(placeholder="Select SMEA type", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
        new_data["checking_params"]["smea"] = self.values[0]
        Globals.select_views_generation_data[new_data["request_id"]] = new_data
        message = await interaction.edit_original_response(content="`Edit successful, if done editing, press button to submit.`")
        await message.delete(delay=1)

class SMEAMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.add_item(SMEAMenu(self.bundle_data))

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    async def on_timeout(self):
        self.stop()

class ModelMenu(discord.ui.Select):
    def __init__(self, bundle_data: da.BundleData):
        self.bundle_data = bundle_data
        options = Nai_vars.models_select_options
        super().__init__(placeholder="Select model", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
        new_data["checking_params"]["model"] = self.values[0]
        Globals.select_views_generation_data[new_data["request_id"]] = new_data
        message = await interaction.edit_original_response(content="`Edit successful, if done editing, press button to submit.`")
        await message.delete(delay=1)

class ModelMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.add_item(ModelMenu(self.bundle_data))

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    async def on_timeout(self):
        self.stop()

class TrueFalseMenu(discord.ui.Select):
    def __init__(self, bundle_data: da.BundleData, name: str):
        self.bundle_data = bundle_data
        self.name = name
        options = [
            discord.SelectOption(
                label="True",
                description="True",
            ),
            discord.SelectOption(
                label="False",
                description="False",
            ),
        ]
        super().__init__(placeholder=f"Select {self.name}", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
        if type(self.values[0]) == str:
            # Convert from str to bool
            if self.values[0] == "True":
                self.values[0] = True
            elif self.values[0] == "False":
                self.values[0] = False
        if self.name == "decrisper":
            new_data["checking_params"]["dynamic_thresholding"] = bool(self.values[0])
        else:
            new_data["checking_params"][f"{self.name}"] = bool(self.values[0])
        Globals.select_views_generation_data[new_data["request_id"]] = new_data
        message = await interaction.edit_original_response(content="`Edit successful, if done editing, press button to submit.`")
        await message.delete(delay=1)

class TrueFalseMenuView(View):
    def __init__(self, bundle_data: da.BundleData, name: str):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.name = name
        self.add_item(TrueFalseMenu(self.bundle_data, self.name))

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    async def on_timeout(self):
        self.stop()

class UndesiredContentMenu(discord.ui.Select):
    def __init__(self, bundle_data: da.BundleData):
        self.bundle_data = bundle_data
        options = Nai_vars.undesired_content_presets(self.bundle_data["checking_params"]["model"]).undesired_content_select_options
        super().__init__(placeholder="Select undesired content", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
        new_data["checking_params"]["undesired_content_presets"] = self.values[0]
        Globals.select_views_generation_data[new_data["request_id"]] = new_data
        message = await interaction.edit_original_response(content="`Edit successful, if done editing, press button to submit.`")
        await message.delete(delay=1)

class UndesiredContentMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.add_item(UndesiredContentMenu(self.bundle_data))

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    async def on_timeout(self):
        self.stop()

class NoiseScheduleMenu(discord.ui.Select):
    def __init__(self, bundle_data: da.BundleData):
        self.bundle_data = bundle_data
        options = Nai_vars.noise_schedule_options
        super().__init__(placeholder="Select noise schedule", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
        new_data["checking_params"]["noise_schedule"] = self.values[0]
        Globals.select_views_generation_data[new_data["request_id"]] = new_data
        message = await interaction.edit_original_response(content="`Edit successful, if done editing, press button to submit.`")
        await message.delete(delay=1)

class NoiseScheduleMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.add_item(NoiseScheduleMenu(self.bundle_data))

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    async def on_timeout(self):
        self.stop()

class SamplerMenu(discord.ui.Select):
    def __init__(self, bundle_data: da.BundleData):
        self.bundle_data = bundle_data
        options = Nai_vars.samplers_options
        super().__init__(placeholder="Select Sampler", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_data: da.BundleData = da.deep_copy_bundle_data(self.bundle_data)
        new_data["checking_params"]["sampler"] = self.values[0]
        Globals.select_views_generation_data[new_data["request_id"]] = new_data
        message = await interaction.edit_original_response(content="`Edit successful, if done editing, press button to submit.`")
        await message.delete(delay=1)

class SamplerMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        self.add_item(SamplerMenu(self.bundle_data))

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    async def on_timeout(self):
        self.stop()

class SelectMenu(discord.ui.Select):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(
            row=0,
        )
        self.bundle_data = bundle_data
        options = [
            discord.SelectOption(
                label="positive",
                description="Positive prompt for image generation",
            ),
            discord.SelectOption(
                label="negative",
                description="Negative prompt for image generation",
            ),
            discord.SelectOption(
                label="width",
                description="Width of the generated image",
            ),
            discord.SelectOption(
                label="height",
                description="Height of the generated image",
            ),
            discord.SelectOption(
                label="steps",
                description="Number of denoising steps",
            ),
            discord.SelectOption(
                label="cfg",
                description="CFG scale",
            ),
            discord.SelectOption(
                label="sampler",
                description="Sampling method",
            ),
            discord.SelectOption(
                label="noise_schdule",
                description="Noise schedule",
            ),
            discord.SelectOption(
                label="smea",
                description="SMEA and SMEA+DYN versions of samplers perform better at high res",
            ),
            discord.SelectOption(
                label="seed",
                description="Seed for the image generation",
            ),
            discord.SelectOption(
                label="model",
                description="Model to use for image generation",
            ),
            discord.SelectOption(
                label="quality_toggle",
                description="Tags to increase quality, will be prepended to the prompt",
            ),
            discord.SelectOption(
                label="undesired_content_presets",
                description="Tags to remove undesired content, will be appended to the prompt",
            ),
            discord.SelectOption(
                label="prompt_conversion_toggle",
                description="Convert Auto1111 way of prompt to NovelAI way of prompt",
            ),
            discord.SelectOption(
                label="upscale",
                description="Upscale image by 4x. Only available for images up to 640x640",
            ),
            discord.SelectOption(
                label="decrisper",
                description="Basically dynamic thresholding",
            ),
            discord.SelectOption(
                label="vibe_transfer_preset",
                description="Select a vibe transfer preset",
            ),
        ]
        super().__init__(placeholder="Select to edit", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        ### TODO: Add logic to edit the image
        # Check if request_id is in the select_views
        if self.bundle_data["request_id"] in Globals.select_views:
            # Update self.bundle_data with select_views_generation_data if request_id is in the select_views
            if self.bundle_data["request_id"] in Globals.select_views_generation_data:
                self.bundle_data = Globals.select_views_generation_data[self.bundle_data["request_id"]]
            if self.values[0] in ["positive", "negative", "width", "height", "steps", "seed", "cfg"]:
                remix_modal = RemixModal(self.bundle_data, self.values[0])
                await interaction.response.send_modal(remix_modal)
            elif self.values[0] == "sampler":
                await interaction.response.send_message(view=SamplerMenuView(self.bundle_data), ephemeral=True)
            elif self.values[0] == "noise_schdule":
                await interaction.response.send_message(view=NoiseScheduleMenuView(self.bundle_data), ephemeral=True)
            elif self.values[0] == "smea":
                await interaction.response.send_message(view=SMEAMenuView(self.bundle_data), ephemeral=True)
            elif self.values[0] == "model":
                await interaction.response.send_message(view=ModelMenuView(self.bundle_data), ephemeral=True)
            elif self.values[0] in ["quality_toggle", "prompt_conversion_toggle", "upscale", "decrisper"]:
                await interaction.response.send_message(view=TrueFalseMenuView(self.bundle_data, name=self.values[0]), ephemeral=True)
            elif self.values[0] == "undesired_content_presets":
                await interaction.response.send_message(view=UndesiredContentMenuView(self.bundle_data), ephemeral=True)
            elif self.values[0] == "vibe_transfer_preset":
                preset_menu_view = VibeTransferPresetMenuView(self.bundle_data)
                await preset_menu_view.send(interaction)

class SelectMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
        # Store the initial bundle_data in the global dictionary for later modification
        Globals.select_views_generation_data[self.bundle_data["request_id"]] = self.bundle_data.copy()
        self.add_item(SelectMenu(self.bundle_data))

    async def send(self):
        message = self.bundle_data["message"]
        await message.edit(view=self)

    @discord.ui.button(emoji="✅",
                       style=discord.ButtonStyle.green,
                       label="Go",
                       row=1)
    async def go(self, interaction: discord.Interaction, button: Button):
        logger.info(f"Go button pressed by {interaction.user.name} ({interaction.user.id})")
        await interaction.response.defer()
        #await interaction.response.send_message("🎨 Remixing in progress 🎨")
        #button.custom_id = self.bundle_data["request_id"]
        if Globals.select_views_generation_data.get(self.bundle_data["request_id"]):
            new_data: da.BundleData = Globals.select_views_generation_data[self.bundle_data["request_id"]].copy()
            channel = interaction.channel
            message = await channel.send("🎨 Remixing in progress 🎨", reference=new_data["reference_message"])
            #message = await interaction.edit_original_response(content="🎨 Adding your request to the queue 🎨")
            new_data["message"] = message
            new_data["interaction"] = interaction
            try:
                checking_params = await check_params(new_data["checking_params"], interaction=interaction)
                params: da.Params = da.create_with_defaults(
                    da.Params,
                    positive=checking_params["positive"],
                    negative=checking_params["negative"],
                    width=checking_params["width"],
                    height=checking_params["height"],
                    steps=checking_params["steps"],
                    cfg=checking_params["cfg"],
                    sampler=checking_params["sampler"],
                    noise_schedule=checking_params["noise_schedule"],
                    sm=checking_params["sm"],
                    sm_dyn=checking_params["sm_dyn"],
                    seed=checking_params["seed"],
                    model=checking_params["model"],
                    vibe_transfer_switch=checking_params.get("vibe_transfer_switch", False), # Safely access vibe_transfer_switch
                    dynamic_thresholding=checking_params["dynamic_thresholding"],
                    skip_cfg_above_sigma=checking_params["skip_cfg_above_sigma"],
                    upscale=checking_params["upscale"],
                )
                # Add vibe transfer data to params if the switch is True and data exists in checking_params
                if checking_params.get("vibe_transfer_switch") and checking_params.get("vibe_transfer_image"):
                    params["vibe_transfer_data"] = [{
                        "image": checking_params["vibe_transfer_image"],
                        "info_extracted": checking_params["vibe_transfer_info_extracted"],
                        "ref_strength": checking_params["vibe_transfer_ref_strength"]
                    }]
                bundle_data: da.BundleData = da.create_with_defaults(
                    da.BundleData,
                    type="txt2img",
                    request_id=self.bundle_data["request_id"],
                    interaction=interaction,
                    message=message,
                    params=params,
                    checking_params=checking_params,
                )
                from core.queuehandler import nai_queue
                from core.queuehandler import NAIQueue
                nai_queue: NAIQueue
                #logger.info(f"Adding to queue: {bundle_data['params']}")
                success = await nai_queue.add_to_queue(bundle_data)
                if success:
                    await interaction.delete_original_response()
            except Exception as e:
                logger.error(f"Error while adding to queue: {e}")
                await message.edit(content="❌ Error while adding to queue ❌", delete_after=10)

    async def on_timeout(self):
        self.stop()
        Globals.select_views.pop(self.bundle_data["request_id"])
        message = self.bundle_data["message"]
        try:
            for child in self.children:
                child: Button | discord.ui.Select
                child.disabled = True
            await message.edit(view=self)
        except discord.NotFound:
            # Message has already been deleted
            pass
        except discord.HTTPException as e:
            logger.error(f"Failed to edit message on timeout: {e}")
            pass
