// Dictionary of all folders and pages/files
export var pages = {};

export function initExplorer(pagesData, levelName) {
  setPages(pagesData, levelName);
  console.log(pages);

  // Register folder up event
  $('.page-explorer .folder-up').on('click', folderUp);

  const explorer = $('.page-explorer');
  const folder = '/';
  changeDir(explorer, folder);
}

export function setPages(json, levelName) {
  // Set pages dict(s) from JSON data
  pages = JSON.parse(json);
  console.log(pages);
  pages = pages[levelName];
}

/** Get pages dictionary entry corresponding to bottom folder in path. */
export function getFolderEntry(path) {
  const segments = path.split('/').slice(1, -1);
  const folder = pages['/'];
  segments.forEach(seg => {
    folder = folder['children'][seg];
  });
  return folder;
}

export function changeDir(explorer, folderPath) {
  // Change current directory

  // Update directory on field
  const node = explorer.find('.path');
  node.text(folderPath);

  // Erase previous files from <div>
  const files = explorer.find('.files');
  files.empty();
  files.append('<span class="folder"></span>');
  files.find('.folder').append('<span class="first"></span>');
  files.append('<span class="first"></span>');

  // And now add the current dir files
  const folder = getFolderEntry(folderPath);
  $.each(folder['children'], (page, row) => {
    let name = 'folder';
    const j = page.lastIndexOf('.');
    if (j != -1) {
      name = page.substr(j + 1);
    }
    var current = '';
    const path = row['path'];
    var accessTimeMessage = '';
    if (name != 'folder') {
      const accessTime = row['access_time'];
      accessTimeMessage = `&#10;↳ found on ${accessTime}`;
    }
    const extensionsURL = 'https://riddler.app/static/icons/extensions';
    const img = `<img src="${extensionsURL}/${name}.png" width="20">`;
    const fc = `<figcaption>${page}</figcaption>`;
    const figure = `<figure ${current} 
        title="${path}${accessTimeMessage}">${img}${fc}</figure>`;
    
    // Append current level files in correct order
    // (current folders -> other folders -> current files -> other files)
    if (name == 'folder') {
      const folderNode = files.children('.folder');
      folderNode.append(figure);
    } else {
      files.append(figure);
    }
  });
  // Pop icons sequentially
  popIcons(explorer);

  // Update folder's files count and total
  // const found = folder['files_found'];
  // const total = folder['files_total'];
  // explorer.find('.completion .found').text(found);
  // explorer.find('.completion .total').text(total);
  // toggleCheck(explorer);
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

export function folderUp() {
  // Change current directory to one up
  const explorer = $(this).parents('.page-explorer');
  const node = explorer.find('.path');
  if (node.text() == '/') {
    // Nothing to do if already on top folder
    return
  }
  const re = /\w+\/$/g;
  const folder = node.text().replace(re, '');
  const admin = explorer.parents('.list').hasClass('admin');
  changeDir(explorer, folder, admin);
}
  