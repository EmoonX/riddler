$(document).ready(function () {
  // Build dict of (level ID -> list of image URLs)
  imgs = {}
  $("tbody > tr:not(.page-explorer)").each(function (j) {
    console.log($(this))
    console.log($(this).find("var"))
    var level_id = $(this).find("var")[0].textContent
    imgs[level_id] = []
    $(this).find(".level-rating > div > img").each(function (j) {
      imgs[level_id].push($(this).attr("src"))
    });
  });

  $(".level-rating > div > img").hover(function () {
    // Make respective hearts appear "full" when hovering
    var i = $(this).index() - 1
    $(this).parent().children("img").each(function (j) {
      if (j <= i) {
        $(this).attr("src", "/static/icons/heart-full.png")
      } else {
        $(this).attr("src", "/static/icons/heart-empty.png")
      }
    });
  });
  $(".level-rating > div").mouseout(function () {
    // Empty all hearts upon moving mouse away
    var level_id = $(this).parents("tr").find("var")[0].textContent
    $(this).children("img").each(function (j) {
      $(this).attr("src", imgs[level_id][j])
    });
  });
  $(".level-rating > div > img").click(function () {
    // Get level ID and rating info
    var level_id = $(this).parents("tr").find("var")[0].textContent
    var rating = $(this).index()

    // Send an HTTP request by Ajax
    var url = "rate/" + level_id + "/" + rating
    var response = $.ajax({type: "GET", url: url, async: false})
    var aux = response.responseText.split(" ")
    if (aux[0] == "403") {
      // Go back to login page if trying to rate after timeout
      window.location.replace("/login/")
      return
    }

    // Update average and count rating fields
    var average = Number(aux[0])
    var count = aux[1]
    if (average > 0) {
      average = String(Math.round(10 * average))
      average = average[0] + "." + average[1]
    } else {
      average = "--"
    }
    var vars = $(this).parent().children("var")
    vars[0].textContent = average
    vars[1].textContent = "(" + count + ")"

    // Update filled-up hearts
    average = Math.round(2 * average) / 2
    for (var i = 0; i < 5; i++) {
      imgs[level_id][i] = "/static/icons/"
      if ((i+1) <= average) {
        imgs[level_id][i] += "heart-full.png"
      } else if ((i+1) - average == 0.5) {
        imgs[level_id][i] += "heart-half.png"
      } else {
        imgs[level_id][i] += "heart-empty.png"
      }
      $(this).parent().children("img")[i].src = imgs[level_id][i]
    }

    // Update current user's rating
    var rating = aux[2]
    var text = "(rate me!)"
    if (rating != "None") {
      text = "(yours: <var>" + rating + "</var>)"
    }
    $(this).parents("figure").find("figcaption > span")[0].innerHTML = text
  });

  /*-------------------------------------------------------------------------*/

  $(".level-id.unlocked").click(function () {
    // Toggle page explorer
    $(this).toggleClass("active")
    var tr = $(this).parents("tr")
    tr.toggleClass("active")
    tr.next(".page-explorer").toggleClass("active")
    toggle_check(tr.next(".page-explorer"))
  });

  function toggle_check(parent) {
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

  function change_dir(folder, parent, node) {
    // Update directory on field
    node.text("/" + folder + "/")

    // Get JS object data converted from Python dict
    var data = parent.data("folders").replaceAll("'", "\"")
    var folders = $.parseJSON(data)
    data = parent.data("files_count").replaceAll("'", "\"")
    var files_count = $.parseJSON(data)
    data = parent.data("files_total").replaceAll("'", "\"")
    var files_total = $.parseJSON(data)

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

  $(".page-explorer .folder-up").click(function () {
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
});
