import {
  buildRiddle,
  currentRiddle,
  riddles,
  SERVER_HOST,
  updateState,
} from './riddle.js';

import { createTab } from './tabs.js';

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
  const level = riddle.levels[riddle.shownLevel];
  const token = `${prefix}${basename}` || '/';
  const figure = getFileFigure(object, token, offset);
  if (object.path === level.frontPath && !object.folder) {
    // Highlight front page at first
    figure.addClass('active');
  }

  parent.append(figure);
  if (object.folder) {
    const div = $('<div class="folder-files"></div>');
    div.appendTo(parent);
    if (level.frontPath && !level.frontPath.startsWith(object.path)) {
      // Leave only level's front page folder(s) initially open
      div.toggle();
    }
    for (const child of Object.values(object.children)
      .sort((a, b) => {
        // Sort folders first; ensure lexicographical ordering
        if (a.folder && b.folder) {
          return a.path.localeCompare(b.path);
        }
        return Number(b.folder || false) - Number(a.folder || false);
      })
    ) {
      insertFiles(div, child, offset + 1, '');
      if (child.children && !child.folder) {
        // Handle hybrid page/folder navigation
        for (const grandchild of Object.values(child.children)) {
          if (grandchild.special === 1) {
            const basename = child.path.split('/').at(-1);
            insertFiles(div, grandchild, offset + 1, `${basename}/`);
          } else {
            const folder = { ...child, folder: true };
            insertFiles(div, folder, offset + 1, '');
            break;
          }
        }
      }
    }
  }
}

/** Generates `<figure>`jQuery element from given page tree node. */
function getFileFigure(node, token, offset) {
  let type;
  if (node.folder) {
    type = 'folder';
  } else if (! token.includes('.')) {
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
    const level = riddle.levels[riddle.shownLevel];
    const filesFound = node.filesFound;
    const filesTotal = level.solved ? node.filesTotal : '??';
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
  let levelSet = riddle.levelSets[riddle.shownSet];
  let level = riddle.levels[riddle.shownLevel];
  if ($(this).is('#previous-set')) {
    if (levelSet.previous && level.name === levelSet.firstLevel) {
      levelSet = riddle.levelSets[levelSet.previous];
    }
    level = riddle.levels[levelSet.firstLevel];
  } else {
    if (levelSet.next) {
      levelSet = riddle.levelSets[levelSet.next];
      level = riddle.levels[levelSet.firstLevel];
    } else {
      level = riddle.levels[levelSet.lastLevel];
    }
  }
  updatePopupNavigation(riddle, level);
}

/** Changes displayed level to previous or next one, upon arrow click. */
export function changeLevel() {
  const riddle = riddles[currentRiddle];
  let level = riddle.levels[riddle.shownLevel];
  if ($(this).is('#previous-level')) {
    level = riddle.levels[level.previous];
  } else {
    level = riddle.levels[level.next];
  }
  updatePopupNavigation(riddle, level);
}

/** Updates level/set being shown and navigation buttons. */
function updatePopupNavigation(riddle, level) {
  const levelSet = riddle.levelSets[level.setName];
  riddle.shownSet = levelSet.name;
  riddle.shownLevel = level.name;

  $('#level var#level-name').text(level.name);
  $('#level #previous-set').toggleClass('disabled', !level.previous);
  $('#level #previous-level').toggleClass('disabled', !level.previous);
  $('#level #next-level').toggleClass('disabled', !level.next);
  $('#level #next-set').toggleClass('disabled', !level.next);

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
    })().replace(/[/][*]$/, '');;
    const parsedUrl = new URL(`${rootPath}${path}`);
    parsedUrl.username = $(this).attr('data-username') || '';
    parsedUrl.password = $(this).attr('data-password') || '';
    createTab(parsedUrl.toString(), { active: true });
  }
}
