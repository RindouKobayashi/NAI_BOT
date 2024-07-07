import discord
from discord import app_commands
from discord.ext import commands
import settings
from settings import logger
import base64
import io
import re
import requests
from hashlib import blake2b
import argon2
from PIL import Image, ImageOps
import numpy as np
import torch


class NovelAIAPI:
    BASE_URL = "https://image.novelai.net"

    @staticmethod
    def argon_hash(email: str, password: str, size: int, domain: str) -> str:
        pre_salt = f"{password[:6]}{email}{domain}"
        blake = blake2b(digest_size=16)
        blake.update(pre_salt.encode())
        salt = blake.digest()
        raw = argon2.low_level.hash_secret_raw(password.encode(), salt, 2, int(2000000 / 1024), 1, size, argon2.low_level.Type.ID)
        hashed = base64.urlsafe_b64encode(raw).decode()
        return hashed

    @staticmethod
    def get_access_key(email: str, password: str) -> str:
        return NovelAIAPI.argon_hash(email, password, 64, "novelai_data_access_key")[:64]

    @staticmethod
    def login(key) -> str:
        response = requests.post(f"https://api.novelai.net/user/login", json={"key": key})
        response.raise_for_status()
        return response.json()["accessToken"]

    @staticmethod
    def generate_image(access_token, prompt, model, action, parameters):
        data = {"input": prompt, "model": model, "action": action, "parameters": parameters}
        response = requests.post(f"{NovelAIAPI.BASE_URL}/ai/generate-image", json=data, headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        return response.content

    @staticmethod
    def image_to_base64(image):
        i = 255. * image[0].numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        image_bytesIO = io.BytesIO()
        img.save(image_bytesIO, format="png")
        logger.info(f"TEST")
        return base64.b64encode(image_bytesIO.getvalue()).decode()

    @staticmethod
    def bytes_to_image(image_bytes):
        i = Image.open(io.BytesIO(image_bytes))
        i = i.convert("RGB")
        i = ImageOps.exif_transpose(i)
        image = np.array(i).astype(np.float32) / 255.0
        return torch.from_numpy(image)[None,]

    @staticmethod
    def calculate_resolution(pixel_count, aspect_ratio):
        pixel_count = pixel_count / 4096
        w, h = aspect_ratio
        k = (pixel_count * w / h) ** 0.5
        width = int(np.floor(k) * 64)
        height = int(np.floor(k * h / w) * 64)
        return width, height

    @staticmethod
    def prompt_to_nai(prompt, weight_per_brace=0.05):
        def prompt_to_stack(sentence):
            result = []
            current_str = ""
            stack = [{"weight": 1.0, "data": result}]
            
            for i, c in enumerate(sentence):
                if c in '()':
                    if c == '(':
                        if current_str: stack[-1]["data"].append(current_str)
                        stack[-1]["data"].append({"weight": 1.0, "data": []})
                        stack.append(stack[-1]["data"][-1])
                    elif c == ')':
                        searched = re.search(r"^(.*):([0-9\.]+)$", current_str)
                        current_str, weight = searched.groups() if searched else (current_str, 1.1)
                        if current_str: stack[-1]["data"].append(current_str)
                        stack[-1]["weight"] = float(weight)
                        if stack[-1]["data"] != result:
                            stack.pop()
                    current_str = ""
                else:
                    current_str += c
            
            if current_str:
                stack[-1]["data"].append(current_str)
            
            return result

        def prompt_stack_to_nai(l, weight_per_brace):
            result = ""
            for el in l:
                if isinstance(el, dict):
                    brace_count = round((el["weight"] - 1.0) / weight_per_brace)
                    result += "{" * brace_count + "[" * -brace_count + prompt_stack_to_nai(el["data"], weight_per_brace) + "}" * brace_count + "]" * -brace_count
                else:
                    result += el
            return result

        return prompt_stack_to_nai(prompt_to_stack(prompt.replace("\(", "（").replace("\)", "）")), weight_per_brace).replace("（", "(").replace("）",")")

class NAI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.email = settings.NAI_EMAIL  
        self.password = settings.NAI_PASSWORD  

    @app_commands.command(name="nai", description="Generate an image using NovelAI")
    @app_commands.describe(prompt="The prompt for image generation")
    async def nai(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer()

        try:
            access_key = NovelAIAPI.get_access_key(self.email, self.password)
            access_token = NovelAIAPI.login(access_key)

            nai_prompt = NovelAIAPI.prompt_to_nai(prompt)
            model = "nai-diffusion-3"  # You can change this to the desired model
            action = "generate"
            parameters = {
                "width": 512,
                "height": 768,
                "scale": 7,
                "sampler": "k_euler_ancestral",
                "steps": 28,
                "seed": 0,
                "n_samples": 1,
                "ucPreset": 0,
                "uc": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
            }

            image_bytes = NovelAIAPI.generate_image(access_token, nai_prompt, model, action, parameters)
            image = NovelAIAPI.bytes_to_image(image_bytes)
            image_base64 = NovelAIAPI.image_to_base64(image)
            logger.info(f"Image converted to base64: {image_base64}")
            await interaction.followup.send(file=discord.File(io.BytesIO(base64.b64decode(image_base64)), filename="generated_image.png"))

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.followup.send("An error occurred while generating the image. Please try again later.")

async def setup(bot: commands.Bot):
    await bot.add_cog(NAI(bot))
    logger.info("COG LOADED: NAI - COG FILE: nai_cog.py")