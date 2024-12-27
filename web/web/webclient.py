import json

import aiohttp


async def bot_request(path: str, **kwargs) -> str:
    '''Send HTTP to webserver running on Discord bot.'''

    # Correctly prepare values to conforming JSON format
    url = 'http://localhost:4757/' + path
    for param, value in kwargs.items():
        if isinstance(value, (dict, list, set, tuple)):
            if isinstance(value, set):
                value = list(value)
            kwargs[param] = json.dumps(value)
        elif isinstance(value, bool) or value is None:
            kwargs[param] = int(bool(value))

    # Send request and return response
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=kwargs) as resp:
            text = await resp.text()
            return text
