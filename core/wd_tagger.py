import settings
from settings import logger
from gradio_client import Client, handle_file

try:
    client = Client(
        "https://smolrabbit-wd-tagger.hf.space",
        hf_token=settings.HUGGING_FACE_TOKEN,
        )
except Exception as e:
    logger.error(f"WD-TAGGER: {e}")

def predict(image_url):
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

    # Create a dictionary with the confidence data
    confidence_levels = {item['label']: item['confidence'] for item in confidence_data}
    # Get the highest confidence level item
    highest_confidence_level = max(confidence_levels, key=confidence_levels.get)
    #logger.info(f"WD-TAGGER: {confidence_levels}")
    #logger.info(f"WD-TAGGER: {character_data}")

    # Check confidence_levels and see if it's above a certain threshold
    if confidence_levels['explicit'] > 0.2:
        return confidence_levels, highest_confidence_level, True
    elif confidence_levels['questionable'] > 0.2:
        return confidence_levels, highest_confidence_level, True
    elif (confidence_levels['general'] + confidence_levels['sensitive']) < 0.5:
        return confidence_levels, highest_confidence_level, True
    else:
        return confidence_levels, highest_confidence_level, False