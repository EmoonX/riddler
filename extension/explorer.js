// Dictionary of all folders and pages/files
export var pages = {};

/** Inits page explorer for given riddle level. */
export function initExplorer(pagesData, levelName) {
  setPages(pagesData, levelName);
  insertFiles(pages['/'], '/', -1);
}

/** Sets pages dict(s) from JSON data. */
function setPages(json, levelName) {
  pages = JSON.parse(json);
  pages = pages[levelName];
}

/** Recursively insert files on explorer with correct margin. */
function insertFiles(object, filename, count) {
  if (filename != '/') {
    const figure = getFileFigureHtml(object, filename, count);
    $('.page-explorer').append(figure);
  }
  for (const childFilename in object.children) {
    const child = object.children[childFilename];
    if (child.folder) {
      insertFiles(child, childFilename, count + 1)
    } else {
      const figure = getFileFigureHtml(child, childFilename, count + 1);
      $('.page-explorer').append(figure);
    }
  }
}

/** Generate `<figure>` HTML tag for given file oject. */
function getFileFigureHtml(object, filename, count) {
  let type = 'folder';
  if (!object.folder) {
    const i = filename.lastIndexOf('.');
    type = filename.substr(i+1);
  }
  const url = `https://riddler.app/static/icons/extensions/${type}.png`;
  const margin = `${0.4 * count}em`;
  const img = `<img src="${url}">`;
  const fc = `<figcaption>${filename}</figcaption>`;
  const html = `
    <figure class="file"
      title="${object.path}" style="margin-left: ${margin}"
    >
      ${img}${fc}
    </figure>
  `;
  return html;
}

/** Select file and unselect the other ones, as in a file explorer. */
function clickFile() {
  const files = $(this).parents('.page-explorer').find('figure.file');
  files.each(function () {
    $(this).removeClass('active');
  });
  $(this).addClass('active');
}

/** Animate "files popping in sequence" visual effect. */
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
});
  