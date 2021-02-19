const cheevoRankColors = {
  'C': 'firebrick',
  'B': 'lightcyan',
  'A': 'gold',
  'S': 'darkturquoise'
};

function changeThumb() {
  // Load image from file browser
  if (this.files && this.files[0]) {
    // Get elements from index
    const index = this.id.substr(0, this.id.search('-'));
    const thumb = document.getElementById(index + '-thumb');
    const data = document.getElementsByName(index + '-imgdata')[0];

    // Read image data as base64 string and load it
    const reader = new FileReader();
    reader.onload = (e => {
      thumb.setAttribute('src', e.target.result);
      data.setAttribute('value', e.target.result);
    });
    reader.readAsDataURL(this.files[0]);

    // Save also image name on hidden input
    const image = document.getElementsByName(index + '-image')[0];
    image.setAttribute('value', this.files[0].name);
  }
}

function changeCheevoRank() {
  if (!this.checked) {
    return;
  }
  console.log(this.value)
  const color = cheevoRankColors[this.value]
  const index = this.name.substr(0, this.name.search('-'));
  const thumb = document.getElementById(index + '-thumb');
  thumb.style.borderColor = color
  thumb.style.boxShadow = "0 0 0.8em " + color
}

window.onload = (_ => {
  // Listen to thumb changes 
  const thumbInputs = document.getElementsByClassName('thumb-input');
  Array.from(thumbInputs).forEach(input => {
    input.addEventListener('change', changeThumb);
  });
  // Listen to rank radio changes
  const rankRadios = document.getElementsByClassName('rank-radio');
  Array.from(rankRadios).forEach(radio => {
    radio.addEventListener('click', changeCheevoRank);
  });
});
