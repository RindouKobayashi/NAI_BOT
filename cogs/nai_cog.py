import discord
from discord import app_commands
from discord.ext import commands
from settings import logger, AUTOCOMPLETE_DATA
import base64
import io
import requests
import dotenv
import asyncio
from os import environ as env
import zipfile
from pathlib import Path
import settings
from core.queuehandler import nai_queue
import random
import json
from core.viewhandler import VibeTransferView
from core.checking_params import check_params
from core.bundle_data import BundleData

# Import utility functions
from core.nai_utils import prompt_to_nai, calculate_resolution



class NAI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if settings.NAI_API_TOKEN is not None:
            self.access_token = settings.NAI_API_TOKEN
        else:
            raise RuntimeError("Please ensure that NAI_ACCESS_TOKEN is set in your .env file.")
        
        self.output_dir = "nai_output"

    @app_commands.command(name="nai", description="Generate an image using NovelAI")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.choices(
        sampler=[
            app_commands.Choice(name="k_euler", value="k_euler"),
            app_commands.Choice(name="k_euler_ancestral", value="k_euler_ancestral"),
            app_commands.Choice(name="k_dpmpp_2s_ancestral", value="k_dpmpp_2s_ancestral"),
            app_commands.Choice(name="k_dpmpp_2m", value="k_dpmpp_2m"),
            app_commands.Choice(name="k_dpmpp_sde", value="k_dpmpp_sde"),
            app_commands.Choice(name="ddim", value="ddim"),
        ],
        model=[
            app_commands.Choice(name="nai-diffusion-3", value="nai-diffusion-3"),
            app_commands.Choice(name="nai-diffusion-2", value="nai-diffusion-2"),
            app_commands.Choice(name="nai-diffusion", value="nai-diffusion"),
            app_commands.Choice(name="safe-diffusion", value="safe-diffusion"),
            app_commands.Choice(name="nai-diffusion-furry", value="nai-diffusion-furry"),
            app_commands.Choice(name="nai-diffusion-furry-3", value="nai-diffusion-furry-3"),
        ],
        undesired_content_presets=[
            app_commands.Choice(name="Heavy", value="heavy"),
            app_commands.Choice(name="Light", value="light"),
            app_commands.Choice(name="Human_Focus", value="human_focus"),
            app_commands.Choice(name="None", value="none"),
        ],
        smea=[
            app_commands.Choice(name="SMEA", value="SMEA"),
            app_commands.Choice(name="SMEA+DYN", value="SMEA+DYN"),
            app_commands.Choice(name="None", value="None"),
        ]
    )
    @app_commands.describe(
        positive="Positive prompt for image generation",
        negative="Negative prompt for image generation",
        width="Image width (default: 832)",
        height="Image height (default: 1216)",
        steps="Number of steps (default: 28)",
        cfg="CFG scale (default: 5.0)",
        sampler="Sampling method (default: k_euler)",
        smea="SMEA and SMEA+DYN versions of samplers perform better at high res (default: None)",
        seed="Seed for generation (default: 0, random)",
        model="Model to use (default: nai-diffusion-3)",
        quality_toggle="Tags to increase qualityh will be prepended to the prompt (default: True)",
        undesired_content_presets="Undesired content presets (default: Heavy)",
        prompt_conversion_toggle="Convert Auto1111 way of prompt to NovelAI way of prompt (default: False)",
        upscale="Upscale image by 4x. Only available for images up to 640x640 (default: False)",
        vibe_transfer_switch="Vibe transfer switch (default: False)",
    )
    async def nai(self, interaction: discord.Interaction, 
                  positive: str, 
                  negative: str = None, 
                  width: int = 832, 
                  height: int = 1216, 
                  steps: int = 28, 
                  cfg: float = 5.0, 
                  sampler: app_commands.Choice[str] = "k_euler", 
                  smea: app_commands.Choice[str] = "None",
                  seed: int = 0,
                  model: app_commands.Choice[str] = "nai-diffusion-3",
                  quality_toggle: bool = True,
                  undesired_content_presets: app_commands.Choice[str] = "heavy",
                  prompt_conversion_toggle: bool = False,
                  upscale: bool = False,
                  vibe_transfer_switch: bool = False,
                  ):
        logger.info(f"COMMAND 'NAI' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer()

        try:

            await interaction.followup.send("Checking parameters...")

            checking_params = {
                "positive": positive,
                "negative": negative,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg": cfg,
                "sampler": sampler,
                "smea": smea,
                "seed": seed,
                "model": model,
                "quality_toggle": quality_toggle,
                "undesired_content_presets": undesired_content_presets,
                "prompt_conversion_toggle": prompt_conversion_toggle,
                "upscale": upscale,
                "vibe_transfer_switch": vibe_transfer_switch
            }

            checking_params = await check_params(checking_params, interaction)

            # Unpack the parameters       
            params = {
                "positive": checking_params["positive"],
                "negative": checking_params["negative"],
                "width": checking_params["width"],
                "height": checking_params["height"],
                "steps": checking_params["steps"],
                "cfg": checking_params["cfg"],
                "sampler": checking_params["sampler"],
                "sm": checking_params["sm"],
                "sm_dyn": checking_params["sm_dyn"],
                "seed": checking_params["seed"],
                "model": checking_params["model"],
                "vibe_transfer_switch": checking_params["vibe_transfer_switch"],
                "upscale": checking_params["upscale"],
            }

            message = await interaction.edit_original_response(content="Adding your request to the queue...")

            # Create a bundle_data that contains all the parameters
            bundle_data: BundleData = {
                "request_id": str(settings.uuid.uuid4()),
                "interaction": interaction,
                "message": message,
                "params": params,
                "checking_params": checking_params
            }
            
            # Add the request to the queue
            
            success = await nai_queue.add_to_queue(bundle_data)

            if not success:
                # The message has already been edited in the add_to_queue function
                return

        except Exception as e:
            #logger.error(f"Error in NAI command: {str(e)}")
            #await interaction.edit_original_response(content=f"An error occurred while queueing the image generation. {str(e)}")
            pass

    @nai.autocomplete('positive')
    async def nai_positive_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        def search_current_term(query):
            terms = query.split(',')
            current_term = terms[-1].strip().lower()
            
            if not current_term:
                return []

            results = [
                tag for tag in AUTOCOMPLETE_DATA
                if tag.lower().startswith(current_term)
            ]

            return results[:25]  # Limit to 25 results as per Discord's limit

        results = await asyncio.to_thread(search_current_term, current)
        
        # Prepare the choices, including the parts of the query that are already typed
        prefix = ','.join(current.split(',')[:-1]).strip()
        if prefix:
            prefix += ', '
        
        valid_choices = [
            app_commands.Choice(name=f"{prefix}{item}"[:100], value=f"{prefix}{item}"[:100])
            for item in results
            if len(item) > 0  # Ensure item is not empty
        ]
        
        return valid_choices
    @nai.autocomplete('negative')
    async def nai_positive_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        def search_current_term(query):
            terms = query.split(',')
            current_term = terms[-1].strip().lower()
            
            if not current_term:
                return []

            results = [
                tag for tag in AUTOCOMPLETE_DATA
                if tag.lower().startswith(current_term)
            ]

            return results[:25]  # Limit to 25 results as per Discord's limit

        results = await asyncio.to_thread(search_current_term, current)
        
        # Prepare the choices, including the parts of the query that are already typed
        prefix = ','.join(current.split(',')[:-1]).strip()
        if prefix:
            prefix += ', '
        
        valid_choices = [
            app_commands.Choice(name=f"{prefix}{item}"[:100], value=f"{prefix}{item}"[:100])
            for item in results
            if len(item) > 0  # Ensure item is not empty
        ]
        
        return valid_choices
    

    @app_commands.command(name="vibe_transfer", description="Store reference images for vibe transfer with info and strength value")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        image_1="Reference image 1",
        image_1_info_extracted="Extracted image 1 info",
        image_1_ref_strength="Reference image 1 strength",
        image_2="Reference image 2",
        image_2_info_extracted="Extracted image 2 info",
        image_2_ref_strength="Reference image 2 strength",
        image_3="Reference image 3",
        image_3_info_extracted="Extracted image 3 info",
        image_3_ref_strength="Reference image 3 strength",
        image_4="Reference image 4",
        image_4_info_extracted="Extracted image 4 info",
        image_4_ref_strength="Reference image 4 strength",
        image_5="Reference image 5",
        image_5_info_extracted="Extracted image 5 info",
        image_5_ref_strength="Reference image 5 strength",
    )
    async def vibe_trasnfer(self, interaction: discord.Interaction,
                            image_1: discord.Attachment,
                            image_1_info_extracted: float,
                            image_1_ref_strength: float,
                            image_2: discord.Attachment = None,
                            image_2_info_extracted: float = None,
                            image_2_ref_strength: float = None,
                            image_3: discord.Attachment = None,
                            image_3_info_extracted: float = None,
                            image_3_ref_strength: float = None,
                            image_4: discord.Attachment = None,
                            image_4_info_extracted: float = None,
                            image_4_ref_strength: float = None,
                            image_5: discord.Attachment = None,
                            image_5_info_extracted: float = None,
                            image_5_ref_strength: float = None,
                            ):
        logger.info(f"COMMAND 'VIBE_TRANSFER' USED BY: {interaction.user} ({interaction.user.id})")

        await interaction.response.defer(ephemeral=True)

        try:
            # Prepare lists of images and their corresponding info and strength values
            images = [image_1, image_2, image_3, image_4, image_5]
            infos = [image_1_info_extracted, image_2_info_extracted, image_3_info_extracted, image_4_info_extracted, image_5_info_extracted]
            strengths = [image_1_ref_strength, image_2_ref_strength, image_3_ref_strength, image_4_ref_strength, image_5_ref_strength]

            # Check values are between 0 and 1 for all strength values and info extracted values
            for info, strength in zip(infos, strengths):
                if info is not None and not 0 <= info <= 1:
                    raise ValueError("Info extracted value must be between 0 and 1.")
                if strength is not None and not 0 <= strength <= 1:
                    raise ValueError("Reference strength value must be between 0 and 1.")
                    
            # Check all attachments are valid images
            for attachment in images:
                if attachment is not None and not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    raise ValueError("Only PNG, JPG, JPEG and WebP images are supported.")

            # Create a json file named their user ID storing in database
            user_id = str(interaction.user.id)
            user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{user_id}.json"

            json_data = []

            for image, info, strength in zip(images, infos, strengths):
                if image is not None:
                    image_bytes = await image.read()
                    image_string = base64.b64encode(image_bytes).decode("utf-8")
                    json_data.append({
                        "image": image_string,
                        "info_extracted": info,
                        "ref_strength": strength
                    })

            with open(user_file_path, "w") as f:
                json.dump(json_data, f, indent=4)

            await interaction.edit_original_response(content="Vibe transfer data saved successfully.")

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.edit_original_response(content=f"An error occurred while processing the command. `{str(e)}`")

    @app_commands.command(name="view_vibe_transfer", description="View your saved vibe transfer data and edit them")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def view_vibe_transfer(self, interaction: discord.Interaction, ephemeral: bool = True):
        logger.info(f"COMMAND 'VIEW_VIBE_TRANSFER' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer(ephemeral=ephemeral)
        pagination_view = VibeTransferView(interaction=interaction)
        await pagination_view.send()

"""     async def check_params(self, checking_params: dict, interaction: discord.Interaction):
        
        try:

            # Check if command used in server ANIMEAI_SERVER
            if interaction.guild_id == settings.ANIMEAI_SERVER:
                # Check if command used in channel IMAGE_GEN_BOT_CHANNEL
                if interaction.channel_id != settings.IMAGE_GEN_BOT_CHANNEL:
                    raise ValueError(f"`Command can only be used in `<#{settings.IMAGE_GEN_BOT_CHANNEL}>")
                
            # Process model
            if checking_params["model"] != "nai-diffusion-3":
                checking_params["model"] = checking_params["model"].value

            # Check pixel limit
            pixel_limit = 1024*1024 if checking_params["model"] in ("nai-diffusion-2", "nai-diffusion-3", "nai-diffusion-furry-3") else 640*640
            if checking_params["width"] * checking_params["height"] > pixel_limit:
                raise ValueError(f"`Image resolution ({checking_params['width']}x{checking_params['height']}) exceeds the pixel limit ({pixel_limit}px).`")

            # Check upscale
            if checking_params["upscale"] == True:
                # Check if width x height <= 640 x 640
                if checking_params["width"] * checking_params["height"] > 640 * 640:
                    raise ValueError(f"`Image resolution ({checking_params['width']}x{checking_params['height']}) exceeds the pixel limit (640x640) for upscaling.`")
            
            # Check steps limit
            if checking_params["steps"] > 28:
                raise ValueError(f"`Steps ({checking_params['steps']}) exceeds the steps limit (28).`")
            
            # Check seed
            if checking_params["seed"] <= 0:
                checking_params["seed"] = random.randint(0, 9999999999)

            # Enforce cfg constraint
            min_cfg, max_cfg, cfg_step = 0.0, 10.0, 0.1
            checking_params["cfg"] = max(min_cfg, min(max_cfg, round(checking_params["cfg"] / cfg_step) * cfg_step))
            
            checking_params["width"], checking_params["height"] = calculate_resolution(checking_params["width"]*checking_params["height"], (checking_params["width"], checking_params["height"]))

            # Process sampler and SMEA
            if checking_params["sampler"] != "k_euler":
                checking_params["sampler"] = checking_params["sampler"].value
            if checking_params["smea"] != "None":
                checking_params["smea"] = checking_params["smea"].value
                if checking_params["smea"] == "SMEA":
                    checking_params["sm"] = True
                    checking_params["sm_dyn"] = False
                elif checking_params["smea"] == "SMEA+DYN":
                    checking_params["sm"] = True
                    checking_params["sm_dyn"] = True
                else:
                    checking_params["sm"] = False
                    checking_params["sm_dyn"] = False
            elif checking_params["smea"] == "None":
                checking_params["sm"] = False
                checking_params["sm_dyn"] = False

            # Process prompt and negative prompt with function prompt_to_nai if prompt_conversion_toggle is True
            if checking_params["prompt_conversion_toggle"]:
                checking_params["prompt"] = prompt_to_nai(checking_params["prompt"])
                if checking_params["negative"] is not None:
                    checking_params["negative"] = prompt_to_nai(checking_params["negative"])

            # Process negative prompt with tags
            if checking_params["undesired_content_presets"] == "heavy":
                checking_params["undesired_content_presets"] = app_commands.Choice(name="heavy", value="heavy")
            if checking_params["undesired_content_presets"] != None:
                # Check if negative prompt is empty
                if checking_params["negative"] is None:
                    checking_params["negative"] = ""
                if checking_params["undesired_content_presets"].value == "heavy":
                    # Check model to see what tags to add
                    if checking_params["model"] == "nai-diffusion-3":
                        checking_params["negative"] +=  "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract]," + checking_params["negative"]
                    elif checking_params["model"] == "nai-diffusion-2":
                        checking_params["negative"] = "lowres, bad, text, error, missing, extra, fewer, cropped, jpeg artifacts, worst quality, bad quality, watermark, displeasing, unfinished, chromatic aberration, scan, scan artifacts," + checking_params["negative"]
                    elif checking_params["model"] == "nai-diffusion-furry" or checking_params["model"] == "nai-diffusion-furry-3":
                        checking_params["negative"] = "{{worst quality}}, [displeasing], {unusual pupils}, guide lines, {{unfinished}}, {bad}, url, artist name, {{tall image}}, mosaic, {sketch page}, comic panel, impact (font), [dated], {logo}, ych, {what}, {where is your god now}, {distorted text}, repeated text, {floating head}, {1994}, {widescreen}, absolutely everyone, sequence, {compression artifacts}, hard translated, {cropped}, {commissioner name}, unknown text, high contrast," + checking_params["negative"]
                elif checking_params["undesired_content_presets"].value == "light":
                    # Check model to see what tags to add
                    if checking_params["model"] == "nai-diffusion-3" or checking_params["model"] == "nai-diffusion-2":
                        checking_params["negative"] = "lowres, jpeg artifacts, worst quality, watermark, blurry, very displeasing," + checking_params["negative"]
                    elif checking_params["model"] == "nai-diffusion-furry" or checking_params["model"] == "nai-diffusion-furry-3":
                        checking_params["negative"] = "{worst quality}, guide lines, unfinished, bad, url, tall image, widescreen, compression artifacts, unknown text," + checking_params["negative"]
                elif checking_params["undesired_content_presets"].value == "human_focus":
                    # Check model to see what tags to add
                    if checking_params["model"] == "nai-diffusion-3":
                        checking_params['negative'] = "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract], bad anatomy, bad hands, @_@, mismatched pupils, heart-shaped pupils, glowing eyes," + checking_params['negative']

            return checking_params

        except Exception as e:
            logger.error(f"Error in check_params: {e}")
            await interaction.edit_original_response(content=f"{str(e)}")
 """            

async def setup(bot: commands.Bot):
    await bot.add_cog(NAI(bot))
    logger.info("COG LOADED: NAI - COG FILE: nai_cog.py")
