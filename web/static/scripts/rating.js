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

async function updateRating() {
  // Update ratings on database and reflect it immediatelly on page

  // Get level name and rating info
  const row = $(this).parents('.row');
  const levelName = row.find('.level-name').text().trim();
  const ratingOld = Number(row.find('figure.rating > figcaption var').text());
  var ratingNew = $(this).index() + 1;

  // Send an HTTP GET request
  await fetch(
    `levels/rate/${levelName}/${ratingNew}`,
    {'method': (ratingNew !== ratingOld) ? 'PUT' : 'DELETE'},
  )

    .then(response => {
      if (response.status === 401) {
        // Go back to login page if trying to rate while not logged in
        console.log('[Rating] Error updating rating for level ${levelName}...')
        location.replace(`/login?redirect_url${location.href}`);
        return;
      }
      return response.text();
    })
    .then(text => {
      // Update average and count rating fields
      const values = text.split(' ');
      const count = values[1];
      var average = Number(values[0]);
      average = String(Math.round(10 * average));
      average = average[0] + '.' + average[1];
      $(this).parents('.rating').find('.average').text(average);
      $(this).parents('.rating').find('.count').text('(' + count + ')');

      // Show or hide ratings depending if player rated or not
      ratingNew = values[2];
      if (ratingNew != 'None') {
        $(this).parents('.hearts').removeClass('unrated');
      } else {
        $(this).parents('.hearts').addClass('unrated');
        $(this).parents('.rating').find('.average').text('??');
      }  
      // Update ratings dictionary
      average = Math.round(2 * average) / 2;
      ratings[levelName] = 0;

      // Updated filled-up hearts, if rated
      if (ratingNew != 'None') {
        const dir = '/static/icons/';
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
      }
      // Update current user's rating
      var html = '(rate me!)';
      if (ratingNew != 'None') {
        html = `(yours: <var>${ratingNew}</var>)`;
      }
      const span = $(this).parents('.rating').find('figcaption > span');
      span.html(html);

      console.log(
        `[Rating] Level ${levelName} has been given ${ratingNew} heart(s)!`
      );
    });
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
