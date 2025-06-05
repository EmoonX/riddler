import {  
  changeLevel,
  changeLevelSet,
  clickFile,
  doubleClickFile,
  insertFiles,
} from './explorer.js';

import {
  SERVER_HOST,
  updateState,
} from './riddle.js';

$(() => {
  // Set explorer events
  $('#level').on('click', '#previous-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#next-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#previous-level:not(.disabled)', changeLevel);
  $('#level').on('click', '#next-level:not(.disabled)', changeLevel);
  $('.page-explorer').on('click', 'figure.file', clickFile);
  $('.page-explorer').on('dblclick', 'figure.file', doubleClickFile);
  console.log('aaaaaaaaaa')

  // Set button click events
  $('[name=login]').on('click', () => {
    window.open(`${SERVER_HOST}/login`, '_blank');
  });

  // Get message data from background.js
  let port = chrome.runtime.connect(
    { name: 'popup.js' }
  );
  port.onMessage.addListener(data => {
    console.log('Received data from background.js...');
    const alias = data.currentRiddle;
    if (alias) {
      // Update explorer.js members
      const riddles = data.riddles;
      updateState(riddles, alias);

      // Display logged in riddle data
      $('#currently-playing').toggle(true);
      $('#buttons').remove();

      // Show current riddle info in extension's popup
      const riddle = riddles[alias];
      const setName = riddle.lastVisitedSet;
      const levelName = riddle.lastVisitedLevel;
      const level = riddle.levels[setName][levelName];
      const explorerURL = `${SERVER_HOST}/${alias}/levels`;
      $('#riddle > .icons img.current').attr('src', riddle.iconUrl);
      $('#riddle > .full-name').text(riddle.fullName);
      $('#riddle a').attr('href', explorerURL);
      $('#level > var#current-level').text(levelName);
      console.log(level);
      if (level.previousSet) {
        console.log($('#level #previous-set'));
        $('#level #previous-set').removeClass('disabled');
      }
      if (level.previousLevel) {
        $('#level #previous-level').removeClass('disabled');
      }
      if (level.nextLevel) {
        $('#level #next-level').removeClass('disabled');
      }
      if (level.nextSet) {
        $('#level #next-set').removeClass('disabled');
      }
      // Build HTML for list of files of currently visited level
      insertFiles($('.page-explorer'), level.pages['/'], 0, '');
    }
  });
});
