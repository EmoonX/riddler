/** Base server URL. */
const SERVER_URL = 'https://riddler.app';

/** Dictionary of all durrent player riddle data. */
var riddles = {};

/** Current riddle alias. */
var currentRiddle;

/** Inits page explorer for current visited riddle level. */
export function initExplorer() {
  const DATA_URL = SERVER_URL + '/get-user-riddle-data';
  $.get(DATA_URL, json => {
    const riddlesData = JSON.parse(json);
    console.log(riddlesData);
    currentRiddle = riddlesData.currentRiddle;
    $.each(riddlesData.riddles, (_, data) => {
      buildRiddle(data);
    });
    sendMessageToPopup();
  });
}

/** Builds riddle dict from riddle and levels JSON data. */
function buildRiddle(data) {
  const alias = data.alias;
  const pagesUrl = SERVER_URL + `/${alias}/levels/get-pages`;
  $.get(pagesUrl, json => {
    const pagesData = JSON.parse(json);
    riddles[alias] = data;
    const riddle = riddles[alias];
    riddle.iconUrl = `images/riddles/${alias}.png`;
    riddle.shownLevel = riddle.visitedLevel;
    riddle.levels = {};
    $.each(pagesData, (levelName, pages) => {
      const level = {
        name: levelName,
        pages: pages,
      }
      riddle.levels[levelName] = level;
    });
    $.each(riddle.levelOrdering, (i, levelName) => {
      let previousName = null;
      if (i > 0) {
        previousName = riddle.levelOrdering[i-1];
        riddle.levels[previousName].next = levelName;
      }
      riddle.levels[levelName].previous = previousName;
    });
  });
}

/** Updates current dict with possibly new riddle, level and/or page. */
export function updateRiddleData(alias, levelName) {
  currentRiddle = alias;
  if (!(alias in riddles) || !(levelName in riddles[alias].levels)) {
    // Add new riddle and/or level
    const DATA_URL = SERVER_URL + `/get-user-riddle-data/${alias}`;
    $.get(DATA_URL, json => {
      const data = JSON.parse(json);
      buildRiddle(data);
    });
  } else {
    // Add (possibly) new page
    const pagesUrl = SERVER_URL + `/${alias}/levels/get-pages/${levelName}`;
    $.get(pagesUrl, json => {
      const pagesData = JSON.parse(json);
      const riddle = riddles[alias];
      riddle.visitedLevel = levelName
      riddle.shownLevel = levelName;
      $.each(pagesData, (levelName, pages) => {
        const level = riddle.levels[levelName];
        level.pages = pages;
      });
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

/** Generates `<figure>` HTML tag for given file oject. */
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
    const levelSolved = riddle.shownLevel in riddle.solvedLevels;
    const filesFound = object.filesFound;
    const filesTotal = levelSolved ? object.filesTotal : '??';
    fileCount =
      `<div class="file-count">(${filesFound} / ${filesTotal})</div>`;
  }
  const html = `
    <figure class="file ${state}"
      title="${object.path}" style="margin-left: ${margin}"
    >
      ${img}${fc}${fileCount}
    </figure>
  `;
  return html;
}

/** Changes displayed level to previous or next one, upon arrow click. */
function changeLevel() {
  const riddle = riddles[currentRiddle];
  let level = riddle.levels[riddle.shownLevel];
  const levelName =
    $(this).hasClass('previous') ?
      level.previous : level.next;
  riddle.shownLevel = levelName;
  level = riddle.levels[levelName];
  $('#level > var.current').text(levelName);
  $('#level > .previous').toggleClass('disabled', !level.previous);
  $('#level > .next').toggleClass('disabled', !level.next);
  $('.page-explorer').empty();
  insertFiles($('.page-explorer'), level.pages['/'], -1);
}

/** Selects file and unselect the other ones, as in a file explorer. */
function clickFile() {
  const files = $(this).parents('.page-explorer').find('figure.file');
  files.each(function () {
    $(this).removeClass('active');
  });
  $(this).addClass('active');
}

/** Handles double clicking files or folders. */
function doubleClickFile() {
  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1) {
    // Open desired page in new tab
    const path = $(this).attr('title');
    const endpoint = SERVER_URL + `${currentRiddle}/levels/get-root-path`;
    $.get(endpoint, rootPath => {
      const url = rootPath + path;
      window.open(url, '_blank');
    });
  } else {
    // Open or collapse folder, showing/hiding inner files
    const files = $(this).next('.folder-files');
    files.toggle();
  }
}

/** Animates "files popping in sequence" visual effect. */
function popIcons(explorer) {
  explorer.find('figure').each(function (index) {
    const t = 50 * (index + 1);
    setTimeout(_ => {
      $(this).addClass('show');
    }, t);
  });
}

$(_ => {
  $('#level').on('click', '.previous:not(.disabled)', changeLevel);
  $('#level').on('click', '.next:not(.disabled)', changeLevel);
  $('.page-explorer').on('click', 'figure.file', clickFile);
  $('.page-explorer').on('dblclick', 'figure.file', doubleClickFile);
});
  