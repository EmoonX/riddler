import {
  setPages, toggleExplorer, folderUp
}
  from './explorer.js';

function toggleCheck(parent) {
  // Display check mark if all files found
  var comp = parent.find("nav > .content > .completion")
  var vars = comp.find("var")
  var check = comp.find(".check")
  var count = vars[0].textContent
  var total = vars[1].textContent
  if (count != "--" && count == total) {
    check.toggle(true);
  } else {
    check.toggle(false);
  }
}

function clickIcon() {

}

function doubleClickIcon() {
  
}

$(_ => {
  // Get JS object data converted from Python dict
  const aux = location.href.split('/');
  aux.push('get-pages');
  const url = aux.join('/');
  $.get(url, data => {
    setPages(data);    
  });
  // Listen to page explorer clicks
  $('.levels').on('click', '.page-explorer figure', clickIcon);
  $('.levels').on('dblclick', '.page-explorer figure', doubleClickIcon);
});
