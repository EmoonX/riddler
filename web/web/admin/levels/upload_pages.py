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

    # Check for right permissions
    await admin_auth(alias)

    # Receive text data and split it between levels (if any)
    data = (await request.data).decode('utf-8')
    has_levels = '#' in data
    parts = filter(
        lambda text: text and not text.isspace(),
        data.split('#')
    )

    _LevelUpdater = await LevelUpdater.create(alias)
    set_name = None
    for text in parts:
        # Build list of pages' paths in suitable format
        lines = [
            line.strip()
            for line in text.replace('\r', '').replace('\\', '/').split('\n')
        ]
        pages = list(filter(None, lines[1:]))

        if has_levels:
            # Get level info (given '#' is present)
            if '--' in lines[0]:
                level_name, set_name = map(
                    lambda s: s.strip(),
                    lines[0].split('--'),
                )
            else:
                level_name = lines[0].strip()
            lu = _LevelUpdater(level_name, set_name, pages)
            await lu.process_level()

        # Insert/update individual pages
        for path in pages:
            if '/' not in path or '.' not in path[-5:]:
                _log(f"Skipping wrong format page: \033[3m{path}\033[0m")
                continue
            await lu.process_page(path)

    return 'OK', 200
