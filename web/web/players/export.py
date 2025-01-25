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

    async def build_pages(self):
        riddles = await get_riddles(unlisted=True)
        for riddle in riddles:
            pages = await get_pages(riddle['alias'], as_json=False)
            if not pages:
                continue
            self.data[riddle['alias']] = pages
            for level in pages.values():
                pages = []
                paths = absolute_paths(level['/'])
                for path, page_node in sorted(paths):
                    pages.append({
                        'path': path,
                        'access_time': page_node['access_time'],
                    })

                level |= {'pages': pages}
                if 'front_page' in level:
                    level |= {'front_page': level['front_page']}
                    del level['image']
                    if 'answer' in level:
                        level |= {'answer': level['answer']}
                                    
                level |= {'pages_found': level['/']['filesFound']}
                if {'front_page', 'answer'}.issubset(level.keys()):
                    level |= {'pages_total': level['/']['filesTotal']}

                del level['/']

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
    await export.build_pages()
    return await export.download(format)
