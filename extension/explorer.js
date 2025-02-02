/** Base server URL. */
const SERVER_URL = 'https://emoon.dev';

/** All the user riddle data. */
export let riddles = {};

/** Current riddle alias. */
let currentRiddle;

/** Inits explorer by fetching user riddle data and pages. */
export async function initExplorer(callback) {
  riddles.init = true;
  await fetch(`${SERVER_URL}/get-user-riddle-data`)
  .then(response => {
    if (response.status === 401) {
      throw `Unable to retrieve riddle data from server (not logged in).`;
    }
    return response.json();
  })
  .then(async riddlesData => {
    currentRiddle = riddlesData.currentRiddle;
    await fetch(`${SERVER_URL}/${currentRiddle}/levels/get-pages`)
      .then(response => response.json())
      .then(pagesData => {
        // Fetch current riddle before rest to ease popup wait time
        const riddle = riddlesData.riddles[currentRiddle];
        console.log(`[${currentRiddle}] Building riddle data…`);
        buildRiddle(riddle, pagesData);
        if (callback) {
          callback();
        }
      });
    await fetch(`${SERVER_URL}/get-user-pages`)
      .then(response => response.json())
      .then(allPagesData => {
        for (const [alias, riddle] of Object.entries(riddlesData.riddles)) {
          if (alias != currentRiddle) {
            console.log(`[${alias}] Building riddle data…`);
            buildRiddle(riddle, allPagesData[alias]);
          }
        }
      });
  })
  .catch(exception => {
    delete riddles.init;
    console.log(exception);
  });
}

/** Builds riddle dict from riddle and levels JSON data. */
async function buildRiddle(riddle, pages) {
  riddle.iconUrl = `${SERVER_URL}/static/riddles/${riddle.alias}.png`;
  riddle.shownSet = riddle.lastVisitedSet;
  riddle.shownLevel = riddle.lastVisitedLevel;
  riddle.pagesByPath = {};
  const setsArray = Object.keys(riddle.levels);
  let previousSetName = null;
  let previousLevelName = null;
  for (const [setIdx, setName] of Object.entries(setsArray)) {
    const levelSet = riddle.levels[setName];
    for (const [levelName, level] of Object.entries(levelSet)) {
      level.pages = pages[levelName];
      if (previousLevelName) {
        const previousLevel =
          riddle.levels[previousSetName][previousLevelName];
        level.previousLevel = previousLevelName;
        previousLevel.nextLevel = levelName;
        level.previousSet = previousSetName
      }
      if (setName !== setsArray.at(-1)) {
        level.nextSet = setsArray[Number(setIdx) + 1];
      } else if (levelName !== Object.keys(levelSet).at(-1)) {
        level.nextSet = setName;
      }
      previousSetName = setName;
      previousLevelName = levelName;
      updatePathsIndex(riddle, level.pages['/']);
    }        
  }
  riddles[riddle.alias] = riddle;
}

/** Updates current dict with possibly new riddle, level and/or page. */
export async function updateRiddleData(alias, setName, levelName) {
  currentRiddle = alias;
  const riddle = riddles[alias];
  if (!riddle.levels[setName][levelName]) {
    // Add new riddle and/or level
    await fetch(`${SERVER_URL}/get-user-riddle-data/${alias}`)
      .then(response => response.json())
      .then(async riddleData => {
        await fetch(`${SERVER_URL}/${alias}/levels/get-pages`)
          .then(response => response.json())
          .then(pagesData => {
            buildRiddle(riddleData, pagesData);
          });
      });
  } else {
    // Add (possibly) new page
    await fetch(`${SERVER_URL}/${alias}/levels/get-pages/${levelName}`)
      .then(response => response.json())
      .then(pagesData => {
        riddle.lastVisitedSet = riddle.shownSet = setName;
        riddle.lastVisitedLevel = riddle.shownLevel = levelName;
        for (const [levelName, pages] of Object.entries(pagesData)) {
          const level = riddle.levels[setName][levelName];
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

export function getRiddleAndPath(url) {
  const parsedUrl = new URL(url);
  const cleanUrl = `${parsedUrl.hostname}${parsedUrl.pathname}`;
  for (const riddle of Object.values(riddles)) {
    const parsedRoot = new URL(riddle.rootPath);
    const cleanRoot = `${parsedRoot.hostname}${parsedRoot.pathname}`;
    const index = cleanUrl.indexOf(cleanRoot);
    if (index !== -1) {
      let path = cleanUrl.replace(cleanRoot, '');
      if (path.at(-1) === '/' && path !== '/') {
        // Remove trailing slash from folder paths
        path = path.slice(0, -1);
      }
      return [riddle, path];
    }
  }
  return [null, null];
}

export function getPageNode(url) {
  let [riddle, path] = getRiddleAndPath(url);
  const pageNode = riddle.pagesByPath[path];
  return pageNode;
}

/** Sends message containing riddle data to popup.js. */
export function sendMessageToPopup(port) {
  port.postMessage({
    riddles: riddles,
    currentRiddle: currentRiddle,
  });
}

/** Updates module members in popup.js state. */
export function updateStateInPopup(_riddles, _currentRiddle) {
  riddles = _riddles;
  currentRiddle = _currentRiddle;
}

/** Recursively inserts files on parent with correct margin. */
export function insertFiles(parent, object, offset, prefix) {
  const basename = object.path.split('/').at(-1);
  if (object.folder) {
    const hasOnlyOneChild = Object.keys(object.children).length === 1;
    if (hasOnlyOneChild) {
      const child = Object.values(object.children)[0];
      if (child.folder) {
        prefix += `${basename}/`;
        insertFiles(parent, child, offset, prefix);
        return;
      }
    }
  }

  const riddle = riddles[currentRiddle];
  const level = riddle.levels[riddle.shownSet][riddle.shownLevel];
  const token = `${prefix}${basename}` || '/';
  const figure = getFileFigure(object, token, offset);
  if (object.path === level.frontPath) {
    // Highlight front page at first
    figure.addClass('active');
  }
  parent.append(figure);

  if (object.folder) {
    const div = $('<div class="folder-files"></div>');
    div.appendTo(parent);
    if (level.frontPath && level.frontPath.indexOf(object.path) !== 0) {
      // Leave only level's front page folder(s) initially open
      div.toggle();
    }
    for (const child of Object.values(object.children)) {
      insertFiles(div, child, offset + 1, '');
    }
  }
}

/** Generates `<figure>`jQuery element from given file object. */
function getFileFigure(object, token, offset) {
  let type = 'folder';
  if (! object.folder) {
    const i = token.lastIndexOf('.');
    type = token.substr(i+1);
  }
  const url = `images/icons/extensions/${type}.png`;
  const state = (type == 'folder') ? ' open' : '';
  const margin = `${0.4 * offset}em`;
  const img = `<img src="${url}">`;
  const fc = `<figcaption>${token}</figcaption>`;
  let fileCount = '';
  if (object.folder) {
    const riddle = riddles[currentRiddle];
    const level = riddle.levels[riddle.shownSet][riddle.shownLevel];
    const filesFound = object.filesFound;
    const filesTotal = level.beaten ? object.filesTotal : '??';
    fileCount =
      `<div class="file-count">(${filesFound} / ${filesTotal})</div>`;
  }
  // data-username="${object.username}"
  // data-password="${object.password}"
  return $(`
    <figure class="file${state}"
      title="${object.path}"
      style="margin-left: ${margin}"
    >
      ${img}${fc}${fileCount}
    </figure>
  `);
}

/** 
 * Changes displayed level set to previous or next one,
 * upon double arrow click.
 */
export function changeLevelSet() {
  const riddle = riddles[currentRiddle];
  let level = riddle.levels[riddle.shownSet][riddle.shownLevel];
  const setName =
    $(this).is('#previous-set') ?
    level.previousSet :
    level.nextSet;
  const levelName =
    Object.keys(riddle.levels[setName]).at(
      riddle.shownSet !== Object.keys(riddle.levels).at(-1) ?
      0 :
      ($(this).is('#previous-set') ? 0 : -1)
    );
  level = riddle.levels[setName][levelName];
  console.log(levelName);
  console.log(level);
  riddle.shownSet = setName;
  riddle.shownLevel = levelName;
  updatePopupNavigation(riddle, level, setName, levelName);
}

/** Changes displayed level to previous or next one, upon arrow click. */
export function changeLevel() {
  const riddle = riddles[currentRiddle];
  let levelSet = riddle.levels[riddle.shownSet];
  let level = levelSet[riddle.shownLevel];
  let [setName, levelName] = [riddle.shownSet, null];
  if ($(this).is('#previous-level')) {
    const firstInSet = Object.keys(levelSet).at(0);
    if (riddle.shownLevel === firstInSet) {
      setName = level.previousSet;
    }
    levelName = level.previousLevel
  } else {
    const lastInSet = Object.keys(levelSet).at(-1);
    if (riddle.shownLevel === lastInSet) {
      setName = level.nextSet;
    }
    levelName = level.nextLevel;
  }
  level = riddle.levels[setName][levelName];
  updatePopupNavigation(riddle, level, setName, levelName);
}

function updatePopupNavigation(riddle, level, setName, levelName) {
  riddle.shownSet = setName;
  riddle.shownLevel = levelName;
  $('#level > var#current-level').text(levelName);
  $('#level > #previous-set').toggleClass('disabled', !level.previousSet);
  $('#level > #previous-level').toggleClass('disabled', !level.previousLevel);
  $('#level > #next-level').toggleClass('disabled', !level.nextLevel);
  $('#level > #next-set').toggleClass('disabled', !level.nextSet);
  $('.page-explorer').empty();
  insertFiles($('.page-explorer'), level.pages['/'], 0, '');
}

/** Selects file and unselect the other ones, as in a file explorer. */
export function clickFile() {
  const files = $(this).parents('.page-explorer').find('figure.file');
  files.each(function () {
    $(this).removeClass('active');
  });
  $(this).addClass('active');
}

/** Handles double clicking files or folders. */
export async function doubleClickFile() {
  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1 && j != page.length - 1) {
    // Open desired page in new tab
    const riddle = riddles[currentRiddle];
    const path = $(this).attr('title');
    let url = `${riddle.rootPath}${path}`;
    if ($(this).attr('data-username')) {
      let username = $(this).attr('data-username');
      let password = $(this).attr('data-password');
      url = url.replace('://', `://${username}:${password}@`);
    }
    window.open(url, '_blank');
  } else {
    // Open or collapse folder, showing/hiding inner files
    const files = $(this).next('.folder-files');
    files.toggle();
  }
}

/** Clears user riddle data and puts extension in a logged out state. */
export function clearRiddleData() {
  for (const prop of Object.getOwnPropertyNames(riddles)) {
    delete riddles[prop];
  }
}
