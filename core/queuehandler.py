import asyncio
import aiohttp
import io
import zipfile
from discord.ext import commands
from discord import Interaction, File, Message, Activity, ActivityType, AllowedMentions, CustomActivity
from settings import logger, NAI_API_TOKEN
from collections import namedtuple
from pathlib import Path
from datetime import datetime
import base64
import json
import settings
from asyncio import CancelledError
from core.dict_annotation import BundleData
from core.generation import process_txt2img, process_director_tools

from core.nai_utils import image_to_base64


class NovelAIAPI:
    BASE_URL = "https://image.novelai.net"
    OTHER_URL = "https://api.novelai.net"

    @staticmethod
    async def generate_image(session, access_token, prompt, model, action, parameters):
        data = {"input": prompt, "model": model, "action": action, "parameters": parameters}
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{NovelAIAPI.BASE_URL}/ai/generate-image", json=data, headers=headers) as response:
            response.raise_for_status()
            return await response.read()
        
    @staticmethod
    async def upscale(session, access_token, image_base64: str, width: int, height: int, scale: int):
        data = {"image": image_base64, "width": width, "height": height, "scale": scale}
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{NovelAIAPI.OTHER_URL}/ai/upscale", json=data, headers=headers) as response:
            response.raise_for_status()
            return await response.read()

class NAIQueue:
    def __init__(self, bot: commands.Bot):
        self.queue = asyncio.Queue()
        self.session = None
        self.output_dir = Path("nai_output")
        self.output_dir.mkdir(exist_ok=True)
        self.bot = bot
        self.queue_list = []
        self.user_request_count = {}

    async def add_to_queue(self, bundle_data: BundleData):
        user_id = bundle_data["interaction"].user.id
        message = bundle_data["message"]

        # Check if the user has reached the limit
        if user_id not in [125331697867816961, 396774290588041228]:
            if self.user_request_count.get(user_id, 0) >= 2:
                await message.edit(content="You have reached the maximum limit of 2 requests in the queue. Please wait for your current requests to complete before adding more.")
                return False

        position = len(self.queue_list) + 1
        bundle_data["position"] = position
        self.queue_list.append(bundle_data)
        await self.queue.put(bundle_data)

        # Increment the user's request count
        self.user_request_count[user_id] = self.user_request_count.get(user_id, 0) + 1
        await self.update_queue_positions()
        return True

    async def update_queue_positions(self):
        for i, bundle_data in enumerate(self.queue_list, start=1):
            bundle_data: BundleData
            await bundle_data['message'].edit(content=f"<a:neurowait:1269356713451065466> Your request is in queue. Current position: `{i}` <a:neurowait:1269356713451065466>")
        
        # If queue is not empty, shows it in pressence
        if self.queue_list:
            await self.bot.change_presence(activity=CustomActivity(name=f"Queue: {len(self.queue_list)}"))
        else:
            await self.bot.change_presence(activity=Activity(type=ActivityType.watching, name="you"))
    async def process_queue(self):
        self.session = aiohttp.ClientSession()
        try:
            while True:
                try:
                    # Wait for an item to be available in the queue
                    bundle_data: BundleData = await self.queue.get()
                    
                    if self.queue_list:
                        self.queue_list.pop(0)
                    else:
                        logger.warning("Queue list is empty but an item was received from the queue.")

                    # Decrement the user's request count
                    user_id = bundle_data["interaction"].user.id
                    self.user_request_count[user_id] = max(0, self.user_request_count.get(user_id, 0) - 1)

                    await self.update_queue_positions()
                    await self._process_item(bundle_data)
                    self.queue.task_done()
                except CancelledError:
                    logger.info("Queue processing was cancelled.")
                    break
                except RuntimeError as e:
                    if "attached to a different loop" in str(e):
                        #logger.warning(f"Encountered loop mismatch error: {e}. Continuing operation.")
                        # Optionally, you could add a small delay here to prevent rapid logging
                        # await asyncio.sleep(0.1)
                        pass
                    else:
                        logger.error(f"Unexpected RuntimeError in process_queue: {e}")
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error in process_queue: {str(e)}")
                    await asyncio.sleep(1)
        finally:
            if self.session and not self.session.closed:
                await self.session.close()


    async def _process_item(self, bundle_data: BundleData):
        type = bundle_data["type"]
        if type == "txt2img":
            success = await process_txt2img(self.bot, bundle_data)
        elif type == "director_tools":
            success = await process_director_tools(self.bot, bundle_data)



    async def start(self):
        self.queue_task = asyncio.create_task(self.process_queue())

    async def stop(self):
        
        # Cancel the queue processing task
        if hasattr(self, 'queue_task'):
            self.queue_task.cancel()
            try:
                await self.queue_task
            except asyncio.CancelledError:
                pass

nai_queue = None

# Function to be called when starting your bot
async def start_queue(bot):
    global nai_queue
    nai_queue = NAIQueue(bot)
    await nai_queue.start()

# Function to be called when stopping your bot
async def stop_queue():
    global nai_queue
    if nai_queue:
        await nai_queue.stop()
        nai_queue = None