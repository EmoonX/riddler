function changeThumb() {
  // Load image from file browser
  if (this.files && this.files[0]) {
    const index = this.id.substr(0, this.id.search('-'));
    const thumb = document.getElementById(index + '-thumb');
    const reader = new FileReader();
    reader.onload = (e => {
      thumb.setAttribute('src', e.target.result);
    });
    reader.readAsDataURL(this.files[0]);
  }
}

window.onload = (_ => {
  const thumb_inputs = document.getElementsByClassName('thumb-input');
  Array.from(thumb_inputs).forEach(input => {
    input.addEventListener('change', changeThumb);
  });
});
