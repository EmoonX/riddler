// Single port for all content scripts
const port = chrome.runtime.connect({ name: 'content' });
