$(_ => {
  $(".menu").on('click', function () {
    // Toggle page explorer
    const row = $(this).parents(".row");
    const explorer = row.next(".page-explorer");
    row.toggleClass("active");
    explorer.toggleClass("active");

    if (explorer.hasClass('active')) {
      console.log($(this).find('figure'));
      explorer.find('figure').each(function (index) {
        const t = 100 * index;
        setTimeout(_ => {
          console.log($(this));
          $(this).addClass('show');
        }, t);
      });
    } else {
      explorer.find('figure').removeClass('show');
    }
  });

  function change_dir(folder, parent, node) {
    // Update directory on field
    node.text("/" + folder + "/")

    // Get JS object data converted from Python dict
    var data = parent.data("folders").replaceAll("'", "\"")
    var folders = JSON.parse(data)
    data = parent.data("files_count").replaceAll("'", "\"")
    var files_count = JSON.parse(data)
    data = parent.data("files_total").replaceAll("'", "\"")
    var files_total = JSON.parse(data)

    // Erase previous files and add new ones
    var div = parent.find("td > div")
    div.empty()
    folders[folder].forEach(function (page) {
      var name = "folder"
      var j = page.lastIndexOf(".")
      if (j != -1) {
        name = page.substr(j + 1)
      }
      var img = '<img src="/static/icons/' + name + '.png">'
      var fc = '<figcaption>' + page + '</figcaption>'
      var figure = '<figure>' + img + fc + '</figure>'
      div.append(figure)
    });

    // Update folder's files count and total
    var count = files_count[folder]
    var total = files_total[folder]
    var comp = parent.find("nav > .content > .completion")
    var vars = comp.find("var")
    vars[0].textContent = count ? count : "--";
    vars[1].textContent = total ? total : "--";
    toggle_check(parent)
  }

  $(".page-explorer .folder-up").on('click', function () {
    // Change current directory to one up
    var parent = $(this).parents(".page-explorer")
    var node = parent.find("nav > .content > .path")
    if (node.text() == "/cipher/" || node.text() == "/riddle/") {
      // Nothing to do if already on top folder
      return
    }
    var re = /\/\w+\/$/g
    var folder = node.text().replace(re, "").substring(1)
    change_dir(folder, parent, node)
  });

  $(".page-explorer").on("click", "figure", function () {
    // Make clicked file/page "active" and all others inactive
    $(".page-explorer figure").each(function () {
      $(this).removeClass("active")
    });
    $(this).addClass("active")
  });
  $(".page-explorer").on("dblclick", "figure", function () {
    // Action to be taken upon double-clicking icon
    var page = $(this).find("figcaption").text()
    var j = page.lastIndexOf(".")
    if (j != -1) {
      // Open desired page in new tab
      var parent = $(this).parents(".page-explorer")
      var path = parent.find("nav > .content > .path")[0].textContent +
          $(this).find("figcaption")[0].textContent
      var url = "http://rnsriddle.com" + path
      window.open(url, "_blank")
    } else {
      // Change current directory to folder's one
      var parent = $(this).parents(".page-explorer")
      var node = parent.find("nav > .content > .path")
      var folder = node.text().substring(1) + page
      change_dir(folder, parent, node)
    }
  });

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
  