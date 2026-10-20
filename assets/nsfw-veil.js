/* Reveal a veiled sensitive image or video on click or tap, and veil it again
   on the next tap. One delegated capture handler, so a veil built later by page
   script (the RobotMaxx catalogue card) behaves exactly like one the server
   rendered. The veil is a real button, so Enter and Space already fire a click. */
(function () {
  'use strict';

  document.addEventListener('click', function (event) {
    var target = event.target;
    var veil = target && target.closest ? target.closest('.nsfw-veil') : null;
    if (!veil) return;
    var frame = veil.closest('.nsfw-host');
    if (!frame) return;
    // Capture phase: the veil may sit inside a link, so cancel that first.
    event.preventDefault();
    event.stopPropagation();
    frame.classList.toggle('revealed');
  }, true);
})();
