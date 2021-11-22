from functools import cmp_to_key

from quart import Blueprint, render_template

from auth import discord
from admin import admin
from inject import get_achievements
from webclient import bot_request
from util.db import database

# Create app blueprint
home = Blueprint('home', __name__)


@home.route('/home')
async def homepage():
    
    query = '''SELECT u1.*, (
            SELECT country FROM accounts acc
            WHERE u1.username = acc.username
                AND u1.discriminator = acc.discriminator
        ) country
        FROM user_levels u1
        INNER JOIN (
            SELECT username, discriminator,
                MAX(completion_time) AS max_time
            FROM user_levels
            WHERE TIMESTAMPDIFF(DAY, completion_time, NOW()) <= 1
            GROUP BY username
        ) u2
            ON u1.username = u2.username
                AND u1.discriminator = u2.discriminator
                AND u1.completion_time = u2.max_time
        ORDER BY completion_time DESC'''
    recent_completion = await database.fetch_all(query)
    
    return await render_template('home.htm',
        recent_completion=recent_completion)
