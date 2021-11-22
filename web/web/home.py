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
    return await render_template('home.htm')
