import csv
from typing import Self

from quart import Blueprint, jsonify

from inject import get_riddles
from levels import get_pages
from util.levels import get_ordered_levels

export = Blueprint('players_export', __name__)


class Export:

    @classmethod
    async def build(cls) -> Self:
        self = cls()
        self.data = {}
        riddles = await get_riddles(unlisted=True)
        for riddle in riddles:
            pages = await get_pages(riddle['alias'], json=False)
            if pages:
                self.data[riddle['alias']] = pages
        
        return self

    def to_json(self) -> str:

        def _get_paths(token: dict) -> list[tuple[str, str]]:
            if not 'children' in token:
                return [(token['access_time'], token['path'])]
            paths = []
            for child in token['children'].values():
                paths += _get_paths(child)
            return paths

        for riddle in self.data.values():
            for level in riddle.values():
                paths = _get_paths(level['/'])
                pages = []
                for access_time, path in sorted(paths):
                    pages.append({
                        'path': path,
                        'access_time': access_time,
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

        return jsonify(self.data)


@export.route('/account/export-riddle-data')
async def export_user_riddle_data():
    return (await Export.build()).to_json()
