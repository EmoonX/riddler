// Dictionary of all folders and pages/files
var folders;
var pages = new Set();

export function toggleExplorer() {
  // Toggle page explorer

  const row = $(this).parents('.row');
  const explorer = row.next('.page-explorer');

  // Wait until "display: none" is toggled so to not break transition
  row.toggleClass('active');
  explorer.toggle(0, _ => {
    explorer.toggleClass('active');
    const prev = row.prev();
    if (explorer.hasClass('active')) {
      // Change to initial (front page) directory
      const node = explorer.find('.path');
      const folder = node.text();
      changeDir(explorer, folder);
      console.log(folders)
      
      // Scroll page to accomodate view to margin-top
      $('html').animate({
        scrollTop: row.offset().top
      }, 500);
    }
  });
}

function changeDir(explorer, folder) {
  // Change current directory

  // Update directory on field
  const node = explorer.find('.path');
  node.text(folder);

  // Erase previous files from <div>
  const files = explorer.find('.files');
  files.empty();
  files.append('<span class="folder"></span>');
  files.find('.folder').append('<span class="first"></span>');
  files.append('<span class="first"></span>');

  // And now add the current dir files
  const levelName = explorer.prev().find('.key > input').val();
  folders[folder]['files'].forEach(function (row) {
    const page = row['page'];
    var name = 'folder';
    const j = page.lastIndexOf('.');
    if (j != -1) {
      name = page.substr(j + 1);
    }
    var current = '';
    if (name == 'folder') {
      if (row['level_name'][levelName]) {
        current = 'class="current"';
      }
    } else {
      if (row['level_name'] == levelName) {
        current = 'class="current"';
      }
    }
    const img = `<img src="/static/icons/${name}.png">`;
    const fc = `<figcaption>${page}</figcaption>`;
    const figure = `<figure ${current}>${img}${fc}</figure>`;
    
    // Append current level files in correct order
    // (current folders -> other folders -> current files -> other files)
    if (name == 'folder') {
      const folderNode = files.children('.folder');
      if (row['level_name'][levelName]) {
        folderNode.children('.first').append(figure);
      } else {
        folderNode.append(figure);
      }
    } else {
      if (row['level_name'] == levelName) {
        files.children('.first').append(figure);
      } else {
        files.append(figure);
      }
    }
  });
  // Pop icons sequentially
  popIcons(explorer);

  // Update folder's files count and total
  const files_total = explorer.data('files_total');
  const total = files_total[folder];
  const comp = explorer.find('.completion');
  const vars = comp.find('var');
  vars[0].textContent = total ? total : '--';
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

export function clickIcon() {
  // Mark/unmark file/page as belonging to current level
  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1) {
    $(this).toggleClass('current');
    const explorer = $(this).parents('.page-explorer');
    const levelName = explorer.prev().find('.key > input').val();
    var folder = explorer.find('.path').text();
    const row = folders[folder]['files'].find(
        row => (row['page'] == page));
    if ($(this).hasClass('current')) {
      const frontPath = explorer.prev().find('.front-path');
      if (! frontPath.val()) {
        frontPath.val(row['path'].substr(1));
      }
      pages.add(row['path']);
    } else {
      row['level_name'] = 'NULL';
      pages.delete(row['path']);
    }
    const json = JSON.stringify([...pages]);
    $('input[name="new-pages"]').last().val(json);
    row['level_name'] = levelName;
    var folder = folder.split('/').slice(0, -1).join('/') + '/';
    while (folder != '/') {
      parent = folder.split('/').slice(0, -2).join('/') + '/';
      const row = folders[parent]['files'].find(
        row => ((row['path'] + '/') == folder));
      row['level_name'].append(levelName);
      folder = parent;
    }
  }
}

export function doubleClickIcon() {
  // Action to be taken upon double-clicking icon
  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1) {
    // Open desired page in new tab
    const explorer = $(this).parents('.page-explorer');
    const path = explorer.find('.path').text() +
        $(this).find('figcaption').text();
    const url = 'http://rnsriddle.com' + path;
    window.open(url, '_blank');
  } else {
    // Change current directory to folder's one
    const explorer = $(this).parents('.page-explorer');
    const node = explorer.find('.path');
    const folder = node.text() + page + '/';
    changeDir(explorer, folder);
  }
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
  changeDir(explorer, folder);
}

$(_ => {
  // Get JS object data converted from Python dict
  var data = $('form').data('folders').replaceAll('\'', '"');
  data = data.replaceAll('None', '"NULL"');
  folders = JSON.parse(data);

  // Event handlers
  $('.menu-button').on('click', toggleExplorer);
  $('.page-explorer .folder-up').on('click', folderUp);
  $('.page-explorer').on('click', 'figure', clickIcon);
  $('.page-explorer').on('dblclick', 'figure', doubleClickIcon);

  $('button[name="upload-pages"]').on('click', function () {
    // Open (hidden) file browser when clicking upload button
    $('input[name="pages"]').trigger('click');
  });
  $('input[name="pages"]').on('change', function () {
    // Send POST request with chosen paths text file
    const reader = new FileReader();
    reader.onload = (e => {;
      const data = e.target.result;
      const url = location.href.replace('/levels/', '/update-pages/');
      $.post(url, data, 'text')
        .fail(_ => {
          // Error, something went wrong on server side
          console.log('[Upload pages] Error updating database...');
        })
        .done(_ => {
          // Success, so reload the current page to see changes
          console.log('[Upload pages] Database successfully updated!');
          location.reload();
        });
      ;
    });
    const file = $(this).get(0).files[0];
    reader.readAsText(file);
  });
});
  