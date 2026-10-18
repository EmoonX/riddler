// Single port for all content scripts
const port = browser.runtime.connect({ name: 'content' });
