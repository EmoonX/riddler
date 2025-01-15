let port = chrome.runtime.connect(
{ name: 'Communication with background.js' }
);
port.onMessage.addListener(data => {
  console.log('Connected to credentials.js...')
  alert(data.greeting);
});

