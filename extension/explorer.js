/** Current riddle alias. */
var currentRiddle;

/** Dictionary of all folders and pages/files. */
var pages = {};

/** Inits page explorer for given riddle level. */
export function initExplorer(alias, pagesData, levelName) {
  currentRiddle = alias;
  setPages(pagesData, levelName);
  insertFiles($('.page-explorer'), pages['/'], '/', -1);
}

/** Sets pages dict(s) from JSON data. */
function setPages(json, levelName) {
  pages = JSON.parse(json);
  pages = pages[levelName];
}

/** Recursively inserts files on parent with correct margin. */
function insertFiles(parent, object, filename, count) {
  for (const childFilename in object.children) {
    const child = object.children[childFilename];
    const figure = getFileFigureHtml(child, childFilename, count + 1);
      parent.append(figure);
    if (child.folder) {
      const div = $('<div class="folder-files"></div>')
      div.appendTo(parent);
      insertFiles(div, child, childFilename, count + 1);
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
  const url = `https://riddler.app/static/icons/extensions/${type}.png`;
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
    const endpoint =
      `https://riddler.app/${currentRiddle}/levels/get-root-path`;
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
  $('.page-explorer').on('click', 'figure.file', clickFile);
  $('.page-explorer').on('dblclick', 'figure.file', doubleClickFile);
});
  