from quart import Blueprint, request, render_template
from quart_discord import requires_authorization

from auth import discord
from ipc import web_ipc
from util.db import database

# Create app blueprint
admin = Blueprint('admin', __name__)


@admin.route('/admin/<alias>/', methods=['GET', 'POST'])
@requires_authorization
async def config(alias: str):
    '''Riddle administration configuration.'''
    
    # Get riddle/guild full name from database
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    if not result:
        # Invalid alias...
        return 'Riddle not found!', 404
    full_name = result['full_name']
    
    # Check if user is indeed an admin of given guild
    guilds = await discord.fetch_guilds()
    for guild in guilds:
        if guild.name == full_name:
            if not guild.permissions.administrator:
                return 'Unauthorized', 401
            break
    
    # Fetch guild levels info from database
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle AND is_secret IS FALSE'
    values = {'riddle': alias}
    levels = await database.fetch_all(query, values)
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle AND is_secret IS TRUE'
    secret_levels = await database.fetch_all(query, values)
    
    def r(msg):
        '''Render page and get filename cookies locally.'''
        return render_template('admin/admin.htm', 
                alias=alias, levels=levels, msg=msg)

    # Render page normally on GET
    if request.method == 'GET':
        return await r('')

    # Insert new level info on database
    form = await request.form
    query = 'INSERT INTO levels ' \
            '(riddle, level_set, `index`, `name`, path, image, answer, ' \
                '`rank`, discord_category, discord_name) VALUES ' \
            '(:riddle, :set, :index, :name, :path, :image, :answer, ' \
                ':rank, :discord_category, :discord_name)'
    print(query)
    index = len(levels) + 1
    values = {'riddle': alias, 'set': 'Normal Levels',
            'index': index, 'name': form['%d-name' % index],
            'path': form['%d-path' % index],
            'image': form['%d-image' % index],
            'answer': form['%d-answer' % index],
            'rank': form['%d-rank' % index],
            'discord_category': 'Normal Levels',
            'discord_name': form['%d-discord_name' % index]}
    await database.execute(query, values)
    # query = 'INSERT IGNORE INTO secret_levels VALUES ' \
    #         '(:guild, :category, :level_name, :path, ' \
    #             ':previous_level, :answer_path)'
    # secret_levels_values = {'guild': alias, 'category': 'Secret Levels',
    #         'level_name': form['new_secret_id'], 'path': form['new_secret_path'],
    #         'previous_level': form['new_secret_prev'],
    #         'answer_path': form['new_secret_answer']}
    # if '' not in secret_levels_values.values():
    #     await database.execute(query, secret_levels_values)

    # Update Discord guild channels and roles with new levels info.
    # This is done by sending an request to the bot's IPC server.
    values['is_secret'] = 0
    await web_ipc.request('build', guild_name=full_name, levels=[values])

    return await r('Guild info updated successfully!')

