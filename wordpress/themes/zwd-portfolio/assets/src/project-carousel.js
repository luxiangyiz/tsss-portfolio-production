/**
 * Project card infinite carousel.
 *
 * Duplicates the project card set to create a seamless horizontal loop.
 * Only runs on the project archive page (`.post-type-archive-project`).
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var wrapper = document.querySelector('.project-carousel-wrapper');
    if (!wrapper) return;

    var grid = wrapper.querySelector('.project-card-grid.carousel-mode');
    if (!grid) return;

    var cards = grid.querySelectorAll(':scope > li');
    if (cards.length === 0) return;

    // Ensure the track container exists; if not, create it and move the grid inside.
    var track = wrapper.querySelector('.project-carousel-track');
    if (!track) {
      track = document.createElement('div');
      track.className = 'project-carousel-track';
      grid.parentNode.insertBefore(track, grid);
      track.appendChild(grid);
    }

    // Only enable infinite scroll when there are more than 4 cards.
    var SCROLL_THRESHOLD = 4;
    if (cards.length <= SCROLL_THRESHOLD) {
      track.classList.add('is-static');
      return;
    }

    track.classList.add('is-scrolling');

    // Clone all cards for seamless loop
    var fragment = document.createDocumentFragment();
    cards.forEach(function (card) {
      var clone = card.cloneNode(true);
      clone.classList.add('project-card--clone');
      // Clear focusable attributes on clones to avoid duplicate IDs
      clone.querySelectorAll('[id]').forEach(function (el) {
        el.removeAttribute('id');
      });
      fragment.appendChild(clone);
    });
    grid.appendChild(fragment);

    // Adjust animation speed based on card count.
    // Base: 60 seconds for one full cycle when 5 cards are present; scales linearly with count.
    var baseSpeed = 60;
    var speed = baseSpeed * (cards.length / 5);
    track.style.animationDuration = Math.max(speed, 30) + 's';

    // Pause on hover is handled by CSS, but also pause when tab focus is inside
    grid.addEventListener('focusin', function () {
      track.style.animationPlayState = 'paused';
    });
    grid.addEventListener('focusout', function () {
      track.style.animationPlayState = 'running';
    });

    // Touch devices: pause while user is interacting
    var touchPauseTimer;
    track.addEventListener('touchstart', function () {
      clearTimeout(touchPauseTimer);
      track.style.animationPlayState = 'paused';
    }, { passive: true });
    track.addEventListener('touchend', function () {
      touchPauseTimer = setTimeout(function () {
        track.style.animationPlayState = 'running';
      }, 2000); // resume after 2s of no interaction
    }, { passive: true });
  });
})();
