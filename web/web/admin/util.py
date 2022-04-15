from base64 import b64decode
from io import BytesIO
import os

from PIL import Image


async def save_image(
    folder: str, alias: str,
    filename: str, imgdata: str, prev_filename=''
):
    '''Create a image from a base64 string and 
    save it on riddle's thumbs or cheevos folder.'''

    # Get pure base64 data from URL and convert it to image
    mime, data = imgdata.split(',', maxsplit=1)
    mime += ','
    data = b64decode(data)
    img = Image.open(BytesIO(data))

    if folder == 'cheevos':
        # Center and crop cheevo image 1:1
        left, top, right, bottom = (0, 0, img.width, img.height)
        if img.width > img.height:
            left = (img.width - img.height) / 2
            right = left + img.height
        elif img.height > img.width:
            top = (img.height - img.width) / 2
            bottom = top + img.width
        box = (left, top, right, bottom)
        img = img.crop(box)

        # Resize cheevo image to 200x200
        size = (300, 300)
        img = img.resize(size)

    # Get correct riddle dir, creating it if nonexistent
    riddle_dir = f"../static/{folder}/{alias}"
    if not os.path.isdir(riddle_dir):
        os.makedirs(riddle_dir)

    # Erase previous file (if any and filename was changed)
    if prev_filename and filename != prev_filename:
        prev_path = f"{riddle_dir}/{prev_filename}"
        try:
            os.remove(prev_path)
            print(f"[{alias}] Image {prev_filename} successfully removed.")
        except (FileNotFoundError, IsADirectoryError):
            print(f"[{alias}] Couldn\'t remove image {prev_filename}.")

    # Save image on riddle's thumbs folder
    path = f"{riddle_dir}/{filename}"
    img.save(path)
    print(f"[{alias}] Image {filename} successfully saved.")
