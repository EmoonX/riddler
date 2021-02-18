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

window.onload = (_ => {
  const thumb_inputs = document.getElementsByClassName('thumb-input');
  Array.from(thumb_inputs).forEach(input => {
    input.addEventListener('change', changeThumb);
  });
});
