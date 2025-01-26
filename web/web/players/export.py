import csv
from datetime import datetime
import json
from typing import Self

from quart import Blueprint, Response, request, send_file

from auth import discord, User
from inject import get_riddles
from levels import get_pages, absolute_paths
from util.levels import get_ordered_levels

export = Blueprint('players_export', __name__)


class Export:

    def __init__(self, user: User):
        tnow = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        self.filename = f"userdata-{user.name}-{tnow}"
        self.data = {}

    async def build_data(self):
        riddles = await get_riddles(unlisted=True)
        for riddle in riddles:
            page_tree = await get_pages(riddle['alias'], as_json=False)
            if not page_tree:
                continue
            self.data[riddle['alias']] = {}
            for level_name, level_data in page_tree.items():
                pages = []
                paths = absolute_paths(level_data['/'])
                for path, page_node in sorted(paths):
                    pages.append({
                        'path': path,
                        'access_time': page_node['access_time'],
                    })

                level = {'pages': pages}
                if 'frontPage' in level_data:
                    level |= {'front_page': level_data['frontPage']}
                    if 'answer' in level_data:
                        level |= {'answer': level_data['answer']}
                                    
                level |= {'pages_found': level_data['/']['filesFound']}
                if {'front_page', 'answer'}.issubset(level.keys()):
                    level |= {'pages_total': level_data['/']['filesTotal']}

                self.data[riddle['alias']][level_name] = level

    async def download(self, format: str) -> Response:
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
        return json.dumps(self.data, indent=2)
    

@export.route('/account/export-riddle-data')
async def export_user_riddle_data():
    format = request.args.get('format', '')
    user = await discord.get_user()
    export = Export(user)
    await export.build_data()
    return await export.download(format)
