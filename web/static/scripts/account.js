$(document).ready(function () {
  function validatePassword() {
    // Pop up message if "password" and "confirm" input fields are different
    var msg = "";
    if ($("password[name='new_password']").val() !=
        $("password[name='confirm']").val()) {
      msg = "Passwords don't match!";
    }
    $("password[name='confirm']")[0].setCustomValidity(msg);
  }
  // Check validity every time a field is changed
  $("password[name='new_password']").change(validatePassword);
  $("password[name='confirm']").change(validatePassword);

  function validateDiscord() {
    var handle = $("input[name='discord_tag']");
    var patt = /^.{2,32}#\d{4}$/
    var msg = "";
    if (handle.val() && !patt.test(handle.val())) {
      msg = "Invalid DiscordTag format! " +
          "Valid example: B0b 7h3 H4x0r#1337"
    }
    handle[0].setCustomValidity(msg);
  }
  $("input[name='discord_tag']").change(validateDiscord);

  function displayFlag() {
    // Alter flag image and caption on selected option changed
    var path = "/cipher/flags/" + $("select option:selected").val() + ".png";
    var text = $("select option:selected").text();
    $("figure > img").attr("src", path);
    $("figcaption").text(text);
  }
  $("select").change(displayFlag)

  function displayAvatar() {
    // Load image from file browser
    if (this.files && this.files[0]) {
      var reader = new FileReader();
      reader.onload = function(e) {
        $(".avatar").attr("src", e.target.result);
        $("input[type='hidden']").val(e.target.result)
      }
      reader.readAsDataURL(this.files[0]);
    }
  }
  $("input[type='file']").change(displayAvatar);

  $("select").val($("#selected").val()).change()
  displayFlag();
});
