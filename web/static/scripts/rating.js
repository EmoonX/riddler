// Dictionary of levels' ratings
const ratings = {};

function heartMouseEnter() {
  // Make respective hearts appear "full" when hovering
  const i = $(this).index();
  $(this).parent().children('img').each(function (j) {
    if (j <= i) {
      $(this).attr('src', '/static/icons/heart-full.png');
    } else {
      $(this).attr('src', '/static/icons/heart-empty.png');
    }
  });
}

function heartsMouseLeave() {
  // Restore all hearts to original upon moving mouse away
  const levelName = $(this).parents('.row').find('.name').text();
  const dir = '/static/icons/'
  var rating = ratings[levelName];
  $(this).children('img').each(function (j) {
    if (rating >= 1) {
      $(this).attr('src', dir + 'heart-full.png');
      rating -= 1;
    } else if (rating == 0.5) {
      $(this).attr('src', dir + 'heart-half.png');
      rating -= 0.5;
    } else {
      $(this).attr('src', dir + 'heart-empty.png');
    }
  });
};

function updateRating() {
  // Update ratings on database and reflect it immediatelly on page

  // Get level name and rating info
  const levelName = $(this).parents('.row').find('.name').text();
  const prevRating = $(this).index() + 1;

  // Send an HTTP GET request
  const url = `levels/rate/${levelName}/${prevRating}`;
  $.get(url, text => {  
    // Update average and count rating fields
    const values = text.split(' ');
    const count = values[1];
    var average = Number(values[0]);
    if (average > 0) {
      average = String(Math.round(10 * average));
      average = average[0] + '.' + average[1];
    } else {
      average = '--';
    }
    $(this).parents('.rating').find('.average').text(average);
    $(this).parents('.rating').find('.count').text('(' + count + ')');
  
    // Update ratings dictionary and filled-up hearts
    average = Math.round(2 * average) / 2;
    ratings[levelName] = 0;
    const dir = '/static/icons/'
    for (var i = 0; i < 5; i++) {
      var filename = dir;
      if ((i+1) <= average) {
        ratings[levelName] += 1.0;
        filename += 'heart-full.png';
      } else if ((i+1) - average == 0.5) {
        ratings[levelName] += 0.5;
        filename += 'heart-half.png';
      } else {
        filename += 'heart-empty.png';
      }
      const img = $(this).parent().children('img.heart').eq(i);
      img.attr('src', filename);
    }
  
    // Update current user's rating
    const rating = values[2];
    var html = '(rate me!)';
    if (rating != 'None') {
      html = `(yours: <var>${rating}</var>)`;
    }
    const span = $(this).parents('.rating').find('figcaption > span');
    span.html(html);

    console.log(`[Rating] Level ${levelName} `
          + `has been given ${rating} hearts!`);
  })
    .fail(response => {
      console.log('[Rating] Error updating rating for level ${levelName}...')
      if (response.status == 401) {
        // Go back to login page if trying to rate while not logged in
        location.replace('/login');
        return;
      }
    }
  );
};

$(_ => {
  // Build dictionary of level ratings
  $('.row').each(function (j) {
    const levelName = $(this).find('.name').text();
    ratings[levelName] = 0;
    $(this).find('.rating img.heart').each(function () {
      const src = $(this).attr('src');
      const filename = src.substr(src.lastIndexOf('/') + 1)
      switch (filename) {
        case 'heart-full.png':
          ratings[levelName] += 1.0;
          break;
        case 'heart-half.png':
          ratings[levelName] += 0.5;
          break;
      }
      if (filename == 'heart-empty.png') {
        // Break out
        return true;
      }
    });
  });

  // Register events
  $('.list.levels .rating img.heart').on('mouseenter', heartMouseEnter);
  $('.list.levels .rating .hearts').on('mouseleave', heartsMouseLeave);
  $('.list.levels .rating img.heart').on('click', updateRating);
});
