import { retrieveWithCache } from './cache.js';

import {  
  changeLevel,
  changeLevelSet,
  clickFile,
  doubleClickFile,
  getLevelImageBlob,
  insertFiles,
} from './explorer.js';

import {
  getSimpleRootPath,
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
      $('header').toggle(true);
      $('#level').toggle(true);
      $('.page-explorer').toggle(true);
      $('#buttons').remove();

      // Show current riddle info in extension's popup
      const riddle = riddles[alias];
      const explorerURL = `${SERVER_HOST}/${alias}/levels`;
      $('#riddle img.current').attr('src', riddle.iconUrl);
      $('#riddle .full-name').text(riddle.fullName);
      $('#riddle a').attr('href', explorerURL);
      
      const level = riddle.levels[riddle.lastVisitedLevel];
      if (! level) {
        return;
      }

      // Show current level name/navigation
      const rootPath = getSimpleRootPath(riddle);
      $('#level #set-name').text(level.setName);
      $('#level #level-name a').text(level.name);
      $('#level #level-name a').attr('href', `${rootPath}${level.frontPath}`);
      getLevelImageBlob(riddle.alias, level).then(imageBlob => {
        $('#level img#level-image').attr('src', imageBlob);
      });
      if (level.previous) {
        $('#level #previous-set').removeClass('disabled');
        $('#level #previous-level').removeClass('disabled');
      }
      if (level.next) {
        $('#level #next-level').removeClass('disabled');
        $('#level #next-set').removeClass('disabled');
      }      

      // Build HTML for list of files of currently visited level
      insertFiles($('.page-explorer'), level.pages['/'], 0, '');
    }
  });
});
