import discord
from discord import app_commands
from discord.ext import commands
from settings import logger
import base64
import io
import requests
import dotenv
from os import environ as env
import zipfile
from pathlib import Path
import settings
from core.queuehandler import nai_queue
import random

# Import utility functions
from .nai_utils import prompt_to_nai, image_to_base64, bytes_to_image, calculate_resolution



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
        seed="Seed for generation (default: 0, random)",
        model="Model to use (default: nai-diffusion-3)"
    )
    async def nai(self, interaction: discord.Interaction, 
                  positive: str, 
                  negative: str = None, 
                  width: int = 832, 
                  height: int = 1216, 
                  steps: int = 28, 
                  cfg: float = 5.0, 
                  sampler: app_commands.Choice[str] = "k_euler", 
                  seed: int = 0,
                  model: str = "nai-diffusion-3"):
        logger.info(f"COMMAND 'NAI' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer()

        # Define min, max, step values
        min_cfg, max_cfg, cfg_step = 0.0, 10.0, 0.1

        try:

            await interaction.followup.send("Checking parameters...")

            # Check pixel limit
            pixel_limit = 1024*1024 if model in ("nai-diffusion-2", "nai-diffusion-3") else 640*640
            if width*height > pixel_limit:
                raise ValueError(f"Image resolution ({width}x{height}) exceeds the pixel limit ({pixel_limit}px).")
            
            # Check steps limit
            if steps > 28:
                raise ValueError("Steps must be less than or equal to 28.")
            
            # Check seed
            if seed <= 0:
                seed = random.randint(0, 9999999999)

            # Enforce cfg constraints
            cfg = max(min_cfg, min(max_cfg, round(cfg / cfg_step) * cfg_step))

            width, height = calculate_resolution(width*height, (width, height))


            # Process sampler
            if sampler != "k_euler":
                sampler = sampler.value
            #logger.info(f"Sampler: {sampler}")

            params = {
                "positive": positive,
                "negative": negative,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg": cfg,
                "sampler": sampler,
                "seed": seed,
                "model": model,
                # ... (add any other parameters you need)
            }

            
            # Add the request to the queue
            message = await interaction.edit_original_response(content="Adding your request to the queue...")
            success = await nai_queue.add_to_queue(interaction, params, message)

            if not success:
                # The message has already been edited in the add_to_queue function
                return

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.edit_original_response(content=f"An error occurred while queueing the image generation. `{str(e)}`")

async def setup(bot: commands.Bot):
    await bot.add_cog(NAI(bot))
    logger.info("COG LOADED: NAI - COG FILE: nai_cog.py")
