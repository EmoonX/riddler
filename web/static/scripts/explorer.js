// Dictionary of all folders and pages/files
var pages;

// Dictionary of sets of current pages for each level
var currentPages = {};

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
      changeDir(explorer, folder);
      
      // Scroll page to accomodate view to margin-top
      $('html').animate({
        scrollTop: row.offset().top
      }, 500);
    }
  });
}

function getFolderEntry(path) {
  // Get pages dictionary entry corresponding to bottom folder in path
  const segments = path.split('/').slice(1, -1);
  var folder = pages['/'];
  segments.forEach(seg => {
    folder = folder['children'][seg];
  });
  return folder;
}

function changeDir(explorer, folderPath) {
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
  const levelName = explorer.prev().find('.key > input').val();
  const folder = getFolderEntry(folderPath);
  $.each(folder['children'], (page, row) => {
    var name = 'folder';
    const j = page.lastIndexOf('.');
    if (j != -1) {
      name = page.substr(j + 1);
    }
    var current = '';
    if (name == 'folder') {
      if (row['levels'][levelName]) {
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
      if (row['levels'][levelName]) {
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
  // const files_total = explorer.data('files_total');
  // const total = files_total[folder];
  // const comp = explorer.find('.completion');
  // const vars = comp.find('var');
  // vars[0].textContent = total ? total : '--';
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
    const folderPath = explorer.find('.path').text();
    const folder = getFolderEntry(folderPath)
    const row = folder['children'][page];
    if ($(this).hasClass('current')) {
      const frontPath = explorer.prev().find('.front-path');
      if (! frontPath.val()) {
        frontPath.val(row['path']);
      }
      if (! currentPages[levelName]) {
        currentPages[levelName] = new Set();
      }
      row['level_name'] = levelName;
      currentPages[levelName].add(row['path']);
    } else {
      row['level_name'] = 'NULL';
      currentPages[levelName].delete(row['path']);
    }
    const index = explorer.attr('id');
    const json = JSON.stringify([...currentPages[levelName]]);
    $(`input[name="${index}-pages"]`).last().val(json);

    // Recursively mark/unmark parent folders for highlighting
    const segments = folderPath.split('/').slice(1, -1);
    var parent = pages['/'];
    segments.forEach(seg => {
      const folder = parent['children'][seg];
      if ($(this).hasClass('current')) {
        if (! folder['levels'][levelName]) {
          folder['levels'][levelName] = 0;
        }
        folder['levels'][levelName] += 1;
      } else {
        folder['levels'][levelName] -= 1;
      }
      console.log(seg)
      console.log(folder['levels'])
      parent = folder;
    });
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
  // const aux = location.href.split('/').slice(0, -1);
  // aux.push('get-pages');
  // const url = aux.join('/');
  // $.get(url, data => {
  //   pages = JSON.parse(data);
  // });
  // Dinamically register events for (current or new) explorer actions
  $('.levels').on('click', '.row .menu-button', toggleExplorer);
  $('.levels').on('click', '.page-explorer .folder-up', folderUp);
  $('.levels').on('click', '.page-explorer figure', clickIcon);
  $('.levels').on('dblclick', '.page-explorer figure', doubleClickIcon);

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
  