// Outline colors for cheevos based on rank
const cheevoRankColors = {
  'C': 'firebrick',
  'B': 'lightcyan',
  'A': 'gold',
  'S': 'darkturquoise'
};

function changeThumb() {
  // Load image from file browser
  if (this.files && this.files[0]) {
    // Get elements from index
    const index = this.id.substr(0, this.id.search('-'));
    const thumb = $('#' + index + '-thumb');
    const data = $('[name="' + index + '-imgdata"]');

    // Read image data as base64 string and load it
    const reader = new FileReader();
    reader.onload = (e => {
      thumb.attr('src', e.target.result);
      data.attr('value', e.target.result);
    });
    reader.readAsDataURL(this.files[0]);

    // Save also image name on hidden input
    const image = $('[name="' + index + '-image"]');
    image.attr('value', this.files[0].name);
  }
}

function changeCheevoRank() {
  // Update cheevo thumb outline color on rank change
  const rank = this.value.toLowerCase();
  const index = this.name.substr(0, this.name.search('-'));
  const thumb = $('#' + index + '-thumb');
  thumb.removeClass();
  thumb.addClass(['cheevo-thumb', rank + '-rank']);
}

function addCheevoRow() {
  // Add new cheevo row

  // Disable Add button for the time being
  $('button[name="add-cheevo"]').prop('disabled', true);

  // Get new index from current number of rows
  const index = $('.row').length + 1;

  $.get('/admin/cheevo-row/', function(html) {
    // Get HTML from rendered template and append to section
    html = html.replaceAll('[[ index ]]', index);
    div = $.parseHTML(html);
    $('.admin.new').append(div);

    // Add listeners to new fields
    console.log('#' + index + '-input')
    $('.admin.new').on('change', '#' + index + '-input', changeThumb);
    $('.admin.new').on('click', '.rank-radio', changeCheevoRank);
  }, 'html');
}

$(_ => {
  // Dinamically create css classes for thumb outline colors
  css = '<style type="text/css">';
  $.each(cheevoRankColors, function(rank, color) {
    css += '.' + rank.toLowerCase() + '-rank { ';
    css += 'border-color: ' + color + '; ';
    css += 'box-shadow: 0 0 0.8em ' + color + '; } ';
  });
  css += '</style>';
  $('head').append(css);

  // Listen to thumb changes
  $('.thumb-input').each(function () {
    $(this).on('change', changeThumb);
  });
  // Listen to rank radio changes
  $('.rank-radio').each(function () {
    $(this).on('click', changeCheevoRank);
  });
  // Listen to Add button click
  $('button[name="add-cheevo"]').on('click', addCheevoRow);
});
