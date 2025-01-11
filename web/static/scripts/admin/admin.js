import {
  pages, getFolderEntry, changeDir
}
  from '../explorer.js';

/** Outline colors for cheevos based on rank. */
const cheevoRankColors = {
  'C': 'firebrick',
  'B': 'lightcyan',
  'A': 'gold',
  'S': 'darkturquoise'
};

/** Dictionary of sets of current added pages for each level.  */
var addedPages = {};

/** Set of removed (unhighlighted) level pages.  */
var removedPages = new Set();

/** Syncs discord name with level name on the latter change. */
function updateDiscordName() {
  const row = $(this).parents('.row');
  const levelName = $(this).val();
  const discordName = row.find('.discord-name');
  discordName.val(levelName);
}

function changeThumb() {
  // Load image from file browser
  if (this.files && this.files[0]) {
    // Get elements from index
    const index = this.id.substr(0, this.id.search('-'));
    const thumb = $(`#${index}-thumb`);
    const data = $(`[name="${index}-imgdata"]`);

    // Read image data as base64 string and load it
    const reader = new FileReader();
    reader.onload = (e => {
      thumb.attr('src', e.target.result);
      data.attr('value', e.target.result);
    });
    reader.readAsDataURL(this.files[0]);

    // Save also image name on hidden input
    const image = $(`[name="${index}-image"]`);
    image.attr('value', this.files[0].name);
  }
}

function changeCheevoRank() {
  // Update cheevo thumb outline color on rank change
  const rank = this.value.toLowerCase();
  const index = this.name.substr(0, this.name.search('-'));
  const thumb = $(`#${index}-thumb`);
  thumb.removeClass();
  thumb.addClass([rank + '-rank', 'thumb', 'cheevo']);
}

function toggleFile(file, highlighted) {
  // Mark/unmark file/page as belonging to current level

  // Do nothing if state isn't going to be changed
  if (file.hasClass('current') == highlighted) {
    return;
  }
  // Check if page is indeed a file; ignore folders
  const page = file.find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j == -1) {
    return;
  }
  // Change file state
  file.toggleClass('current');
  
  // Get level and folder info
  const explorer = file.parents('.page-explorer');
  const index = explorer.attr('id');
  const levelName = explorer.prev().find('.key > input').val();
  const folderPath = explorer.find('.path').text();
  const folder = getFolderEntry(folderPath, '', true)
  const row = folder['children'][page];

  console.log(file.hasClass('current'))
  if (file.hasClass('current')) {
    // File was highlighted
    const frontPath = explorer.prev().find('.front-path');
    if (! frontPath.val()) {
      // Automatically fill front path on first highlight
      frontPath.val(row['path']);
    }
    if (! addedPages[levelName]) {
      addedPages[levelName] = new Set();
    }
    row['level_name'] = levelName;
    removedPages.delete(row['path'])
    addedPages[levelName].add(row['path']);
    const addedJSON = JSON.stringify([...addedPages[levelName]]);
    $(`input[name="${index}-added-pages"]`).val(addedJSON);
  } else {
    // File was unhighlighted
    row['level_name'] = 'NULL';
    if (addedPages[levelName]) {
      addedPages[levelName].delete(row['path']);
    }
    removedPages.add(row['path'])
    const removedJSON = JSON.stringify([...removedPages]);
  $(`input[name="removed-pages"]`).val(removedJSON);
  }

  // Recursively mark/unmark parent folders for highlighting
  const segments = folderPath.split('/').slice(1, -1);
  var parent = pages['/'];
  segments.forEach(seg => {
    const folder = parent['children'][seg];
    if (file.hasClass('current')) {
      if (! folder['levels'][levelName]) {
        folder['levels'][levelName] = 0;
      }
      folder['levels'][levelName] += 1;
    } else {
      folder['levels'][levelName] -= 1;
    }
    parent = folder;
  });
}

function clickIcon() {
  // Change file highlighted state
  const newState = ! $(this).hasClass('current');
  toggleFile($(this), newState);
}

function doubleClickIcon() {
  // Action to be taken upon double-clicking icon
  const explorer = $(this).parents('.page-explorer');
  const page = $(this).find('figcaption').text();
  const j = page.lastIndexOf('.');
  if (j != -1 && j != page.length - 1) {
    // Register file path as level front's one
    if (! $(this).hasClass('current')) {
      // Highlight file beforehand if necessary
      toggleFile($(this), true);
    }
    const frontPath = explorer.prev().find('.front-path')
    const path = explorer.find('.path').text() +
        $(this).find('figcaption').text();
    frontPath.val(path);
  } else {
    // Change current directory to folder's one
    const node = explorer.find('.path');
    const folder = node.text() + page + '/';
    changeDir(explorer, folder, true);
  }
}

function validateRows() {
  // Enable/disable Add button whether or not
  // all new row fields have been entered

  // Check text and image input fields
  const fields = $(this).parents('.row').find('input');
  var ok = true;
  fields.each(function () {
    if ((! $(this).val()) && $(this).attr('type') != 'hidden') {
      ok = false;
      return;
    }
  });
  // Also check if a radio button has been checked
  const radios = fields.filter(':radio');
  if (! radios.is(':checked')) {
    ok = false;
  }
  // Enable/disable Add button accordingly
  $('button.add').prop('disabled', !ok);
}

function addRow(event) {
  // Add new level or cheevo row

  // Disable Add button for the time being
  const type = event.data.type;
  $(`button.add`).prop('disabled', true);

  // Get new index from current number of rows
  var index = String($('.list:not(.secret) .row').length + 1);
  if (type == 'secret-level') {
    index = 's' + String($('.list.secret .row').length + 1);
  }  
  // Send GET request for a new row
  const url = (type != 'secret-level') ? `${type}-row` : 'level-row';
  const data = {'index': index};
  $.get(url, data, function(html) {
    // Get HTML from rendered template and append to section
    const row = $.parseHTML(html);
    const list = (type != 'secret-level') ?
      $('.new:not(.secret)') : $('.secret.new');
    list.show();
    list.append(row);

    // Insert handy values from previous row (if any)
    if (index != '1') {
      const prevIndex =
        (index[0] != 's') ?
        (parseInt(index) - 1).toString() :
        ('s' + (parseInt(index.substring(1)) - 1).toString());
      const prevName = $(`[name=${prevIndex}-name]`).val();
      const prevCategory = $(`[name=${prevIndex}-discord_category]`).val();
      $(`[name=${index}-requirements]`).val(prevName);
      $(`[name=${index}-discord_category]`).val(prevCategory);
    }
    // Add listeners to new fields
    list.on('change', `.name input`, updateDiscordName);
    list.on('change', `#${index}-input`, changeThumb);
    if (type == 'cheevo') {
      list.on('click', '.rank-radio', changeCheevoRank);
    }
    // Enable added row validation
    list.on('change', '.row:last input', validateRows);
  }, 'html');
}

$(_ => {
  // Dinamically create CSS classes for thumb outline colors
  var css = '<style type="text/css">';
  $.each(cheevoRankColors, (rank, color) => {
    css += '.' + rank.toLowerCase() + '-rank { ';
    css += `border-color: ${color} !important; `;
    css += `box-shadow: 0 0 0.8em ${color} !important; } `;
  });
  css += '</style>';
  $('head').append(css);

  // Listen to level name changes
  $('.row .name input').on('change', updateDiscordName);

  // Listen to thumb changes
  $('.thumb-input').each(_ => {
    $(this).on('change', changeThumb);
  });
  // Listen to rank radio changes
  $('.rank-radio').each(_ => {
    $(this).on('click', changeCheevoRank);
  });
  // Listen to page explorer clicks
  $('.levels').on('click', '.page-explorer figure', clickIcon);
  $('.levels').on('dblclick', '.page-explorer figure', doubleClickIcon);

  // Listen to Add level OR Add cheevo click
  $('button[name="add-level"]').on('click', {type: 'level'}, addRow);
  $('button[name="add-secret-level"]').on('click', {type: 'secret-level'}, addRow);
  $('button[name="add-cheevo"]').on('click', {type: 'cheevo'}, addRow);
});
