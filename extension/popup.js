import {  
  changeLevel,
  changeLevelSet,
  clickFile,
  doubleClickFile,
  updatePopupNavigation,
} from './explorer.js';

import {
  SERVER_HOST,
  updateState,
} from './riddle.js';

import { createTab } from './tabs.js';

// Get message data from background.js
const port = chrome.runtime.connect({ name: 'popup' });

port.onMessage.addListener(async data => {
  console.log('Received data from background.js...');  
  $('#loading').toggle(false);

  const alias = data.currentRiddle;
  if (! alias) {
    // Display buttons menu when not logged in
    $('#buttons').toggle(true);
    return;
  }

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
  if (level) {
    updatePopupNavigation(riddle, level);
  }
});

$(() => {
  // Set explorer events
  $('#level').on('click', '#previous-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#next-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#previous-level:not(.disabled)', changeLevel);
  $('#level').on('click', '#next-level:not(.disabled)', changeLevel);
  $('.page-explorer').on('click', 'figure.file', clickFile);
  $('.page-explorer').on('dblclick', 'figure.file', doubleClickFile);

  // Set button click link events
  $('button').on('click', function () {
    createTab(`${SERVER_HOST}/${this.name}`);
  });
});
