import asyncio
import aiohttp
import io
import zipfile
from discord.ext import commands
from discord import Interaction, File, Message, Activity, ActivityType
from settings import logger, NAI_API_TOKEN
from collections import namedtuple
from pathlib import Path
from datetime import datetime
from main import bot

# Define a named tuple for queue items
QueueItem = namedtuple('QueueItem', ['interaction', 'params', 'message', 'position'])

class NovelAIAPI:
    BASE_URL = "https://image.novelai.net"

    @staticmethod
    async def generate_image(session, access_token, prompt, model, action, parameters):
        data = {"input": prompt, "model": model, "action": action, "parameters": parameters}
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{NovelAIAPI.BASE_URL}/ai/generate-image", json=data, headers=headers) as response:
            response.raise_for_status()
            return await response.read()

class NAIQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.session = None
        self.output_dir = Path("nai_output")
        self.output_dir.mkdir(exist_ok=True)
        self.bot = bot
        self.queue_list = []
        self.user_request_count = {}

    async def add_to_queue(self, interaction: Interaction, params: dict, message: Message):
        user_id = interaction.user.id

        # Check if the user has reached the limit
        if self.user_request_count.get(user_id, 0) >= 2:
            await message.edit(content="You have reached the maximum limit of 2 requests in the queue. Please wait for your current requests to complete before adding more.")
            return False

        position = len(self.queue_list) + 1
        item = QueueItem(interaction, params, message, position)
        self.queue_list.append(item)
        await self.queue.put(item)

        # Increment the user's request count
        self.user_request_count[user_id] = self.user_request_count.get(user_id, 0) + 1
        await self.update_queue_positions()
        return True

    async def update_queue_positions(self):
        for i, item in enumerate(self.queue_list, start=1):
            await item.message.edit(content=f"Your request is in queue. Current position: `{i}`")

    async def process_queue(self):
        self.session = aiohttp.ClientSession()
        while True:
            item = await self.queue.get()
            self.queue_list.pop(0)

            # Decrement the user's request count
            user_id = item.interaction.user.id
            self.user_request_count[user_id] = max(0, self.user_request_count.get(user_id) - 1)

            await self.update_queue_positions()
            await self._process_item(item)
            self.queue.task_done()

    async def _process_item(self, item: QueueItem):
        interaction, params, message, _ = item
        interaction: Interaction
        message : Message
        try:
            # Prepare parameters for the API call
            nai_params = {
                "width": params['width'],
                "height": params['height'],
                "n_samples": 1,
                "seed": params['seed'],
                "sampler": params['sampler'],
                "steps": params['steps'],
                "scale": params['cfg'],
                "uncond_scale": 1.0,
                "negative_prompt": params['negative'],
                "sm": False,
                "sm_dyn": False,
                "cfg_rescale": 0,
                "noise_schedule": "native",
                "legacy": False,
                "quality_toggle": False,
            }

            message = await message.edit(content="Generating image...")

            # Start the timer
            start_time = datetime.now()

            # Call the NovelAI API
            zipped_bytes = await NovelAIAPI.generate_image(
                self.session, 
                NAI_API_TOKEN, 
                params['positive'], 
                params['model'], 
                "generate", 
                nai_params
            )

            # Process the response
            zipped = zipfile.ZipFile(io.BytesIO(zipped_bytes))
            image_bytes = zipped.read(zipped.infolist()[0])

            # Save the image
            file_path = f"nai_generated_{interaction.id}.png"
            (self.output_dir / file_path).write_bytes(image_bytes)

            # Stop the timer
            end_time = datetime.now()
            elapsed_time = end_time - start_time
            elapsed_time = round(elapsed_time.total_seconds(), 2)

            # Some information
            reply_content = f"Seed: `{params['seed']}` | Elapsed time: `{elapsed_time}s`"


            # Send the image to Discord
            files = []
            file = File(f"{self.output_dir}/{file_path}")
            files.append(file)
            await message.edit(
                content=reply_content,
                attachments=files
            )

            # Check if channel posted on is 1157817614245052446 then add reaction
            if interaction.channel.id == 1157817614245052446:
                await message.add_reaction("🔎")

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            reply_content = f"An error occurred while processing your request: {str(e)}"
            await message.edit(content=reply_content)

    async def start(self):
        asyncio.create_task(self.process_queue())

    async def stop(self):
        if self.session:
            await self.session.close()

nai_queue = NAIQueue()

# Function to be called when starting your bot
async def start_queue():
    await nai_queue.start()

# Function to be called when stopping your bot
async def stop_queue():
    await nai_queue.stop()