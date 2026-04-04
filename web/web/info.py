from quart import abort, Blueprint, redirect, render_template
from jinja2.exceptions import TemplateNotFound

from inject import get_riddles

# Create app blueprint
info = Blueprint('info', __name__)


@info.get('/<page>')
async def info_page(page: str):
    '''Show a front/info page by rendering its immediate template.
    Throw 404 if such template doesn't exist.'''

    path = f"info/{page}.htm" if page != 'riddles' else f"{page}.htm"
    try:
        return await render_template(path)
    except TemplateNotFound:
        # Possibly a riddle front page
        riddles = await get_riddles(unlisted=True)
        aliases = [riddle['alias'] for riddle in riddles]
        if page in aliases:
            return redirect(f"/{page}/players")

        abort(404)


@info.get('/old/<page>')
@info.get('/old/<page>.html')
async def old_page(page: str):
    ext = page.partition('.')[-1]
    if ext and ext != 'html':
        abort(404)
    return await render_template(f"/old/{page}.htm")
