/** Base server URL. */
const SERVER_URL = 'https://emoon.dev';

/** All player riddle data. */
let riddles = {};

/** Current riddle alias. */
let currentRiddle;

/** Builds riddle dict from riddle and levels JSON data. */
async function buildRiddle(riddle) {
  const pagesUrl = `${SERVER_URL}/${riddle.alias}/levels/get-pages`;
  await fetch(pagesUrl)
    .then(response => response.json())
    .then(pagesData => {
      riddle.iconUrl = `${SERVER_URL}/static/riddles/${riddle.alias}.png`;
      riddle.shownSet = riddle.lastVisitedSet;
      riddle.shownLevel = riddle.lastVisitedLevel;
      for (const [setName, levelSet] of Object.entries(riddle.levels)) {
        let previousName = null;
        for (const [levelName, level] of Object.entries(levelSet)) {
          level.pages = pagesData[levelName];
          if (previousName) {
            riddle.levels[setName][previousName].next = levelName;
          }
          level.previous = previousName;
          previousName = levelName;
        }
      }
    });
  riddles[riddle.alias] = riddle;
}

/** Updates current dict with possibly new riddle, level and/or page. */
export async function updateRiddleData(alias, setName, levelName) {
  currentRiddle = alias;
  if (!riddles[alias].levels[setName][levelName]) {
    // Add new riddle and/or level
    const DATA_URL = `${SERVER_URL}/get-user-riddle-data/${alias}`;
    await fetch(DATA_URL)
      .then(response => response.json())
      .then(data => {
        buildRiddle(data);
      });
  } else {
    // Add (possibly) new page
    const pagesUrl = `${SERVER_URL}/${alias}/levels/get-pages/${levelName}`;
    await fetch(pagesUrl)
      .then(response => response.json())
      .then(pagesData => {
        const riddle = riddles[alias];
        riddle.lastVisitedSet = riddle.shownSet = setName;
        riddle.lastVisitedLevel = riddle.shownLevel = levelName;
        for (const [levelName, pages] of Object.entries(pagesData)) {
          const level = riddle.levels[setName][levelName];
          level.pages = pages;
        }
      });
  }
}

/** Send message containing module data to popup.js. */
export function sendMessageToPopup() {
  chrome.runtime.onConnect.addListener(port => {
    console.log('Connected to popup.js...');
    port.postMessage({
      riddles: riddles,
      currentRiddle: currentRiddle,
    });
  });
}

/** Updates module members in popup.js state. */
export function updateStateInPopup(_riddles, _currentRiddle) {
  riddles = _riddles;
  currentRiddle = _currentRiddle;
}

/** Recursively inserts files on parent with correct margin. */
export function insertFiles(parent, object, count) {
  for (const childFilename in object.children) {
    const child = object.children[childFilename];
    const figure = getFileFigureHtml(child, childFilename, count + 1);
      parent.append(figure);
    if (child.folder) {
      const div = $('<div class="folder-files"></div>');
      div.appendTo(parent);
      insertFiles(div, child, count + 1);
    }
  }
}

/** Generates `<figure>` HTML tag for given file object. */
function getFileFigureHtml(object, filename, count) {
  let type = 'folder';
  if (!object.folder) {
    const i = filename.lastIndexOf('.');
    type = filename.substr(i+1);
  }
  const url = `images/icons/extensions/${type}.png`;
  const state = (type == 'folder') ? 'open' : '';
  const margin = `${0.4 * count}em`;
  const img = `<img src="${url}">`;
  const fc = `<figcaption>${filename}</figcaption>`;
  let fileCount = '';
  if (object.folder) {
    const riddle = riddles[currentRiddle];
    const level = riddle.levels[riddle.shownSet][riddle.shownLevel];
    const filesFound = object.filesFound;
    const filesTotal = level.beaten ? object.filesTotal : '??';
    fileCount =
      `<div class="file-count">(${filesFound} / ${filesTotal})</div>`;
  }
  const html = `
    <figure class="file ${state}"
      title="${object.path}"
      data-username="${object.username}"
      data-password="${object.password}"
      style="margin-left: ${margin}"
    >
      ${img}${fc}${fileCount}
    </figure>
  `;
  return html;
}

/** Changes displayed level to previous or next one, upon arrow click. */
export function changeLevel() {
  const riddle = riddles[currentRiddle];
  let level = riddle.levels[riddle.shownSet][riddle.shownLevel];
  const levelName =
    $(this).hasClass('previous') ?
      level.previous : level.next;
  // riddle.shownSet = 
  riddle.shownLevel = levelName;
  level = riddle.levels[riddle.shownSet][levelName];
  $('#level > var.current').text(levelName);
  $('#level > .previous').toggleClass('disabled', !level.previous);
  $('#level > .next').toggleClass('disabled', !level.next);
  $('.page-explorer').empty();
  insertFiles($('.page-explorer'), level.pages['/'], -1);
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
    const path = $(this).attr('title');
    const endpoint = `${SERVER_URL}/${currentRiddle}/levels/get-root-path`;
    await fetch(endpoint)
      .then(response => response.text())
      .then(rootPath => {
        let url = rootPath + path;
        if ($(this).attr('data-username')) {
          let username = $(this).attr('data-username');
          let password = $(this).attr('data-password');
          url = url.replace('://', `://${username}:${password}@`);
        }
        window.open(url, '_blank');
      });
  } else {
    // Open or collapse folder, showing/hiding inner files
    const files = $(this).next('.folder-files');
    files.toggle();
  }
}

(async () => {
  // Inits page explorer for currently visited riddle level
  const DATA_URL = `${SERVER_URL}/get-user-riddle-data`;
  await fetch(DATA_URL)
    .then(response => response.json())
    .then(async riddlesData => {
      currentRiddle = riddlesData.currentRiddle;
      Object.entries(riddlesData.riddles).forEach(async ([alias, riddle]) => {
        console.log(`[${alias}] Building riddle data…`);
        await buildRiddle(riddle);
        console.log(riddle);
      });
      sendMessageToPopup();
    });
})();
