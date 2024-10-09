import discord
from discord.ui import View, Button
import settings
from settings import USER_VIBE_TRANSFER_DIR, logger, DATABASE_DIR, uuid, Globals
import base64
import json
import os
import random
from core.modalhandler import EditModal, AddModal, RemixModal
from core.nai_utils import base64_to_image
import core.dict_annotation as da
from core.checking_params import check_params
from core.nai_vars import Nai_vars

class VibeTransferView(View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=600)
        self.interaction = interaction
        self.current_page: int = 1

    async def send(self):
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
    
    async def update_message(self, content: str = None):
        await self.update_buttons()
        embed, file = await self.create_embed()
        await self.interaction.edit_original_response(embed=embed, view=self, attachments=[file], content=content)
    
    async def get_json_data(self):
        # Check if file exists
        if not os.path.exists(f"{USER_VIBE_TRANSFER_DIR}/{self.interaction.user.id}.json"):
            return None
        with open(f"{USER_VIBE_TRANSFER_DIR}/{self.interaction.user.id}.json", "r") as f:
            return json.load(f)
        
    async def delete_json_data(self):
        vibe_transfer_data = await self.get_json_data()
        if self.current_page <= len(vibe_transfer_data):
            del vibe_transfer_data[self.current_page - 1]

        with open(f"{USER_VIBE_TRANSFER_DIR}/{self.interaction.user.id}.json", "w") as f:
            json.dump(vibe_transfer_data, f, indent=4)

        
    async def update_buttons(self):
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

        if self.current_page <= len(await self.get_json_data()):
            self.delete.disabled = False
        else:
            self.delete.disabled = True

        if self.current_page > len(await self.get_json_data()):
            self.edit.disabled = True
        else:
            self.edit.disabled = False

        if len(await self.get_json_data()) == 5:
            self.new.disabled = True
        else:
            self.new.disabled = False

    async def check_author(self, interaction: discord.Interaction):
        #logger.info(f"Checking: {interaction.user.id} == {self.interaction.user.id}")
        return interaction.user.id == self.interaction.user.id

    @discord.ui.button(emoji="⏪",
                        style=discord.ButtonStyle.primary,
                        label="First Page")
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
                       label="Previous Page")
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
                       label="Next Page")
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
                        label="Last Page")
    async def goto_last(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not await self.check_author(interaction):
            await interaction.followup.send("You are not authorized to use this button", ephemeral=True)
            return
        else:
            self.current_page = 5
            await self.update_message()

    @discord.ui.button(emoji="🗑️",
                        style=discord.ButtonStyle.danger,
                        label="Delete")
    async def delete(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if not await self.check_author(interaction):
            await interaction.followup.send("You are not authorized to use this button", ephemeral=True)
            return
        else:
            await self.delete_json_data()
            await self.update_message()

    @discord.ui.button(emoji="✏️",
                        style=discord.ButtonStyle.secondary,
                        label="Edit")
    async def edit(self, interaction: discord.Interaction, button: Button):
        if not await self.check_author(interaction):
            await interaction.response.send_message("You are not authorized to use this button", ephemeral=True)
            return
        else:
            modal = EditModal(title=f"Image {self.current_page} Vibe Transfer Edit", page=self.current_page, update_message=self.update_message)
            await interaction.response.send_modal(modal)

    @discord.ui.button(emoji="🆕",
                        style=discord.ButtonStyle.primary,
                        label="New")
    async def new(self, interaction: discord.Interaction, button: Button):
        if not await self.check_author(interaction):
            await interaction.response.send_message("You are not authorized to use this button", ephemeral=True)
            return
        else:
            modal = AddModal(title=f"Image {len(await self.get_json_data()) + 1} Vibe Transfer Add", update_message=self.update_message) 
            await interaction.response.send_modal(modal)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        embed, file = await self.create_embed()
        message = await self.interaction.edit_original_response(embed=embed, view=self, attachments=[file], content=f"`Timed out, deleting in 10 seconds...`")
        await message.delete(delay=10)

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
        if self.name == "decrisper":
            new_data["checking_params"]["dynamic_thresholding"] = self.values[0]
        else:
            new_data["checking_params"][self.name] = self.values[0]
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
                label="vibe_transfer_switch",
                description="Vibe transfer switch",
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
            elif self.values[0] in ["quality_toggle", "prompt_conversion_toggle", "upscale", "vibe_transfer_switch", "decrisper"]:
                await interaction.response.send_message(view=TrueFalseMenuView(self.bundle_data, name=self.values[0]), ephemeral=True)
            elif self.values[0] == "undesired_content_presets":
                await interaction.response.send_message(view=UndesiredContentMenuView(self.bundle_data), ephemeral=True)

class SelectMenuView(View):
    def __init__(self, bundle_data: da.BundleData):
        super().__init__(timeout=600)
        self.bundle_data = bundle_data
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
                    vibe_transfer_switch=checking_params["vibe_transfer_switch"],
                    dynamic_thresholding=checking_params["dynamic_thresholding"],
                    skip_cfg_above_sigma=checking_params["skip_cfg_above_sigma"],
                    upscale=checking_params["upscale"],
                )
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