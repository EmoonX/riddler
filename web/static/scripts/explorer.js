// Dictionary of all folders and pages/files
export let pages = {};

export function toggleExplorer() {
  // Toggle page explorer

  const row = $(this).parents('.row');
  const explorer = row.next('.page-explorer');
  const admin = row.parents('.list').hasClass('admin');
  if (admin && (! explorer.hasClass('active'))) {
    // Don't open explorer until level name is supplied
    const levelName = row.find('.name input').val()
    if (! levelName) {
      return;
    }
  }
  // Wait until "display: none" is toggled so to not break transition
  row.toggleClass('active');
  explorer.toggle(0, _ => {
    explorer.toggleClass('active');
    if (explorer.hasClass('active')) {
      // Change to initial (front page) directory
      const node = explorer.find('.path');
      const folderPath = node.text();
      changeDir(explorer, folderPath, admin);

      // Scroll page to accomodate view to margin-top
      $('html').animate({
        scrollTop: row.offset().top
      }, 500);
    }
  });
}

export function getFolderEntry(folderPath, level, admin) {
  // Get pages dictionary entry corresponding to bottom folder in path
  const segments = folderPath.split('/').slice(1, -1);
  let folder = admin ?  pages['/'] : pages[level]['/'];
  segments.forEach(seg => {
    folder = folder['children'][seg];
  });
  return folder;
}

export function changeDir(explorer, folderPath, admin) {
  // Change current directory

  // Update directory on field
  const pathNode = explorer.find('.path');
  pathNode.text(folderPath);
  
  // Erase previous files from <div>
  const files = explorer.find('.files');
  files.empty();
  files.append('<span class="folder"></span>');
  files.find('.folder').append('<span class="first"></span>');
  files.append('<span class="first"></span>');

  // Get level and folder entry
  const prev = explorer.prev()
  const levelName = (
    admin ?
    prev.find('.name input').val() :
    prev.find('.level-name').text()
  ).trim();
  const folder = getFolderEntry(folderPath, levelName, admin);

  // Show credentials if current folder has associated un/pw
  const credentials = explorer.find('.credentials');
  if (folder.username !== undefined || folder.password !== undefined) {
    credentials.toggle(true);
    credentials.find('.username').text(folder.username || '???');
    credentials.find('.password').text(folder.password || '???');
  } else {
    credentials.toggle(false);
  }

  // Get sorted (by extension and then name) pages object
  const pages =
    Object.keys(folder.children)
    .sort((a, b) => {
      const i = a.lastIndexOf('.');
      const j = b.lastIndexOf('.');
      if (i == -1 || j == -1) {
        return (
          (i == j) ?
            a.localeCompare(b) : ((i == -1) ? +1 : -1)
        );
      } else {
        const aExt = a.substring(i+1);
        const bExt = b.substring(j+1);
        return (
          (aExt != bExt) ?
            aExt.localeCompare(bExt) : a.localeCompare(b)
        );
      }
    }).reduce(
      (obj, key) => {
        obj[key] = folder.children[key];
        return obj;
      },
      {}
    )
  ;
  // And now add the current dir files
  $.each(pages, (filename, node) => {
    let type;
    if (node.folder) {
      type = 'folder';
    } else if (filename.indexOf('.') === -1) {
      type = 'html';
    } else if (node.unknownExtension) {
      type = 'unknown';
    } else {
      type = filename.split('.').at(-1).toLowerCase();
    }
    let class_ = 'file';
    if (type === 'folder') {
      class_ += ' folder';
    }
    if (admin) {
      if (type === 'folder') {
        if (node['levels'][levelName]) {
          class_ += ' current';
        }
      } else {
        if (node['level_name'] == levelName) {
          class_ = ' current';
        }
      }
    }
    let accessTimeMessage = '';
    if (type !== 'folder') {
      const accessTime = node['access_time'];
      accessTimeMessage = `&#10;↳ found on ${accessTime}`;
    }
    const figure = `
      <figure
        class="${class_}"
        title="${node['path']}${accessTimeMessage}"
        data-username=${node['username']}
        data-password=${node['password']}
      >
        <img src="/static/icons/extensions/${type}.png">
        <figcaption>${filename}</figcaption>
      </figure>
    `;

    // Append current level files in correct order
    // (current folders -> other folders -> current files -> other files)
    if (type === 'folder') {
      const folderNode = files.children('.folder');
      if (admin && node['levels'][levelName]) {
        folderNode.children('.first').append(figure);
      } else {
        folderNode.append(figure);
      }
    } else {
      if (admin && node['level_name'] == levelName) {
        files.children('.first').append(figure);
      } else {
        files.append(figure);
      }
    }
  });
  // Pop icons sequentially
  popIcons(explorer);

  // Update folder's files count and total
  const found = folder['filesFound'];
  const total = folder['filesTotal'];
  explorer.find('.completion .found').text(found);
  explorer.find('.completion .total').text(total);
  toggleCheck(explorer);
}

function toggleCheck(explorer) {
  // Display check mark if all files found
  const check = explorer.find('.check')
  const found = explorer.find('.completion .found').text()
  const total = explorer.find('.completion .total').text()
  if (found != "--" && found == total) {
    check.show();
  } else {
    check.hide();
  }
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
  const re = /[^/]+\/$/g;
  const folder = node.text().replace(re, '');
  const admin = explorer.parents('.list').hasClass('admin');
  changeDir(explorer, folder, admin);
}

(async () => {
  // Get JS object data converted from Python dict
  const aux = location.href.split('/');
  aux.push('get-pages');
  const url = aux.join('/');
  await fetch(url)
    .then(data => data.json())
    .then(object => {
      // Set pages content from response data
      pages = object;

      // Add click handler _only after_ dictionary is built
      $('.levels').on('click', '.row .menu-button', toggleExplorer);
    });

  // Dinamically register events for (current or new) explorer actions
  $('.levels').on('click', '.page-explorer .folder-up', folderUp);
  $('button[name="upload-pages"]').on('click', function () {
    // Open (hidden) file browser when clicking upload button
    $('input[name="pages"]').trigger('click');
  });
  $('input[name="pages"]').on('change', function () {
    // Send POST request with chosen paths text file
    const reader = new FileReader();
    reader.onload = (e => {;
      const data = e.target.result;
      $.post(`${location.href}/upload-pages`, data, 'text')
        .fail(_ => {
          // Error, something went wrong on server side
          console.log('[Upload pages] Error updating page/level data...');
        })
        .done(_ => {
          // Success, so reload the current page to see changes
          console.log('[Upload pages] Page/level data successfully updated!');
          location.reload();
        });
      ;
    });
    const file = $(this).get(0).files[0];
    reader.readAsText(file);
  });
})();
