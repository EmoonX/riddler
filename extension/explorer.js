/** Base server URL. */
const SERVER_URL = 'https://riddler.app';

/** Dictionary of all durrent player riddle data. */
var riddles = {};

/** Current riddle alias. */
var currentRiddle;

/** Updates members from popup.js state. */
export function update(_riddles, _currentRiddle) {
  riddles = _riddles;
  currentRiddle = _currentRiddle;
}

/** Inits page explorer for current visited riddle level. */
export function initExplorer(callback) {
  const DATA_URL = SERVER_URL + '/get-current-riddle-data';
  $.get(DATA_URL, json => {
    const riddleData = JSON.parse(json);
    currentRiddle = riddleData['alias'];
    const pagesUrl = SERVER_URL + `/${currentRiddle}/levels/get-pages`;
    $.get(pagesUrl, json => {
      const pagesData = JSON.parse(json);
      console.log(pagesData)
      buildRiddle(riddleData, pagesData);
      callback(riddles, currentRiddle);
    });
  });
}

/** Builds riddle dict from riddle and levels JSON data. */
function buildRiddle(riddleData, pagesData) {
  riddles[currentRiddle] = {};
  const riddle = riddles[currentRiddle];
  const levelOrdering = riddleData.levelOrderings[currentRiddle];
  riddle.fullName = riddleData.fullName;
  riddle.iconUrl = SERVER_URL + `/static/riddles/${currentRiddle}.png`
  riddle.visitedLevel = riddleData.lastVisitedLevels[currentRiddle];
  riddle.shownLevel = riddle.visitedLevel;
  riddle.levels = {};
  $.each(pagesData, (levelName, pages) => {
    const level = {
      name: levelName,
      pages: pages,
    }
    riddle.levels[levelName] = level;
  });
  $.each(levelOrdering, (i, levelName) => {
    let previousName = null;
    if (i > 0) {
      previousName = levelOrdering[i-1];
      riddle.levels[previousName].next = levelName;
    }
    riddle.levels[levelName].previous = previousName;
  });
}

export function setCurrentRiddleAndLevel(riddle, level) {
  currentRiddle = riddle;
  riddles[riddle].currentLevel = level;
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
  const url = SERVER_URL + `/static/icons/extensions/${type}.png`;
  const state = (type == 'folder') ? 'open' : '';
  const margin = `${0.4 * count}em`;
  const img = `<img src="${url}">`;
  const fc = `<figcaption>${filename}</figcaption>`;
  const html = `
    <figure class="file ${state}"
      title="${object.path}" style="margin-left: ${margin}"
    >
      ${img}${fc}
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
  