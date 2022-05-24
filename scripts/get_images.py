'''Web-crawler script. Picks up front level links
from a `filelist.txt` and searches given site pages
for images' URLs, downloading them in the process.'''

import os
import shutil
import sys

from bs4 import BeautifulSoup
import requests

if len(sys.argv) != 2:
    print('ERROR: missing filename', file=sys.stderr)
    sys.exit(1)

# Get file data splitted between levels
filename = sys.argv[1]
with open(filename, encoding='utf-8') as file:
    data = file.read().replace('\r', '').split('#')[1:]

# Build dict of front URLs
levels = {}
for text in data:
    level, url = text.split('\n')[0:2]
    level = level.strip()
    url = url.strip()
    levels[level] = url

if not os.path.exists('images'):
    os.mkdir('images')
    print('Created dir "images"')

images = {}
for level, url in levels.items():
    # Crawl page for <img> tag
    resp = requests.get(url)
    if resp.status_code != 200:
        continue
    html = resp.text
    soup = BeautifulSoup(html, features="lxml")
    if not soup.find('img'):
        continue
    src = soup.img['src']
    image_url = url.rsplit('/', maxsplit=1)[0] + '/' + src
    images[level] = image_url

    # Download image from given URL and save it in folder
    resp = requests.get(image_url, stream=True)
    path = 'images/' + src
    if not os.path.exists(path):
        with open(path, 'wb') as image_file:
            shutil.copyfileobj(resp.raw, image_file)
            print(f"({level}) Image {src} saved")

# Updates filelist with image links
for i, text in enumerate(data):
    rows = text.strip().split('\n')
    level = rows[0].strip()
    rows[0] = '#' + rows[0]
    if level in images:
        image_url = images[level]
        rows.insert(2, image_url)
    data[i] = '\n'.join(rows)

# Save output to new .txt
with open('filelist.txt', 'w', encoding='utf-8') as output:
    text = '\n\n'.join(data)
    print(text)
    output.write(text)
