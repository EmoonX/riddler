import os
from pathlib import Path
import shutil

from pymysql.err import IntegrityError
from quart import Blueprint, request
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth
from credentials import get_path_credentials
from inject import get_riddle
from util.db import database

# Create app blueprint
admin_upload_pages = Blueprint('admin_upload_pages', __name__)


@requires_authorization
@admin_upload_pages.post('/admin/<alias>/levels/upload-pages')
async def upload_pages(alias: str):
    '''Upload page list with data sent by admin in text format.'''

    # Check for right permissions
    await admin_auth(alias)

    previous_level = None

    async def _process_level(level_set: str | None, level: str, pages: list[str]):
        '''Process individual level data.'''

        nonlocal previous_level
        if previous_level:
            # Set previous level's answer as current one's front path
            query = '''
                UPDATE levels
                SET answer = :answer
                WHERE riddle = :riddle AND name = :name
            '''
            values = {
                'riddle': alias,
                'name': previous_level,
                'answer': pages[0],
            }
            await database.execute(query, values)

        image_filename = None
        if pages[1:] and _is_image(pages[1]):
            image_filename = await _process_image(level, pages[1])

        # Insert new level (if indeed new)
        query = '''
            INSERT INTO levels (
                riddle, level_set, set_index, `index`, name,
                `path`, image, discord_category, discord_name
            ) VALUES (
                :riddle, :level_set, :set_index, :index, :name,
                :path, :image, :discord_category, :discord_name
            )
        '''
        values = {
            'riddle': alias,
            'set_index': 1,
            'level_set': level_set,
            'index': abs(int(level)) if level.isdigit() else 0,
            'name': level,
            'path': pages[0],
            'image': image_filename,
            'discord_category': level_set,
            'discord_name': level.lower().replace(' ', '-')
        }
        try:
            await database.execute(query, values)
        except IntegrityError:
            _log(f"Level \033[1m{level}\033[0m already in database…")
        else:
            _log(f"Added level \033[1m{level}\033[0m to the database.")
            if previous_level:
                await _add_requirement(level, previous_level)

        previous_level = level

    async def _add_requirement(level: str, requires: str):
        query = '''
            INSERT IGNORE INTO level_requirements
                (riddle, level_name, requires)
            VALUES (:riddle, :level_name, :requires)
        '''
        values = {'riddle': alias, 'level_name': level, 'requires': requires}
        await database.execute(query, values)

    def _is_image(path: str) -> bool:
        '''Check if path points to an image file.'''
        _, ext = os.path.splitext(path)
        return ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']

    async def _process_image(level: str, image_path: str) -> str | None:
        '''Fetch image content from riddle website and update related info.'''

        # Send HTTP request to retrieve image file
        image_url = f"{riddle['root_path']}{image_path}"
        credentials = await get_path_credentials(alias, image_path)
        if username := credentials['username']:
            password = credentials['password']
            image_url = image_url.replace('://', f"://{username}:{password}@")
        print(
            f"> \033[1m[{alias}]\033[0m "
            f"Fetching level image from \033[3m{image_url}\033[0m… ",
            end=''
        )
        res = requests.get(image_url, stream=True)
        print(f"\033[1m{'OK' if res.ok else res.status_code}\033[0m")

        if res.ok:
            # Image found and retrieved, so save it
            image_filename = os.path.basename(image_path)
            image_dir = f"../static/thumbs/{alias}"
            save_path = f"{image_dir}/{image_filename}"
            Path(image_dir).mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as image:
                shutil.copyfileobj(res.raw, image)

            # Add or update image's filename
            query = '''
                UPDATE levels
                SET image = :image
                WHERE riddle = :riddle AND name = :name
            '''
            values = {
                'riddle': alias,
                'name': level,
                'image': image_filename
            }
            await database.execute(query, values)

            return image_filename

        return None

    async def _process_page(path: str, level: str | None = None):
        '''Insert/update page in DB, possibly attached to a level.'''

        query = '''
            INSERT INTO level_pages
                (`riddle`, `path`, `level_name`)
            VALUES (:riddle, :path, :level_name);
        '''
        values = {'riddle': alias, 'path': path, 'level_name': level}
        try:
            # Add page as part of the level
            await database.execute(query, values)
        except IntegrityError:
            # Page already present, update level if suitable
            if level:
                query = '''
                    UPDATE level_pages
                    SET level_name = :level_name
                    WHERE riddle = :riddle AND path = :path
                '''
                if await database.execute(query, values):
                    _log(
                        f"Updated level "
                        f"for page \033[3m{path}\033[0m ({level})…"
                    )
                    return
            _log(f"Skipping page \033[3m{path}\033[0m ({level})…")
        else:
            _log(
                f"Added page \033[3m{path}\033[0m "
                f"({level}) " if level else ''
                'to the database!'
            )

    def _log(msg: str):
        '''Log message.'''
        print(f"> \033[1m[{alias}]\033[0m {msg}", flush=True)

    # Receive text data and split it between levels (if any)
    data = (await request.data).decode('utf-8')
    has_levels = '#' in data
    parts = filter(
        lambda text: text and not text.isspace(),
        data.split('#')
    )

    riddle = await get_riddle(alias)
    level_set = None
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
                level, level_set = map(lambda s: s.strip(), lines[0].split('--'))
            else:
                level = lines[0].strip()

            await _process_level(level_set, level, pages)

        # Insert/update individual pages
        for path in pages:
            if not path:
                continue
            if '/' not in path or '.' not in path[-5:]:
                _log(f"Skipping wrong format page: \033[3m{path}\033[0m")
                continue
            await _process_page(path, level)

    return 'OK', 200
