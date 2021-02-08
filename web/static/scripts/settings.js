$(document).ready(function () {
  function displayFlag() {
    // Alter flag image and caption on selected option changed
    var path = "/static/flags/" + $("select option:selected").val() + ".png";
    var text = $("select option:selected").text();
    $("figure > img").attr("src", path);
    $("figcaption").text(text);
  }
  $("select").change(displayFlag);
  if ($("#selected")) {
    $("select").val($("#selected").val()).change();
  }
  displayFlag();;
});
