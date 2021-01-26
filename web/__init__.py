import os
import sys

from flask import Flask

# Avoid "no module named" errors because of __init__.py
sys.path.append('.')

from util import mysql_init

# Flask app object
app = Flask(__name__)

# Create MySQL object
mysql_init(app)

from login import login
from guild import guild

for blueprint in (login, guild):
    # Register app blueprint to allow other modules
    app.register_blueprint(blueprint)

# "Unique" and "secret" secret key
app.secret_key = 'RASPUTIN'

# Database connection details
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT'))
app.config['MYSQL_USER'] = 'emoon'
app.config['MYSQL_PASSWORD'] = 'emoon'
app.config['MYSQL_DB'] = 'guilds'

# Run Flask application
if __name__ == '__main__':
    app.run(host='0.0.0.0')
