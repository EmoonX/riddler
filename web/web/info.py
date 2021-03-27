from quart import Blueprint, render_template

# Create app blueprint
info = Blueprint('info', __name__)


@info.route("/about")
async def about():
    return await render_template('about.htm')
