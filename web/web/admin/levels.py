from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

from pymysql.err import IntegrityError
from quart import Blueprint, jsonify, render_template, request
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth
from admin.util import save_image
from inject import get_riddle
from levels import get_pages
from util.db import database
from webclient import bot_request

# Create app blueprint
admin_levels = Blueprint('admin_levels', __name__)


@admin_levels.route('/admin/<alias>/levels', methods=['GET', 'POST'])
@requires_authorization
async def manage_levels(alias: str):
    '''Riddle level management.'''

    # Check for admin permissions
    await admin_auth(alias)

    async def r(levels: list, secret_levels: list, msg: str):
        '''Render page with correct data.'''
        return await render_template(
            'admin/levels.htm', alias=alias,
            levels=levels, secret_levels=secret_levels, msg=msg
        )

    # Get initial level data from database
    levels_before = await _fetch_levels(alias)
    secrets_before = await _fetch_levels(alias, is_secret=True)

    # Render page normally on GET
    if request.method == 'GET':
        return await r(levels_before.values(), secrets_before.values(), '')

    # Build dicts of levels after POST
    form = await request.form
    levels_after = {}
    secrets_after = {}
    for name, value in form.items():
        i = name.find('-')
        if i == -1 or name[:i] == 'removed':
            continue
        index, attr = name[:i], name[(i+1):]
        if value == '':
            value = None
        if 's' not in index:
            index = int(index)
            if index not in levels_after:
                levels_after[index] = {}
            levels_after[index][attr] = value
        else:
            index = int(index[1:])
            if index not in secrets_after:
                secrets_after[index] = {}
            secrets_after[index][attr] = value

    # Get full guild name
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    guild_id = await database.fetch_val(
        query, {'alias': alias}, 'guild_id'
    )
    # Update both normal and secret levels
    await _update_levels(levels_before, levels_after, locals())
    await _update_levels(
        secrets_before, secrets_after, locals(), is_secret=True
    )
    # Fetch levels again to display page correctly on POST
    levels = await _fetch_levels(alias)
    secret_levels = await _fetch_levels(alias, is_secret=True)

    return await r(
        levels.values(), secret_levels.values(),
        'Guild info updated successfully!'
    )


async def _fetch_levels(alias: str, is_secret: bool = False):
    '''Fetch level info from database as an indexed dict.'''

    # Get level data from DB
    query = '''
        SELECT * FROM levels
        WHERE riddle = :riddle AND is_secret = :is_secret
        ORDER BY `index`
    '''
    values = {'riddle': alias, 'is_secret': is_secret}
    result = await database.fetch_all(query, values)
    level_list = [dict(row) for row in result]

    # Build dict of levels
    levels = {}
    for i, level in enumerate(level_list):
        if level['path'][0] == '[':
            # Multi-path support
            level['path'] = level['path'].split('"')[1]
        levels[level['index']] = level

        # Get requirements as a comma-separated list
        query = '''
            SELECT * FROM level_requirements
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        values = {'riddle': alias, 'level_name': level['name']}
        result = await database.fetch_all(query, values)
        level['requirements'] = (
            ', '.join(row['requires'] for row in result) if result
            else None
        )

    return levels


async def _update_levels(
    levels_before: dict[int, dict],
    levels_after: dict[int, dict],
    data: dict,
    is_secret: bool = False
):
    '''Update new/changed levels both on DB and guild.'''

    # Some variables for easy access
    alias, form, guild_id = data['alias'], data['form'], data['guild_id']

    async def _update_requirements(level_before: dict, level: dict):
        '''Update procedures for table `level_requirements`'''
        values = {
            'riddle': alias,
            'level_name': level.get('name') or level_before['name'],
        }
        if level['requirements'] is None:
            # Requirement removed, so delete it
            query = '''
                DELETE FROM level_requirements
                WHERE riddle = :riddle
                    AND level_name = :level_name
                    AND requires = :old_requirement
            '''
            values |= {'old_requirement': level_before['requirements']}
            await database.execute(query, values)
            return

        # Update requirement for level (if present)
        query = '''
            UPDATE level_requirements
            SET requires = :requirement
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        values |= {'requirement': level['requirements']}
        success = await database.execute(query, values)
        if not success:
            # No requirements for level yet, insert a new one
            query = '''
                INSERT INTO level_requirements
                    (riddle, level_name, requires)
                VALUES (:riddle, :level_name, :requirement)
            '''
            await database.execute(query, values)

    # Check and update existing levels
    for index, level in levels_before.items():
        # Remove fields that were not modified by admin
        for attr, value in level.items():
            if attr in levels_after[index] \
                    and value == levels_after[index][attr]:
                levels_after[index].pop(attr)

        level_before = levels_before[index]
        level = levels_after[index]
        attrs_to_be_ignored = {'added-pages', 'imgdata', 'requirements'}
        if not set(level.keys()).issubset(attrs_to_be_ignored):
            # Update level(s) database data
            query = 'UPDATE levels SET '
            values = {'riddle': alias, 'is_secret': is_secret, 'index': index}
            aux = []
            for attr, value in level.items():
                if attr in attrs_to_be_ignored:
                    continue
                s = f"`{attr}` = :{attr}"
                aux.append(s)
                if attr == 'discord_category':
                    other = 'level_set'
                    t = f"`{other}` = :{attr}"
                    aux.append(t)
                values[attr] = value
            query += ', '.join(aux)
            query += '''
                WHERE riddle = :riddle
                    AND is_secret = :is_secret AND `index` = :index
            '''
            await database.execute(query, values)

        # Swap image file on image change
        if level.get('imgdata'):
            if 'image' not in level:
                level['image'] = level_before['image']
            await save_image(
                'thumbs', alias,
                level['image'], level['imgdata'], level_before['image']
            )

        if 'requirements' in level:
            await _update_requirements(level_before, level)

        # Update Discord channels and roles names on discord_name change
        if 'discord_name' in level:
            await bot_request(
                'update', guild_id=guild_id,
                old_name=levels_before[index]['discord_name'],
                new_name=level['discord_name']
            )

    # Add new levels, if any
    if len(levels_after) > len(levels_before):
        if not is_secret and levels_before:
            # Swap winners current level (medal) for last old level
            index = len(levels_before)
            query = '''
                UPDATE riddle_accounts SET current_level = :level
                WHERE riddle = :riddle AND current_level = "🏅"
            '''
            values = {'riddle': alias, 'level': form[f"{index}-name"]}
            await database.execute(query, values)

        levels = []
        for i in range(len(levels_before) + 1, len(levels_after) + 1):
            index = str(i) if not is_secret else f"s{i}"

            # Insert new level data on database
            query = '''
                INSERT INTO levels
                (riddle, is_secret, level_set, `index`, `name`,
                    path, image, answer, `rank`,
                    discord_category, discord_name)
                VALUES (:riddle, :is_secret, :set, :index,
                    :name, :path, :image, :answer, :rank,
                    :discord_category, :discord_name)
            '''
            values = {
                'riddle': alias, 'is_secret': is_secret,
                'set': form[f"{index}-discord_category"], 'index': i,
                'name': form[f"{index}-name"], 'path': form[f"{index}-path"],
                'image': form[f"{index}-image"],
                'answer': form[f"{index}-answer"],
                'rank': form[f"{index}-rank"],
                'discord_category': form[f"{index}-discord_category"],
                'discord_name': form[f"{index}-discord_name"],
            }
            await database.execute(query, values)

            # Get image data and save image on thumbs folder
            filename = form[f"{index}-image"]
            imgdata = form[f"{index}-imgdata"]
            await save_image('thumbs', alias, filename, imgdata)

            # Append values to new levels list for bot request
            values['is_secret'] = is_secret
            levels.append(values)

            if not is_secret and (index := int(index)) > 1:
                # Automatically insert level req to previous one (if linear riddle)
                query = '''
                    INSERT IGNORE INTO level_requirements
                    VALUES (:riddle, :level, :requirement, NULL)
                '''
                values = {
                    'riddle': alias,
                    'level': form[f"{index}-name"],
                    'requirement': form[f"{index}-requirements"],
                }
                await database.execute(query, values)

        # Update Discord guild channels and roles with new levels info
        await bot_request('insert', alias=alias, levels=levels)

    # Update removed pages `level_name` field with NULL value
    aux = form['removed-pages']
    if aux:
        removed_pages = json.loads(aux)
        for page in removed_pages:
            query = '''
                UPDATE level_pages SET level_name = NULL
                WHERE riddle = :riddle AND `path` = :path
            '''
            values = {'riddle': alias, 'path': page}
            await database.execute(query, values)

    # Update pages data to changed or new levels
    for i in range(1, len(levels_after) + 1):
        index = str(i) if not is_secret else f"s{i}"
        aux = form[f"{index}-added-pages"]
        if not aux:
            continue
        added_pages = json.loads(aux)
        for page in added_pages:
            # Update path level on table
            level_to = form[f"{index}-name"]
            query = '''
                UPDATE level_pages SET level_name = :level_name
                WHERE riddle = :riddle AND `path` = :path
            '''
            values = {'riddle': alias, 'path': page, 'level_name': level_to}
            await database.execute(query, values)


@admin_levels.get('/admin/<alias>/levels/get-pages')
@requires_authorization
async def get_admin_pages(alias: str) -> str:
    '''Return a recursive JSON of all riddle folders and pages.'''

    # Check for right permissions
    await admin_auth(alias)

    return await get_pages(
        alias,
        index_by_levels=False,
        as_json=True,
        admin=True
    )


@admin_levels.get('/admin/<_alias>/level-row')
async def level_row(_alias: str):
    '''Level row HTML code to be fetched by JS script.'''
    return await render_template(
        'admin/level-row.htm', level=None,
        index=request.args['index'], image='/static/thumbs/locked.png'
    )


@requires_authorization
@admin_levels.post('/admin/<alias>/update-pages')
async def update_pages(alias: str):
    '''Update pages list with data sent by admin in text format.'''

    # Check for right permissions
    await admin_auth(alias)

    previous_level = None

    async def _process_level(level_set: str, level: str, pages: list[str]):
        '''Process individual level data.'''

        image_filename = None
        if _is_image(pages[1]):
            image_filename = await _process_image(level, pages[1])

        # Insert new level (if indeed new)
        try:
            query = '''
                INSERT INTO levels (
                    riddle, level_set, `index`, name,
                    `path`, image, discord_name
                ) VALUES (
                    :riddle, :level_set, :index, :name,
                    :path, :image, :discord_name
                )
            '''
            values = {
                'riddle': alias,
                'level_set': level_set,
                'index': int(level),
                'name': level,
                'path': pages[0],
                'image': image_filename,
                'discord_name': level.lower().replace(' ', '-')
            }
            await database.execute(query, values)
            _log(f"Added level \033[1m{level}\033[0m to the database!")
        except IntegrityError:
            _log(f"Level \033[1m{level}\033[0m already in database…")
        
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
                'answer': pages[0]
            }
            await database.execute(query, values)

        previous_level = level
    
    def _is_image(path: str) -> bool:
        '''Check if path points to an image file.'''
        _, ext = os.path.splitext(path)
        return ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    
    async def _process_image(level: str, image_path: str) -> str | None:
        '''Fetch image content from riddle website and update related info.'''

        # Retrieve image through HTTP request and save it
        image_url = f"{riddle['root_path']}{image_path}"
        print(
            f"> \033[1m[{alias}]\033[0m "
            f"Fetching level image from \033[3m{image_url}\033[0m… ",
            end=''
        )
        res = requests.get(image_url, stream=True)
        print(f"\033[1m{'OK' if res.ok else res.status_code}\033[0m")
        if res.ok:
            image_filename = os.path.basename(image_path)
            image_dir = f"../static/thumbs/{alias}"
            save_path = f"{image_dir}/{image_filename}"
            Path(image_dir).mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as image:
                shutil.copyfileobj(res.raw, image)

            # Possibly update image's filename
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
        '''Insert page into DB, possibly attached to a level.'''

        query = '''
            INSERT INTO level_pages
                (`riddle`, `path`, `level_name`)
            VALUES (:riddle, :path, :level_name);
        '''
        values = {'riddle': alias, 'path': path, 'level_name': level}

        try:
            # Add page as part of the level
            await database.execute(query, values)
            _log(
                f"Added page \033[3m{path}\033[0m "
                    f"({level}) " if level else ''
                f"to the database!"
            )

        except IntegrityError:
            # Page already present, update level if doable
            if level:
                query = '''
                    UPDATE level_pages
                    SET level_name = :level_name
                    WHERE riddle = :riddle AND `path` = :path
                '''
                success = await database.execute(query, values)
                if success:
                    _log(
                        f"Updated level"
                        f"for page \033[3m{path}\033[0m ({level})…"
                    )
                    return

            _log(f"Skipping page \033[3m{path}\033[0m ({level})…")
    
    def _log(msg: str):
        '''Log message.'''
        print(f"> \033[1m[{alias}]\033[0m {msg}", flush=True)

    # Receive text data and split it between levels (if any)
    data = (await request.data).decode('utf-8').split('#')
    riddle = await get_riddle(alias)
    has_levels = bool(len(data) > 1)
    if has_levels:
        del data[0]  # remove initial ''

    for text in data:
        # Build list of pages' paths in suitable format
        lines = text.replace('\r', '').replace('\\', '/').split('\n')
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
            path = path.strip()
            if not path:
                continue
            if '/' not in path or '.' not in path[-5:]:
                _log(f"Skipping wrong format page: \033[3m{path}\033[0m")
                continue
            await _process_page(path, level)

    return 'OK', 200
