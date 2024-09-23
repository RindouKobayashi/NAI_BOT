import base64
import io
import re
import numpy as np
from PIL import Image, ImageOps
import math
#import torch

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

def image_to_base64(image):
    i = 255. * image[0].cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
    image_bytesIO = io.BytesIO()
    img.save(image_bytesIO, format="png")
    return base64.b64encode(image_bytesIO.getvalue()).decode()

def base64_to_image(base64_string):
    image_data = base64.b64decode(base64_string)
    image_file = io.BytesIO(image_data)
    image_file.seek(0)
    return image_file

#def bytes_to_image(image_bytes):
#    i = Image.open(io.BytesIO(image_bytes))
#    i = i.convert("RGB")
#    i = ImageOps.exif_transpose(i)
#    image = np.array(i).astype(np.float32) / 255.0
#    return torch.from_numpy(image)[None,]

def calculate_resolution(pixel_count, aspect_ratio):
    pixel_count = pixel_count / 4096
    w, h = aspect_ratio
    k = (pixel_count * w / h) ** 0.5
    width = int(np.floor(k) * 64)
    height = int(np.floor(k * h / w) * 64)
    return width, height

#def resize_image(image, size_to):
#    samples = image.movedim(-1,1)
#    w, h = size_to
#    s = torch.nn.functional.interpolate(samples, (h, w), mode="bilinear", align_corners=False)
#    s = s.movedim(1,-1)
#    return s

#def resize_to_naimask(mask, image_size=None):
#    samples = mask.movedim(-1,1)
#    w, h = (samples.shape[3], samples.shape[2]) if not image_size else image_size
#    width = int(np.ceil(w / 64) * 8)
#    height = int(np.ceil(h / 64) * 8)
#    s = torch.nn.functional.interpolate(samples, (height, width), mode="nearest")
#    s = s.movedim(1,-1)
#    return s

def naimask_to_base64(image):
    i = 255. * image[0].cpu().numpy()
    i = np.clip(i, 0, 255).astype(np.uint8)
    alpha = np.sum(i, axis=-1) > 0
    alpha = np.uint8(alpha * 255)
    rgba = np.dstack((i, alpha))
    img = Image.fromarray(rgba)
    image_bytesIO = io.BytesIO()
    img.save(image_bytesIO, format="png")
    return base64.b64encode(image_bytesIO.getvalue()).decode()

def calculate_skip_cfg_above_sigma(initial_value, width, height) -> float:
    def Ne(e, t):
        i, s = e
        return [math.floor(i / t), math.floor(s / t)]

    def je(e):
        return e[0] * e[1] * e[2]

    ze = je([4, math.floor(104), math.floor(152)])  # Constant value as before

    # Calculate the new dimensions
    c = Ne([width, height], 8)
    
    # Calculate the new value
    l = math.pow(je([4] + list(c)) / ze, 0.5)
    
    # Update and return the new skip_cfg_above_sigma value
    return initial_value * l