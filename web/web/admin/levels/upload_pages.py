import os
from pathlib import Path
import shutil
from typing import Self

from pymysql.err import IntegrityError
from quart import Blueprint, request
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth
from admin.levels.updater import LevelUpdater
from util.db import database

# Create app blueprint
admin_upload_pages = Blueprint('admin_upload_pages', __name__)


@requires_authorization
@admin_upload_pages.post('/admin/<alias>/levels/upload-pages')
async def upload_pages(alias: str):
    '''Update page/level data through upload in text format.'''

    await admin_auth(alias)

    # Receive text data and split it between levels (if any)
    data = (await request.data).decode('utf-8')
    blocks = filter(lambda text: text.strip(), data.split('#'))

    RiddleLevelUpdater = await LevelUpdater.create(alias)
    for block in blocks:
        # Build list of sanitized pages' paths
        lines = [
            line.strip().replace('\\', '/').replace('\r', '')
            for line in block.split('\n')
        ]
        paths = list(filter(None, lines[1:]))

        # Extract level/set names (if present)
        tokens = map(lambda s: s.strip() or None, lines[0].split('--'))
        level_name = next(tokens, None)
        set_name = next(tokens, None)

        # Init updater object and process level (save for levelless blocks)
        lu = RiddleLevelUpdater(level_name, set_name, paths)
        if level_name:
            await lu.process_level()
            if paths[1:] and _is_image(image_path := paths[1]):
                await lu.process_image(image_path)

        # Process individual pages
        for path in paths:
            if not path.startswith('/'):
                lu.log(f"Skipping wrong format path: \033[3;9m{path}\033[0m")
                continue
            await lu.process_page(path)

    return 'OK', 200


def _is_image(path: str) -> bool:
    '''Check if path points to an image file.'''
    _, ext = os.path.splitext(path)
    return ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
