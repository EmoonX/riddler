// Dictionary of all folders and pages/files
export var pages = {};

export function setPages(json) {
  // Set pages dict(s) from JSON data
  pages = JSON.parse(json);
}

export function toggleExplorer() {
  // Toggle page explorer

  const row = $(this).parents('.row');
  const explorer = row.next('.page-explorer');

  // Wait until "display: none" is toggled so to not break transition
  row.toggleClass('active');
  explorer.toggle(0, _ => {
    explorer.toggleClass('active');
    if (explorer.hasClass('active')) {
      // Change to initial (front page) directory
      const node = explorer.find('.path');
      const folder = node.text();
      const admin = row.parents('.list').hasClass('admin');
      changeDir(explorer, folder, admin);
      
      // Scroll page to accomodate view to margin-top
      $('html').animate({
        scrollTop: row.offset().top
      }, 500);
    }
  });
}

export function getFolderEntry(path, level, admin) {
  // Get pages dictionary entry corresponding to bottom folder in path
  const segments = path.split('/').slice(1, -1);
  var folder;
  if (!admin) {
    folder = pages[level]['/'];
  } else {
    // Admin
    folder = pages['/'];
  }
  segments.forEach(seg => {
    folder = folder['children'][seg];
  });
  return folder;
}

export function changeDir(explorer, folderPath, admin) {
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
  // const levelName = explorer.prev().find('.key > input').val();
  var levelName;
  if (!admin) {
    levelName = explorer.prev().find('.name').text();
  } else {
    levelName = explorer.prev().find('.name input').val();
  }
  const folder = getFolderEntry(folderPath, levelName, admin);
  $.each(folder['children'], (page, row) => {
    var name = 'folder';
    const j = page.lastIndexOf('.');
    if (j != -1) {
      name = page.substr(j + 1);
    }
    var current = '';
    if (admin) {
      if (name == 'folder') {
        if (row['levels'][levelName]) {
          current = 'class="current"';
        }
      } else {
        if (row['level_name'] == levelName) {
          current = 'class="current"';
        }
      }
    }
    const path = row['path'];
    const img = `<img src="/static/icons/${name}.png">`;
    const fc = `<figcaption>${page}</figcaption>`;
    const figure = `<figure ${current} title="${path}">${img}${fc}</figure>`;
    
    // Append current level files in correct order
    // (current folders -> other folders -> current files -> other files)
    if (name == 'folder') {
      const folderNode = files.children('.folder');
      if (admin && row['levels'][levelName]) {
        folderNode.children('.first').append(figure);
      } else {
        folderNode.append(figure);
      }
    } else {
      if (admin && row['level_name'] == levelName) {
        files.children('.first').append(figure);
      } else {
        files.append(figure);
      }
    }
  });
  // Pop icons sequentially
  popIcons(explorer);

  // Update folder's files count and total
  const found = folder['files_found'];
  const total = folder['files_total'];
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
  const re = /\w+\/$/g;
  const folder = node.text().replace(re, '');
  const admin = explorer.parents('.list').hasClass('admin');
  changeDir(explorer, folder, admin);
}

$(_ => {
  // Dinamically register events for (current or new) explorer actions
  $('.levels').on('click', '.row .menu-button', toggleExplorer);
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
      var url = location.href;
      url = url.replace('/admin', '').replace('/levels', '/update-pages');
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
  