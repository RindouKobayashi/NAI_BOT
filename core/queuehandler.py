import asyncio
import aiohttp
import io
import zipfile
from discord import Interaction, File
from settings import logger, NAI_API_TOKEN
from collections import namedtuple
from pathlib import Path

# Define a named tuple for queue items
QueueItem = namedtuple('QueueItem', ['interaction', 'params'])

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

    async def add_to_queue(self, interaction: Interaction, params: dict):
        await self.queue.put(QueueItem(interaction, params))

    async def process_queue(self):
        self.session = aiohttp.ClientSession()
        while True:
            item = await self.queue.get()
            await self._process_item(item)
            self.queue.task_done()

    async def _process_item(self, item: QueueItem):
        interaction, params = item
        interaction: Interaction
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
            file = f"nai_generated_{interaction.id}.png"
            (self.output_dir / file).write_bytes(image_bytes)

            # Send the image to Discord
            await interaction.followup.send(
                file=File(io.BytesIO(image_bytes), filename="generated_image.png")
            )

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            await interaction.followup.send(f"An error occurred while processing your request: {str(e)}")

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