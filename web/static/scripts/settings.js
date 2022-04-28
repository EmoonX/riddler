$(_ => {
  $('select').on('change', _ => {
    // Alter flag image and caption on selected option changed
    const country = $('select option:selected').val();
    const path = `/static/flags/${country}.png`;
    const text = $('select option:selected').text();
    $('figure.flag > img').attr('src', path);
    $('figure.flag > figcaption').text(text);
  });
  if ($('#selected')) {
    const country = $('#selected').val();
    $('select').val(country).trigger('change');
  }
  displayFlag();;
});
