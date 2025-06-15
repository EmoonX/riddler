import {
  buildRiddle,
  currentRiddle,
  riddles,
  SERVER_HOST,
  updateState,
} from "./riddle.js";

/** Lock for `initExplorer` (should run once and non-concurrently). */
export let initNeeded = true;

/** Inits explorer by fetching user riddle data and pages. */
export async function initExplorer(callback) {
  initNeeded = false;
  await fetch(`${SERVER_HOST}/get-user-riddle-data`)
  .then(response => {
    if (response.status === 401) {
      throw `Unable to retrieve riddle data from server (not logged in).`;
    }
    return response.json();
  })
  .then(async riddlesData => {
    updateState(riddles, riddlesData.currentRiddle);
    await fetch(`${SERVER_HOST}/${currentRiddle}/levels/get-pages`)
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
    await fetch(`${SERVER_HOST}/get-user-pages`)
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
    initNeeded = true;
    console.log(exception);
  });
}

/** Sends message containing riddle data to popup.js. */
export function sendMessageToPopup(port) {
  port.postMessage({
    riddles: riddles,
    currentRiddle: currentRiddle,
  });
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

/** Generates `<figure>`jQuery element from given page tree node. */
function getFileFigure(node, token, offset) {
  let type;
  if (node.folder) {
    type = 'folder';
  } else if (token.indexOf('.') === -1) {
    type = 'html';
  } else if (node.unknownExtension) {
    type = 'unknown';
  } else {
    type = token.split('.').at(-1).toLowerCase();
  }
  const url = `images/icons/extensions/${type}.png`;
  const state = node.folder ? ' folder open' : '';
  const margin = `${0.4 * offset}em`;
  const img = `<img src="${url}">`;
  const fc = `<figcaption>${token}</figcaption>`;
  let fileCount = '';
  if (node.folder) {
    const riddle = riddles[currentRiddle];
    const level = riddle.levels[riddle.shownSet][riddle.shownLevel];
    const filesFound = node.filesFound;
    const filesTotal = level.beaten ? node.filesTotal : '??';
    fileCount =
      `<div class="file-count">(${filesFound} / ${filesTotal})</div>`;
  }
  // data-username="${object.username}"
  // data-password="${object.password}"
  return $(`
    <figure class="file${state}"
      title="${node.path}"
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
  $('#level var#current-level').text(levelName);
  $('#level #previous-set').toggleClass('disabled', !level.previousSet);
  $('#level #previous-level').toggleClass('disabled', !level.previousLevel);
  $('#level #next-level').toggleClass('disabled', !level.nextLevel);
  $('#level #next-set').toggleClass('disabled', !level.nextSet);
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
  if ($(this).attr('class').indexOf('folder') !== -1) {
    // Open or collapse folder, showing/hiding inner files
    const files = $(this).next('.folder-files');
    files.toggle();
  } else {
    // Open desired page in new tab
    const riddle = riddles[currentRiddle];
    const path = $(this).attr('title');
    const rootPath = (() => {
      try {
        const hosts = JSON.parse(riddle.rootPath);
        return hosts[0];
      } catch {
        return riddle.rootPath;
      }
    })();
    const url = new URL(`${rootPath}${path}`);
    url.username = $(this).attr('data-username') || '';
    url.password = $(this).attr('data-password') || '';
    window.open(url.toString(), '_blank');
  }
}
