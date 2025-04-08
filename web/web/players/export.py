from collections import defaultdict
import csv
from datetime import datetime
import json
from types import SimpleNamespace
from typing import Self

from quart import Blueprint, Response, request, send_file

from auth import discord, User
from inject import get_riddles
from levels import get_pages, absolute_paths
from util.db import database
from util.levels import get_ordered_levels

export = Blueprint('players_export', __name__)


class Export:
    '''Userdata export procedures.'''

    def __init__(self, user: User):
        '''Init raw `Export` object with empty data and counters.'''
        self.user = user
        self.export_time = datetime.utcnow()
        self.filename = (
            f"userdata-{self.user.name}-" +
            self.export_time.strftime("%Y%m%d%H%M%S")
        )
        self.data = defaultdict(dict)
        self.counters = SimpleNamespace(riddles=0, levels=0, pages=0)

    async def build_data(self):
        '''Build userdata dict from user-unlocked levels and pages.'''
        riddles = await get_riddles(unlisted=True)
        for riddle in riddles:
            alias = riddle['alias']
            page_tree = await get_pages(alias, as_json=False)
            if not page_tree:
                continue
            self.counters.riddles += 1
            for level_name, level_node in page_tree.items():
                level_data = self._build_level_data(alias, level_node)
                self.data[alias][level_name] = level_data
                if level_data.get('answer'):
                   self.counters.levels += 1 
                self.counters.pages += len(level_data)
    
    def _build_level_data(self, alias: str, level_node: dict) -> dict:
        '''Build level-specific userdata.'''

        paths = absolute_paths(level_node['/'])
        pages = [
            {'path': path, 'access_time': page_node['access_time']}
            for path, page_node in sorted(paths)
        ]
        level_data = {'pages': pages}
        if front_page := level_node.get('frontPage'):
            level_data |= {'frontPage': front_page}
            if answer := level_node.get('answer'):
                level_data |= {'answer': answer}
        level_data |= {'filesFound': level_node['/']['filesFound']}
        if {'frontPage', 'answer'}.issubset(level_data.keys()):
            level_data |= {'filesTotal': level_node['/']['filesTotal']}

        return level_data

    async def record(self):
        '''Record user's export time and riddle progress counters.'''
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

        response = Response(text)
        response.headers['Content-Disposition'] = \
            f"attachment; filename={self.filename}"
        
        return response

    async def _to_json(self) -> str:
        '''Simple JSON pretty-printed dump.'''
        return json.dumps(self.data, indent=2)
    

@export.route('/account/export-userdata')
async def export_userdata():
    '''
    Retrieve user's current riddle data and export it
    as a downloadable file in the given (suitable) format.
    '''
    format = request.args.get('format', '')
    user = await discord.get_user()
    export = Export(user)
    await export.build_data()
    await export.record()
    return await export.download(format)
