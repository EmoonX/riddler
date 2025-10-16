import posixpath
from urllib.parse import urljoin

from quart import Blueprint, render_template
from quartcord import requires_authorization

from auth import discord
from credentials import get_path_credentials, has_unlocked_path_credentials
from inject import get_riddle
from levels import absolute_paths, get_pages, listify

page_catalog = Blueprint('page_catalog', __name__)


@page_catalog.get('/<alias>/page-catalog')
@requires_authorization
async def catalog(alias: str):
    '''Show page catalog for logged in player.'''

    riddle = await get_riddle(alias)
    user = await discord.get_user()
    all_pages_by_level = await get_pages(
        alias,
        include_hidden=True,
        include_removed=True,
        index_by_levels=True,
        as_json=False,
    )

    async def _retrieve_page(path: str, page_data: dict) -> dict:
        '''Build URL (possibly w/ credentials) and return page data with it.'''

        url = f"{riddle['root_path']}{path}"
        credentials = await get_path_credentials(alias, path)
        if await has_unlocked_path_credentials(alias, user, credentials['path']):
            username = credentials['username']
            password = credentials['password']
            if username or password:
                auth = f"{username or ''}:{password or ''}"
                url = url.replace('://', f"://{auth}@")

        return page_data | {'url': url}

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
        level['frontPages'] = listify(level.get('frontPage'))
        for path in level['frontPages']:
            if front_page := pages.get(path):
                level['pages'] |= {path: front_page | {'flag': 'front-page'}}
                del pages[path]
        if level['frontPages']:
            image_path = posixpath.join(
                # Use `posixpath` to avoid `urljoin`'s '..' resolution
                f"{level['frontPages'][0].rpartition('/')[0]}/",
                level.get('image') or '',
            )
            if image_page := pages.get(image_path):
                level['pages'] |= {
                    image_path: image_page | {'flag': 'front-image'}
                }
                del pages[image_path]

        # Show remaining paths, with answer(s) at the bottom
        level['answers'] = listify(level.get('answer'))
        answer_pages = []
        for path in level['answers']:
            if page := pages.pop(path, None):
                answer_pages.append(page)
        level['pages'] |= pages            
        level['pages'] |= {
            page['path']: page | {'flag': 'answer'}
            for page in answer_pages
        }

        levels[name] = level

    return await render_template(
        '/players/page-catalog.htm',
        riddle=riddle, levels=levels, all_pages_by_path=all_pages_by_path,
    )
