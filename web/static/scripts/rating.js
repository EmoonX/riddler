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
  const rating = $(this).index() + 1;

  // Send an HTTP GET request
  const url = `rate/${levelName}/${rating}`;
  const response = $.get(url);
  console.log(response)
  return
  const aux = response.responseText.split(' ')
  if (aux[0] == '403') {
    // Go back to login page if trying to rate after timeout
    location.replace('/login/')
    return
  }

  // Update average and count rating fields
  var average = Number(aux[0])
  var count = aux[1]
  if (average > 0) {
    average = String(Math.round(10 * average))
    average = average[0] + '.' + average[1]
  } else {
    average = '--'
  }
  var vars = $(this).parent().children('var')
  vars[0].textContent = average
  vars[1].textContent = '(' + count + ')'

  // Update filled-up hearts
  average = Math.round(2 * average) / 2
  for (var i = 0; i < 5; i++) {
    imgs[level_name][i] = '/static/icons/'
    if ((i+1) <= average) {
      imgs[level_name][i] += 'heart-full.png'
    } else if ((i+1) - average == 0.5) {
      imgs[level_name][i] += 'heart-half.png'
    } else {
      imgs[level_name][i] += 'heart-empty.png'
    }
    $(this).parent().children('img')[i].src = imgs[level_name][i]
  }

  // Update current user's rating
  // var rating = aux[2]
  // var text = '(rate me!)'
  // if (rating != 'None') {
  //   text = `(yours: <var>${rating}</var>)`
  // }
  // $(this).parents('figure').find('figcaption > span')[0].innerHTML = text
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
          ratings[levelName] += 1;
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
