from collections import defaultdict
import json

from quart import Blueprint, render_template, request
from quartcord import requires_authorization

from admin.admin_auth import admin_auth
from admin.util import save_image
from levels import get_pages
from util.db import database

# Create app blueprint
admin_levels = Blueprint('admin_levels', __name__)


@admin_levels.route('/admin/<alias>/levels', methods=['GET', 'POST'])
@requires_authorization
async def manage_levels(alias: str):
    '''Riddle level management.'''

    # Check for admin permissions
    await admin_auth(alias)

    async def r(levels_by_set: dict[int, dict], msg: str):
        '''Render page with correct data.'''
        return await render_template(
            'admin/levels.htm',
            alias=alias, levels_by_set=levels_by_set, msg=msg,
        )

    # Get initial level data from database
    levels_by_set = await _fetch_levels(alias)

    # Render page normally on GET
    # if request.method == 'GET':
    return await r(levels_by_set, '')

    # Build set-less dict of current levels
    levels_before = {}
    for set_levels in levels_by_set.values():
        levels_before &= set_levels

    # Build dict of post-POST levels
    form = await request.form
    levels_after = {}
    for name, value in form.items():
        i = name.find('-')
        if i == -1 or name[:i] == 'removed':
            continue
        index, attr = name[:i], name[(i+1):]
        if value == '':
            value = None
        index = int(index)
        if index not in levels_after:
            levels_after[index] = {}
        levels_after[index][attr] = value

    # Update levels
    await _update_levels(alias, form)
    
    # Fetch levels again (to correctly display page on POST)
    levels = await _fetch_levels(alias)

    return await r(levels, 'Level data updated successfully!')


async def _fetch_levels(alias: str) -> dict[int, dict]:
    '''Fetch level data as a nested {level sets -> levels} dict.'''

    # Retrieve level data from DB
    query = '''
        SELECT * FROM levels
        WHERE riddle = :riddle
        ORDER BY set_index, `index`
    '''
    result = await database.fetch_all(query, {'riddle': alias})
    levels = [dict(level) for level in result]

    # Build dict of {level sets -> levels}
    levels_by_set = defaultdict(dict[str, dict])
    for level in levels:
        # Multi-path support
        try:
            paths = json.loads(level['path'])
        except json.decoder.JSONDecodeError:
            pass
        else:
            level['path'] = paths[0]

        # Fetch requirements as a comma-separated list
        query = '''
            SELECT * FROM level_requirements
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        values = {'riddle': alias, 'level_name': level['name']}
        requirements = await database.fetch_all(query, values)
        level['requirements'] = \
            ', '.join(row['requires'] for row in requirements)

        levels_by_set[level['set_index']][level['index']] = level

    return levels_by_set


async def _update_levels(alias: str, data: dict):
    '''Update new/changed levels both on DB and guild.'''

    # Some variables for easy access
    form, guild_id = data['form'], data['guild_id']

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

    # Retrieve current level data
    query = '''
        SELECT * FROM levels
        WHERE riddle = :riddle
    '''
    levels = await database.fetch_all(query, {'riddle': alias})

    if imgdata := data.pop('imgdata', None):
        # Replace image file (and possibly rename it) on image change
        await save_image(
            'thumbs', alias, data['image'], imgdata, level['image']
        )

    await _update_requirements(data, level)
    del data['requirements']

    # Update Discord channels and roles names on discord_name change
    if discord_name := level.pop('discord_name', None):
        await bot_request(
            'update', guild_id=guild_id,
            old_name=levels_before[index]['discord_name'],
            new_name=discord_name
        )

    # Check and update existing levels
    for id, level in levels.items():
        set_index, index = map(int, id.split('-'))
        for attr, value in level.items():
            if attr in ['added-pages', 'imgdata', 'requirements']:
                continue
            query = f"""
                UPDATE levels
                SET {attr} = :attr
                WHERE riddle = :riddle
                    AND set_index = :set_index
                    AND `index` = :index
                    AND {attr} != :attr
            """
            values = {
                'riddle': alias,
                'set_index': set_index,
                'index': index,
                'attr': attr
            }
            await database.execute(query, values)

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
            # Insert new level data on database
            index = str(i) if not is_secret else f"s{i}"
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
                'riddle': alias, 'is_secret': is_secret or None,
                'set': form[f"{index}-discord_category"], 'index': i,
                'name': form[f"{index}-name"], 'path': form[f"{index}-path"],
                'image': form[f"{index}-image"] or '/static/images/locked.png',
                'answer': form[f"{index}-answer"],
                'rank': form[f"{index}-rank"],
                'discord_category': form[f"{index}-discord_category"],
                'discord_name': form[f"{index}-discord_name"],
            }
            await database.execute(query, values)

            if filename := form[f"{index}-image"]:
                # Save image (from image data blob) in the thumbs folder
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
