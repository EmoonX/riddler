/** Server host base URL. */
export const SERVER_HOST = 'https://riddler.app';

/** Player's riddle data. */
export let riddles = {};

/** Current riddle alias. */
export let currentRiddle;

/** Builds riddle object from riddle and levels JSON data. */
export async function buildRiddle(riddle, pages) {

  const iconUrlExternal = `${SERVER_HOST}/static/riddles/${riddle.alias}.png`;
  fetch(iconUrlExternal, {cache : 'force-cache'})
    .then(response => response.blob({type: 'image/png'}))
    .then(async blob => {
      // Store/retrieve cached image blob to avoid annoying icon load times
      riddle.iconUrl = await new Promise(resolve => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
      });
    });

  riddle.levels = {};
  riddle.levelSets = {};
  riddle.pagesByPath = {};
  riddle.shownSet = riddle.lastVisitedSet;
  riddle.shownLevel = riddle.lastVisitedLevel;
  
  let currentSet;
  for (const [i, level] of Object.entries(riddle.orderedLevels)) {
    if (i > 0) {
      const previousLevel = riddle.orderedLevels[i-1];
      level.previous = previousLevel.name;
      previousLevel.next = level.name;
    }
    if (level.setName !== currentSet?.name) {
      if (currentSet) {
        currentSet.lastLevel = level.previous;
        currentSet.next = level.setName;
      }
      const levelSet = {
        name: level.setName,
        firstLevel: level.name,
      };
      if (level.previous) {
        levelSet.previous = currentSet.name;
      }
      riddle.levelSets[level.setName] = currentSet = levelSet;
    }
    if (i == riddle.orderedLevels.length - 1) {
      currentSet.lastLevel = level.name;
    }

    level.pages = pages[level.name];
    if (level.pages) {
      updatePathsIndex(riddle, level.pages['/']);
    }

    riddle.levels[level.name] = level;
  }

  riddles[riddle.alias] = riddle;
}

/** Updates current object with possibly new riddle, level and/or page. */
export async function updateRiddleData(alias, setName, levelName) {
  currentRiddle = alias;
  if (!setName || !levelName) {
    // Not a valid level page; nothing more to be done
    return;
  }
  const riddle = riddles[alias];
  const levelSet = riddle.levels[setName];
  if (!levelSet || !levelSet[levelName]) {
    // Add new riddle and/or level
    await fetch(`${SERVER_HOST}/get-user-riddle-data/${alias}`)
      .then(response => response.json())
      .then(async riddleData => {
        await fetch(`${SERVER_HOST}/${alias}/levels/get-pages`)
          .then(response => response.json())
          .then(pagesData => {
            buildRiddle(riddleData, pagesData);
          });
      });
  } else {
    // Add (possibly) new page
    await fetch(`${SERVER_HOST}/${alias}/levels/get-pages/${levelName}`)
      .then(response => response.json())
      .then(pagesData => {
        riddle.lastVisitedSet = riddle.shownSet = setName;
        riddle.lastVisitedLevel = riddle.shownLevel = levelName;
        for (const [levelName, pages] of Object.entries(pagesData)) {
          const level = riddle.levels[levelName];
          level.pages = pages;
          updatePathsIndex(riddle, level.pages['/']);
        }
      });
  }
}

function updatePathsIndex(riddle, pageNode) {
  riddle.pagesByPath[pageNode.path] = pageNode;
  if (pageNode.folder) {
    for (const child of Object.values(pageNode['children'])) {
      updatePathsIndex(riddle, child);
    }
  }
}

/** Parses riddle and path from URL, based on root host match. */
export function parseRiddleAndPath(url) {
  const parsedUrl = new URL(url);
  const [alias, rootPath] = parseRiddle(parsedUrl);
  if (! alias) {
    return [null, null];
  }

  const parsedRoot = new URL(rootPath);
  const urlTokens = parsedUrl.pathname.split('/');
  const rootTokens = parsedRoot.pathname.split('/');
  let path = '';
  for (let i = 0; i < rootTokens.length; i++) {
    if (urlTokens[i] !== rootTokens[i]) {
      path += '/..';
    }
  }
  for (let i = 0; i < urlTokens.length; i++) {
    if (urlTokens[i] !== rootTokens[i]) {
      path += `/${urlTokens[i]}`;
    }
  }      
  if (path.at(-1) === '/' && path !== '/') {
    // Remove trailing slash from folder paths
    path = path.slice(0, -1);
  }
  return [riddles[alias], path];
}

function parseRiddle(parsedUrl) {
  const hostname = parsedUrl.hostname.replace(/^www\d*\./, '');

  // Build flat list of hosts
  const riddleHosts = {};
  for (const [alias, riddle] of Object.entries(riddles)) {
    try {
      const rootPaths = JSON.parse(riddle.rootPath);
      for (const rootPath of rootPaths) {
        riddleHosts[rootPath] = alias;
      }
    } catch {
      riddleHosts[riddle.rootPath] = alias;
    }
  }
  
  for (const [rootPath, alias] of Object.entries(riddleHosts)) {
    const parsedRoot = new URL(rootPath);
    const rootHostname = parsedRoot.hostname.replace(/^www\d*\./, '');
    if (rootHostname === hostname) {
      return [alias, rootPath];
    }
  }
  return [null, null];
}

/** Gets page tree node from URL. */
export function getPageNode(url) {
  const [riddle, path] = parseRiddleAndPath(url);
  return riddle.pagesByPath[path];
}

/** Check whether the riddle path deals with real personal auth. */
export function isPathSensitive(riddle, path) {
  // (no, pr0ners, I am NOT interested in hoarding your personal user data)
  return riddle.alias === 'notpron' && path.indexOf('/jerk2') === 0;
}

/** Sends message containing riddle data to popup.js. */
export function sendMessageToPopup(port) {
  port.postMessage({
    riddles: riddles,
    currentRiddle: currentRiddle,
  });
}

/** Updates module members' state. */
export function updateState(_riddles, _currentRiddle) {
  riddles = _riddles;
  currentRiddle = _currentRiddle;
}

/** Clears user riddle data and puts extension in a logged out state. */
export function clearRiddleData() {
  for (const prop of Object.getOwnPropertyNames(riddles)) {
    delete riddles[prop];
  }
  initNeeded = true;
}
