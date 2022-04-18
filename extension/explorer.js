// Dictionary of all folders and pages/files
export var pages = {};

export function initExplorer(pagesData, levelName) {
  setPages(pagesData, levelName);
  console.log(pages);

  insertPages(pages['/'], '/', 0)
}

function setPages(json, levelName) {
  // Set pages dict(s) from JSON data
  pages = JSON.parse(json);
  pages = pages[levelName];
}

function insertPages(object, filename, count) {
  if (filename != '/') {
    const figure = getFigureHtml(object, filename, count);
    $('.page-explorer').append(figure);
  }
  for (const childFilename in object.children) {
    const child = object.children[childFilename];
    if (child.folder) {
      insertPages(child, childFilename, count + 1)
    } else {
      const figure = getFigureHtml(child, childFilename, count + 1);
      $('.page-explorer').append(figure);
    }
  }
}

function getFigureHtml(object, filename, count) {
  let type = 'folder';
  if (!object.folder) {
    const i = filename.lastIndexOf('.');
    type = filename.substr(i+1);
  }
  const url = `https://riddler.app/static/icons/extensions/${type}.png`;
  const margin = `${0.4 * count}em`;
  const img = `<img src="${url}" style="margin-left: ${margin}">`;
  const fc = `<figcaption>${filename}</figcaption>`;
  const html = `<figure>${img}${fc}</figure>`;
  return html;
}

function popIcons(explorer) {
  // "Icons popping in sequence" effect
  explorer.find('figure').each(function (index) {
    const t = 50 * (index + 1);
    setTimeout(_ => {
      $(this).addClass('show');
    }, t);
  });
}
  