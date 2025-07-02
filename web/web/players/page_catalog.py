from datetime import datetime
import re
from urllib.parse import urljoin

from quart import Blueprint, render_template, request
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth
from admin.archive import ArchivedPage
from credentials import get_path_credentials
from inject import get_riddle
from levels import absolute_paths, get_pages
from process import process_url
from util.db import database

page_catalog = Blueprint('page_catalog', __name__)


@page_catalog.get('/<alias>/page-catalog')
@requires_authorization
async def catalog(alias: str):
    '''Show page catalog.'''

    riddle = await get_riddle(alias)
    all_pages_by_level = await get_pages(
        alias,
        include_hidden=True,
        include_removed=True,
        index_by_levels=True,
        as_json=False,
    )

    async def _retrieve_page(path: str, page_data: dict) -> dict:

        # Build URL (with possibly embedded credentials)
        url = f"{riddle['root_path']}{path}"
        credentials = await get_path_credentials(alias, path)
        username = credentials['username']
        password = credentials['password']
        if username or password:
            url = url.replace('://', f"://{username or ''}:{password or ''}@")
        page_data |= {'url': url}
        return page_data

    # Start iterating at user-informed level (if any)
    levels = {}
    all_pages_by_path = {}
    for name, level in all_pages_by_level.items():
        pages = {}
        for path, page_data in absolute_paths(level['/']):
            page_data = await _retrieve_page(path, page_data)
            pages[path] = all_pages_by_path[path] = page_data

        # Show front page/image paths at the top
        level |= {'pages': {}}
        if front_page := pages.get(level.get('frontPage')):
            level['pages'] |= {
                level['frontPage']: front_page | {'flag': 'front-page'}
            }
            del pages[level['frontPage']]
        image_path = urljoin(level.get('frontPage'), level.get('image'))
        if image_page := pages.get(image_path):
            level['pages'] |= {
                image_path: image_page | {'flag': 'front-image'}
            }
            del pages[image_path]

        # Show remaining paths, with answer path at the bottom
        answer_page = pages.pop(level.get('answer'), None)
        level['pages'] |= pages
        if answer_page:
            level['pages'] |= {
                level['answer']: answer_page | {'flag': 'answer'}
            }

        levels[name] = level

    return await render_template(
        '/players/page-catalog.htm',
        riddle=riddle, levels=levels, all_pages_by_path=all_pages_by_path,
    )
