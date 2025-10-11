const port = chrome.runtime.connect({ name: 'credentials.js' });

/** One-shot listener for prompting credentials. */
const credentialsListener = (data => {
  console.log('Received data from background.js...');
  port.onMessage.removeListener(credentialsListener);
  if (! data.realm) {
    // Not from an auth request; nothing to show
    return;
  }

  // Prompt user with auth box
  const box = $($.parseHTML(data.boxHTML));
  const credentials = data.unlockedCredentials;
  box.find('.realm').text(`"${data.realm}"`);
  if (credentials) {
    box.find('input[name="username"]').attr('value', credentials.username);
    box.find('input[name="password"]').attr('value', credentials.password);
  }
  $('head').append(`<style>${data.boxCSS}</style>`);
  $('body').append(box[0].outerHTML);
  $('input[name="username"]').trigger('focus').attr;
  $('form.credentials').on('submit', embedCredentials);

  // Retrieve un/pw from last immediate attempt as placeholders (if any)
  const lastCredentials = JSON.parse(sessionStorage.getItem("lastCredentials"));
  const parsedUrl = new URL(window.location.href);
  parsedUrl.username = parsedUrl.password = '';
  if (lastCredentials?.url === parsedUrl.toString()) {
    $('input[name="username"]').attr('placeholder', lastCredentials.username);
    $('input[name="password"]').attr('placeholder', lastCredentials.password);
  }
  sessionStorage.setItem('lastCredentials', null);
});
port.onMessage.addListener(credentialsListener);

/** Embed credentials (`un:pw@...`) into URL, replacing current page. */
function embedCredentials(e) {
  e.preventDefault(); // block GET-submit
  const parsedUrl = new URL(window.location.href);
  parsedUrl.username = parsedUrl.password = '';
  const baseUrl = parsedUrl.toString();
  parsedUrl.username = $('input[name="username"]').val();
  parsedUrl.password = $('input[name="password"]').val(); 
  sessionStorage.setItem('lastCredentials', JSON.stringify({
    url: baseUrl,
    username: parsedUrl.username,
    password: parsedUrl.password,
  }));
  window.location.replace(parsedUrl.toString());
}
