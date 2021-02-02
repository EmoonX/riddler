function saveOptions(e) {
  // Save extension settings from form on browser
  e.preventDefault();
  browser.storage.local.set({
    player_id: document.querySelector('input[name="player_id"]').value
  });
}
  
function restoreOptions() {
  // Restore extension setting to form fields
  function setCurrentChoice(result) {
    document.querySelector('input[name="player_id"]').value = result.player_id;
  }
  function onError(error) {
    console.log(`Error: ${error}`);
  }
  let getting = browser.storage.local.get('player_id');
  getting.then(setCurrentChoice, onError);
}

// Add functions to event both on page load and form submit
document.querySelector('form').addEventListener('submit', saveOptions);
document.addEventListener('DOMContentLoaded', restoreOptions);
  