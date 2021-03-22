// Build list of permitted host URLs
const hostsURL = 'https://riddler.emoon.dev/get-riddle-hosts';
var riddleHosts = [];
fetch(hostsURL)
  .then(res => {
    if (res.status == 200) {
      console.log('OK!');
    } else {
      console.log(':(');
    }
  })
  .then(error => {
    console.log(error);
  })
;
