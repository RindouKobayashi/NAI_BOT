import settings
from settings import logger
from gradio_client import Client, handle_file
import asyncio
import time

client = None  # Lazy initialization
last_used = 0
cleanup_task = None
CLEANUP_DELAY = 300 # 5 minutes in seconds

async def _cleanup_client():
    """Background task to clean up the client after inactivity"""
    await asyncio.sleep(CLEANUP_DELAY)
    global client, cleanup_task
    if client is not None and (time.time() - last_used) >= CLEANUP_DELAY:
        logger.info("WD-TAGGER: Cleaning up client due to inactivity")
        client = None
        cleanup_task = None

def _schedule_cleanup():
    """Schedule client cleanup after delay"""
    global cleanup_task
    if cleanup_task is not None:
        cleanup_task.cancel()
    loop = asyncio.get_event_loop()
    cleanup_task = loop.create_task(_cleanup_client())

def predict(image_url, type:str = "check_nsfw"):
    global client, last_used
    last_used = time.time()

    if client is None:
        try:
            logger.info("WD-TAGGER: Initializing client on first use...")
            client = Client(
                "https://smolrabbit-wd-tagger.hf.space",
                hf_token=settings.HUGGING_FACE_TOKEN,
            )
            logger.info("WD-TAGGER: Client initialized successfully")
        except Exception as e:
            logger.error(f"WD-TAGGER: Failed to initialize client: {e}")
            raise e

    # Schedule cleanup after this usage
    _schedule_cleanup()
    #TODO: Add logic to predict image, still in testing
    #LINK: https://huggingface.co/spaces/SmolRabbit/wd-tagger
    result = client.predict(
        image = handle_file(image_url),
        model_repo = "SmilingWolf/wd-swinv2-tagger-v3",
        general_thresh = 0.5,
        general_mcut_enabled = False,
        character_thresh = 0.85,
        character_mcut_enabled = False,
        api_name = "/predict"
    )
    # Extract the confidence data from the result
    confidence_data = result[1]['confidences']
    #character_data = result[2]['confidences']
    tags_data = result[3]['confidences']

    # Create a dictionary with the confidence data
    confidence_levels = {item['label']: item['confidence'] for item in confidence_data}
    # Create a dictionary with the tags data
    tags = {item['label']: item['confidence'] for item in tags_data}
    # Get the highest confidence level item
    highest_confidence_level = max(confidence_levels, key=confidence_levels.get)
    #logger.info(f"WD-TAGGER: {confidence_levels}")
    #logger.info(f"WD-TAGGER: {character_data}")

    # Check confidence_levels and see if it's above a certain threshold
    if type == "check_nsfw":
        if confidence_levels['explicit'] + confidence_levels['questionable'] > 0.15:
            return confidence_levels, highest_confidence_level, True
        else:
            return confidence_levels, highest_confidence_level, False
    
    if type == "get_tags":
        return tags
