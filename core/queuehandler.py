import asyncio
import aiohttp
import io
import zipfile
from discord.ext import commands
from discord import Interaction, File, Message, Activity, ActivityType
from settings import logger, NAI_API_TOKEN, DATABASE_DIR
from collections import namedtuple
from pathlib import Path
from datetime import datetime
from main import bot
import base64
import json
import settings
from asyncio import CancelledError

# Import utility functions (image_to_base64)
from cogs.nai_utils import image_to_base64

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
            try:
                # Wait for an item to be available in the queue
                item = await self.queue.get()
                
                if self.queue_list:
                    self.queue_list.pop(0)
                else:
                    logger.warning("Queue list is empty but an item was received from the queue.")

                # Decrement the user's request count
                user_id = item.interaction.user.id
                self.user_request_count[user_id] = max(0, self.user_request_count.get(user_id, 0) - 1)

                await self.update_queue_positions()
                await self._process_item(item)
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
            }
            #logger.info(f"Generating image with parameters: {nai_params}")

            # Check if vibe transfer is enabled
            if params['vibe_transfer_switch']:
                # Extract image, info and strength value from user database
                user_file_path = f"{DATABASE_DIR}/{interaction.user.id}.json"
                nai_params['reference_image_multiple'] = []
                nai_params['reference_information_extracted_multiple'] = []
                nai_params['reference_strength_multiple'] = []

                if Path(user_file_path).exists():
                    with open(user_file_path, "r") as user_file:
                        user_data = json.load(user_file)
                        for entry in user_data:
                            # Append image, info_extracted and ref_strength to nai_params
                            nai_params['reference_image_multiple'].append(entry['image'])
                            nai_params['reference_information_extracted_multiple'].append(entry['info_extracted'])
                            nai_params['reference_strength_multiple'].append(entry['ref_strength'])


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
            file_path = f"nai_generated_{interaction.user.id}.png"
            (self.output_dir / file_path).write_bytes(image_bytes)

            # Stop the timer
            end_time = datetime.now()
            elapsed_time = end_time - start_time
            elapsed_time = round(elapsed_time.total_seconds(), 2)

            # Some information
            reply_content = f"Seed: `{params['seed']}` | Elapsed time: `{elapsed_time}s`\nBy: {interaction.user.mention}"


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

            # Check if channel posted on is 1261084844230705182 then add reaction
            logger.info(f"{interaction.channel.id} = {settings.CHANNEL_ID_TEST}")
            if interaction.channel.id == settings.CHANNEL_ID_TEST:
                logger.info(f"Adding reaction to {message.id}")
                await message.add_reaction("🗑️")

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