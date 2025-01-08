#!/usr/bin/python3

'''Web-crawler script. Picks up front level links
from a `filelist.txt` and searches given site pages
for images' URLs, downloading them in the process.'''

import os
import shutil
import sys

from bs4 import BeautifulSoup
import requests
from requests.auth import HTTPBasicAuth


def visit_and_process_images(url: str) -> str:
    '''Visit webpage and search for <img> tags,
    saving it not downloaded yet and returning found URL.'''

    if url[-4:] != '.htm' and url[-5:] != '.html':
        return

    # Crawl page for <img> tag and add it to list
    auth = HTTPBasicAuth('un', 'pw')
    resp = requests.get(url, auth=auth)
    if resp.status_code != 200:
        return
    html = resp.text
    soup = BeautifulSoup(html, features="lxml")
    if not soup.find('img'):
        return
    src = soup.img['src']
    print(f"({level}) Found image {src}...", end='')
    image_url = url.rsplit('/', maxsplit=1)[0] + '/' + src

    # Download image from given URL and save it in folder
    resp = requests.get(image_url, stream=True)
    path = 'images/' + src
    if not os.path.exists(path):
        with open(path, 'wb') as image_file:
            shutil.copyfileobj(resp.raw, image_file)
            print(' saved.')
    else:
        print()

    return image_url


if len(sys.argv) != 2:
    print('ERROR: missing filename', file=sys.stderr)
    sys.exit(1)

# Get file data splitted between levels
filename = sys.argv[1]
with open(filename, encoding='utf-8') as file:
    data = file.read().replace('\r', '').split('#')[1:]

# Build dict of level URLs
levels = {}
level_fronts = {}
for text in data:
    level, urls = text.strip().split('\n', maxsplit=1)
    level = level.strip()
    urls = urls.split()
    level_fronts[level] = urls[0]
    levels[level] = set(urls)

if not os.path.exists('images'):
    os.mkdir('images')
    print('Created dir "images".\n')

for level, urls in levels.items():
    to_add = []
    for url in urls:
        image_url = visit_and_process_images(url)
        if image_url:
            to_add.append(image_url)
    urls.update(to_add)

# Updates filelist with image links
data = []
for level, urls in levels.items():
    name = '#' + level
    front = level_fronts[level]
    urls.remove(front)
    content = [name, front] + sorted(urls)
    text = '\n'.join(content)
    data.append(text)

# Save output to new .txt
with open('filelist.txt', 'w', encoding='utf-8') as output:
    text = '\n\n'.join(data)
    output.write(text)
