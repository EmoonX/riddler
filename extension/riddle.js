import { retrieveWithCache } from './cache.js';

/** Server host base URL. */
export const SERVER_HOST = 'https://riddler.app';

/** Player's riddle data. */
export let riddles = {};

/** Current riddle alias. */
export let currentRiddle;

/** Builds riddle object from riddle and levels JSON data. */
export async function buildRiddle(riddle, pages) {

  // Retrieve (possibly cached) riddle icon
  const iconUrlExternal = `${SERVER_HOST}/static/riddles/${riddle.alias}.png`;
  riddle.iconUrl = await retrieveWithCache('riddles', iconUrlExternal);

  riddle.levels = {};
  riddle.levelSets = {};
  riddle.pagesByPath = new Map();
  riddle.missingAuthPaths = new Map();
  riddle.shownSet = riddle.lastVisitedSet;
  riddle.shownLevel = riddle.lastVisitedLevel;

  // Build level/set navigation structure
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

/** Refresh riddle/pages data. */
export async function refreshRiddleData(alias, data) {
  currentRiddle = alias;
  if (!data.setName || !data.levelName) {
    // Not a valid level page; nothing more to be done
    return;
  }  
  buildRiddle(data.riddleData, data.pagesData);
}

/** Update currently visited riddle and level.  */
export async function updateCurrentRiddleAndLevel(riddle, path) {
  currentRiddle = riddle.alias;
  const page = riddle.pagesByPath.get(path);
  if (page?.['level_name']) {
    riddle.lastVisitedLevel = riddle.shownLevel = page['level_name'];
  }
}

function updatePathsIndex(riddle, pageNode) {
  riddle.pagesByPath.set(pageNode.path, pageNode);
  if (pageNode.folder) {
    for (const child of Object.values(pageNode.children)) {
      updatePathsIndex(riddle, child);
    }
  }
}

/** Parses riddle and path from URL, based on root host match. */
export function parseRiddleAndPath(url) {
  const parsedUrl = new URL(url.replace(/^view-source:/, ''));
  const [alias, rootPath] = parseRiddle(parsedUrl);
  if (! alias) {
    return [null, null];
  }

  const parsedRoot = new URL(rootPath);
  const urlTokens = parsedUrl.pathname.split('/').filter(Boolean);
  const rootTokens = parsedRoot.pathname.split('/').filter(Boolean);  
  const pathTokens = [];
  for (let i = 0; i < rootTokens.length; i++) {
    if (urlTokens[i] !== rootTokens[i]) {
      pathTokens.push('..');
    }
  }
  for (let i = 0; i < urlTokens.length; i++) {
    if (urlTokens[i] !== rootTokens[i]) {
      pathTokens.push(urlTokens[i]);
    }
  }
  const riddle = riddles[alias];
  const path = `/${pathTokens.join('/')}`;

  return [riddle, path];
}
chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
  if (msg.name === 'parseRiddleAndPath') {
    const [riddle, path] = parseRiddleAndPath(msg.url);
    sendResponse({
      riddle: riddle,
      path: path,
    });
  }
});

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

  let [alias, rootPath] = [null, null];
  for (const [_rootPath, _alias] of Object.entries(riddleHosts)) {
    const parsedRoot = new URL(_rootPath);
    const rootHostname = parsedRoot.hostname.replace(/^www\d*\./, '');
    if (_rootPath.indexOf('*') !== -1) {
      // Wildcard root path; ignore host pages outside given pattern
      const rootRegex = new RegExp(
        `${rootHostname}${parsedRoot.pathname}`
        .replaceAll('.', '\\.').replaceAll('*', '.*')
      );
      const url = `${hostname}${parsedUrl.pathname}`;
      if (rootRegex.test(url)) {
        [alias, rootPath] = [_alias, _rootPath.replace(/[/][*]$/, '')];
        break;
      }
    } else {
      // Simple root path
      if (rootHostname === hostname) {
        [alias, rootPath] = [_alias, _rootPath];
      }
    }
  }
  return [alias, rootPath];
}

/** Get simple root path URL, accounting for multiple and glob ones. */
export function getSimpleRootPath(riddle) {
  let rootPath = (() => {
    try {
      const rootPaths = JSON.parse(riddle.rootPath);
      return rootPaths[0];
    } catch {
      return riddle.rootPath;
    }
  })();
  rootPath = rootPath.replace(/[/][*]$/, '');

  return rootPath;
}

/** Find innermost path in set/map which contains the base one (if any). */
export function findContainingPath(basePath, paths) {
  const tokens = basePath.replace('/{2,}', '/').split('/');
  while (tokens.length !== 0) {
    const path = tokens.join('/') || '/';
    if (paths.has(path)) {
      return path;
    }
    tokens.pop();
  }
  return null;
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
