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

$(_ => {
  const aux = location.href.split('/');
  aux.push('get-pages');
  const url = aux.join('/');
  $.get(url, data => {
    pages = JSON.parse(data);
    console.log(pages)
  });
});
