export function toggleExplorer() {
  // Toggle page explorer
  const row = $(this).parents('.row');
  const explorer = row.next('.page-explorer');
  row.toggleClass('active');
  explorer.toggleClass('active');

  const prev = row.prev();
  if (explorer.hasClass('active')) {
    // Pop initial icons
    popIcons(explorer);
    
    // Scroll page to accomodate view to margin-top
    if (prev.hasClass('page-explorer') && (! prev.hasClass('active'))) {
      scroll(0, scrollY + 50);
    }
  } else {
    // Undo the changes done
    explorer.find('figure').removeClass('show');
    if (prev.hasClass('page-explorer') && (! prev.hasClass('active'))) {
      scroll(0, scrollY - 50);
    }
  }
}

function popIcons(explorer) {
  // "Icons popping in sequence" effect
  explorer.find('figure').each(function (index) {
    const t = 50 * index;
    setTimeout(_ => {
      $(this).addClass('show');
    }, t);
  });
}

export function clickIcon() {
  // Make clicked file/page "active" and all others inactive
  $('.page-explorer figure').each(function () {
    $(this).removeClass('active');
  });
  $(this).addClass('active');
}

export function doubleClickIcon() {
  // Action to be taken upon double-clicking icon
  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1) {
    // Open desired page in new tab
    const explorer = $(this).parents('.page-explorer');
    const path = explorer.find('nav > .content > .path')[0].textContent +
        $(this).find('figcaption')[0].textContent;
    const url = 'http://rnsriddle.com' + path;
    window.open(url, '_blank');
  } else {
    // Change current directory to folder's one
    var explorer = $(this).parents('.page-explorer');
    var node = explorer.find('.path');
    var folder = node.text() + page + '/';
    changeDir(folder, explorer, node);
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
  changeDir(folder, explorer, node);
}

function changeDir(folder, explorer, node) {
  // Update directory on field
  node.text(folder);

  // Get JS object data converted from Python dict
  var data = explorer.data('folders').replaceAll('\'', '"');
  data = data.replaceAll('None', '"NULL"');
  const folders = JSON.parse(data);
  const files_total = explorer.data('files_total');

  // Erase previous files and add new ones
  const files = explorer.find('.files');
  files.empty();
  console.log(folders);
  folders[folder]['files'].forEach(function (row) {
    const page = row['page'];
    var name = 'folder';
    const j = page.lastIndexOf('.');
    if (j != -1) {
      name = page.substr(j + 1);
    }
    const img = `<img src="/static/icons/${name}.png">`;
    const fc = `<figcaption>${page}</figcaption>`;
    const figure = `<figure>${img}${fc}</figure>`;
    files.append(figure)
  });
  // Pop icons sequentially
  popIcons(explorer);

  // Update folder's files count and total
  const total = files_total[folder]
  const comp = explorer.find('.completion')
  const vars = comp.find('var')
  vars[0].textContent = total ? total : '--';
}

$(_ => {
  $('.menu').on('click', toggleExplorer);
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
        .done(_ => {console
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
  