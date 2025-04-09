from collections import defaultdict
import csv
from datetime import datetime
import json
from types import SimpleNamespace

from quart import Blueprint, Response, request, send_file

from auth import discord, User
from credentials import get_all_unlocked_credentials
from inject import get_riddles
from levels import get_pages, absolute_paths
from util.db import database
from util.levels import get_ordered_levels

export = Blueprint('players_export', __name__)


@export.route('/account/export-data')
async def export_account_data():
    '''
    Retrieve player's account/riddle data and export it
    as a downloadable file in the given (suitable) format.
    '''
    format = request.args.get('format', '')
    user = await discord.get_user()
    export = _Export(user)
    await export.build_data()
    await export.record()
    return await export.download(format)


class _Export:
    '''Userdata export procedures.'''

    def __init__(self, user: User):
        '''Init raw `Export` object with empty data and counters.'''
        self.user = user
        self.export_time = datetime.utcnow()
        self.filename = (
            f"userdata-{self.user.name}-" +
            self.export_time.strftime("%Y%m%d%H%M%S")
        )
        self.data = defaultdict(lambda: defaultdict(dict))
        self.counters = SimpleNamespace(
            riddles=0, levels=0, pages=0, credentials=0
        )

    async def build_data(self):
        '''Build userdata dict from user-unlocked levels and pages.'''

        riddles = await get_riddles(unlisted=True)
        for alias in [riddle['alias'] for riddle in riddles]:
            # Build tree of page nodes
            page_tree = await get_pages(alias, as_json=False)
            if not page_tree:
                continue
            self.counters.riddles += 1

            # Populate riddle's level data
            for level_name, level_node in page_tree.items():
                level_data = self._build_level_data(alias, level_node)
                self.data[alias]['levels'][level_name] = level_data
                if level_data.get('answer'):
                   self.counters.levels += 1 
                self.counters.pages += level_data['pagesFound']

            # Populate riddle's credential data (if applicable)
            credentials = await get_all_unlocked_credentials(alias, self.user)
            if credentials:
                self.data[alias]['credentials'] = credentials
                self.counters.credentials += len(credentials)
               
    
    def _build_level_data(self, alias: str, level_node: dict) -> dict:
        '''Build level-specific userdata.'''

        def _add_items_when_available(*keys: str):
            '''Copy given available items from level node to data dict.'''
            for key in keys:
                if value := (level_node.get(key) or level_node['/'].get(key)):
                    nonlocal level_data
                    level_data |= {key: value}

        # Build list of pages from paths
        paths = absolute_paths(level_node['/'])
        pages = [
            {'path': path, 'accessTime': page_node['access_time']}
            for path, page_node in sorted(paths)
        ]

        # Populate dict with pages & other relevant level data
        level_data = {}
        _add_items_when_available('frontPage', 'answer')
        level_data |= {'pages': pages}
        _add_items_when_available(
            'pagesFound', 'pagesTotal', 'unlockTime', 'solveTime'
        )

        return level_data

    async def record(self):
        '''Record player's export time and riddle progress counters.'''
        values = {
            'username': self.user.name,
            'export_time': self.export_time,
            **{f"{k[:-1]}_count": v for k, v in vars(self.counters).items()},
        }
        query = f"""
            INSERT INTO _user_exports
            ({', '.join(values.keys())})
            VALUES ({', '.join(f":{k}" for k in values.keys())})
        """
        await database.execute(query, values)

    async def download(self, format: str) -> Response:
        '''Generate export file and return it as attachment in response.'''

        format = format.lower()
        self.filename += f".{format}"
        match format:
            case 'json':
                text = await self._to_json()
            case '':
                message = 'No export format provided.'
                return Response(message, status=422)
            case _:
                message = f"Invalid export format ({format})."
                return Response(message, status=422)

        # Mark file as attachment in header,
        # so response starts a client-sided file download
        response = Response(text)
        response.headers['Content-Disposition'] = \
            f"attachment; filename={self.filename}"
        
        return response

    async def _to_json(self) -> str:
        '''Simple JSON pretty-printed dump.'''
        return json.dumps(self.data, indent=2)
