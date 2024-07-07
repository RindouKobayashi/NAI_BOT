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

# Import utility functions
from .nai_utils import prompt_to_nai, image_to_base64, bytes_to_image, calculate_resolution

class NovelAIAPI:
    BASE_URL = "https://image.novelai.net"

    @staticmethod
    def generate_image(access_token, prompt, model, action, parameters):
        data = {"input": prompt, "model": model, "action": action, "parameters": parameters}
        response = requests.post(f"{NovelAIAPI.BASE_URL}/ai/generate-image", json=data, headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        return response.content

class NAI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if settings.NAI_API_TOKEN is not None:
            self.access_token = settings.NAI_API_TOKEN
        else:
            raise RuntimeError("Please ensure that NAI_ACCESS_TOKEN is set in your .env file.")
        
        self.output_dir = "nai_output"  # You may want to customize this

    @app_commands.command(name="nai", description="Generate an image using NovelAI")
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
                  negative: str = "lowres", 
                  width: int = 832, 
                  height: int = 1216, 
                  steps: int = 28, 
                  cfg: float = 5.0, 
                  sampler: str = "k_euler", 
                  seed: int = 0,
                  model: str = "nai-diffusion-3"):
        await interaction.response.defer()

        try:
            width, height = calculate_resolution(width*height, (width, height))

            params = {
                "width": width,
                "height": height,
                "n_samples": 1,
                "seed": seed,
                "sampler": sampler,
                "steps": steps,
                "scale": cfg,
                "uncond_scale": 1.0,
                "negative_prompt": negative,
                "sm": False,
                "sm_dyn": False,
                "cfg_rescale": 0,
                "noise_schedule": "native",
                "legacy": False,
                "quality_toggle": False,
            }

            # Check pixel limit
            pixel_limit = 1024*1024 if model in ("nai-diffusion-2", "nai-diffusion-3") else 640*640
            if width*height > pixel_limit:
                raise ValueError(f"Image resolution ({width}x{height}) exceeds the pixel limit ({pixel_limit}px).")

            # Check steps limit
            if steps > 28:
                raise ValueError("Steps must be less than or equal to 28.")

            action = "generate"
            nai_prompt = prompt_to_nai(positive)

            zipped_bytes = NovelAIAPI.generate_image(self.access_token, nai_prompt, model, action, params)
            zipped = zipfile.ZipFile(io.BytesIO(zipped_bytes))
            image_bytes = zipped.read(zipped.infolist()[0])  # only support one n_samples

            # Save the image
            full_output_folder = Path(self.output_dir)
            full_output_folder.mkdir(exist_ok=True)
            file = f"nai_generated_{interaction.id}.png"
            (full_output_folder / file).write_bytes(image_bytes)

            # Send the image to Discord
            await interaction.followup.send(file=discord.File(io.BytesIO(image_bytes), filename="generated_image.png"))

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.followup.send(f"An error occurred while generating the image. `{str(e)}`")

async def setup(bot: commands.Bot):
    await bot.add_cog(NAI(bot))
    logger.info("COG LOADED: NAI - COG FILE: nai_cog.py")