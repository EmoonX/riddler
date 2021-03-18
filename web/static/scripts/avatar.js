$(document).ready(function () {
  $(".avatar-small").each(function () {
    // Register initial PNG image path
    var png_path = $(this).attr("src")
    $(this).attr("data-png", png_path)
    var gif_path = $(this).data("gif")
    if (gif_path.substring(0, 4) != "None") {
      $('<img>').attr('src', gif_path).appendTo('body').hide()
    }
  });

  $(".avatar-small").hover(function () {
    // Change image to animated GIF, if any
    var gif_path = $(this).data("gif")
    if (gif_path.substring(0, 4) != "None") {
      $(this).attr("src", gif_path)
    }
  }, function () {
    // Change image back to PNG one
    var png_path = $(this).data("png")
    $(this).attr("src", png_path)
  });
});
