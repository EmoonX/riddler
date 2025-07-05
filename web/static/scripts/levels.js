import {
  changeDir
}
  from './explorer.js';

function clickIcon() {
  // Select icon if not a folder one
  if ($(this).attr('class').split(' ').indexOf('folder') === -1) {
    const figures = $(this).parents('.files').find('figure');
    figures.each(function () {
      $(this).removeClass('active');
    });
    $(this).addClass('active');
  }
}

function doubleClickIcon() {
  // Action to be taken upon double-clicking icon
  const explorer = $(this).parents('.page-explorer');
  const currentFolder = explorer.find('.path').text();
  const basename = $(this).find('figcaption').text();
  const path = currentFolder.replace(/([^/])$/, '$1/') + basename;
  if ($(this).attr('class').split(' ').indexOf('folder') !== -1) {
    // Change current directory to folder's one
    changeDir(explorer, path);
  } else {
    // Open desired page in new tab
    const endpoint = location.href + '/get-root-path';
    $.get(endpoint, rootPath => {
      const url = rootPath + path;
      // if ($(this).attr('data-username')) {
      //   let username = $(this).attr('data-username');
      //   let password = $(this).attr('data-password');
      //   url = url.replace('://', `://${username}:${password}@`);
      // }
      // window.open(url, '_blank');
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noreferrer";
      a.click();
    });    
  }
}

$(_ => {
  // Listen to page explorer clicks
  $('.levels').on('click', '.page-explorer figure', clickIcon);
  $('.levels').on('dblclick', '.page-explorer figure', doubleClickIcon);
});
