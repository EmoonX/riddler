function saveOptions(e) {
  // Save extension settings from form on browser
  e.preventDefault();
  chrome.storage.local.set({
    'player_id': document.querySelector('input[name="player_id"]').value
  });
}
  
function restoreOptions() {
  // Restore extension setting to form fields
  chrome.storage.local.get('player_id', function (result) {
    document.querySelector('input[name="player_id"]').value = result.player_id;
  });
}

// Add functions to event both on page load and form submit
document.querySelector('form').addEventListener('submit', saveOptions);
document.addEventListener('DOMContentLoaded', restoreOptions);
  