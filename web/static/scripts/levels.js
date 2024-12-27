import {
  changeDir
}
  from './explorer.js';

function clickIcon() {
  // Select icon if not a folder one
  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1) {
    const figures = $(this).parents('.files').find('figure');
    figures.each(function () {
      $(this).removeClass('active');
    });
    $(this).addClass('active');
  }
}

function doubleClickIcon() {
  // Action to be taken upon double-clicking icon

  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1) {
    // Open desired page in new tab
    const explorer = $(this).parents('.page-explorer');
    const path = explorer.find('.path').text() +
        $(this).find('figcaption').text();
    const endpoint = location.href + '/get-root-path';
    $.get(endpoint, rootPath => {
      let url = rootPath + path;
      if ($(this).attr('data-username')) {
        let username = $(this).attr('data-username');
        let password = $(this).attr('data-password');
        url = url.replace('://', `://${username}:${password}@`);
      }
      window.open(url, '_blank');
    });    
  } else {
    // Change current directory to folder's one
    const explorer = $(this).parents('.page-explorer');
    const node = explorer.find('.path');
    const folder = node.text() + page + '/';
    changeDir(explorer, folder);
  }
}

$(_ => {
  // Listen to page explorer clicks
  $('.levels').on('click', '.page-explorer figure', clickIcon);
  $('.levels').on('dblclick', '.page-explorer figure', doubleClickIcon);
});
