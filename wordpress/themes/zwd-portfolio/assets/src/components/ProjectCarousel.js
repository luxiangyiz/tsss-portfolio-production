const DRAG_THRESHOLD = 8;

export function mountProjectCarousel(root) {
  if (!root) return () => {};

  const track = root.querySelector('[data-project-track]');
  const previous = root.querySelector('[data-project-previous]');
  const next = root.querySelector('[data-project-next]');
  const cards = Array.from(root.querySelectorAll('[data-project-card]'));
  let pointerId = null;
  let startX = 0;
  let startScrollLeft = 0;
  let dragged = false;
  let frame = 0;

  cards.forEach(card => { card.draggable = false; });

  function cardStep() {
    const firstCard = cards[0];
    if (!firstCard) return track.clientWidth;
    const styles = getComputedStyle(track);
    const gap = parseFloat(styles.columnGap || styles.gap || '0');
    return firstCard.getBoundingClientRect().width + gap;
  }

  function updateControls() {
    const maxScroll = Math.max(0, track.scrollWidth - track.clientWidth - 2);
    previous.disabled = track.scrollLeft <= 2;
    next.disabled = track.scrollLeft >= maxScroll;
  }

  function scheduleControls() {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      updateControls();
    });
  }

  function onCardClick(event) {
    if (dragged) event.preventDefault();
  }

  function onDragStart(event) {
    event.preventDefault();
  }

  function onPointerDown(event) {
    if (event.button !== 0 || !cards.length) return;
    pointerId = event.pointerId;
    startX = event.clientX;
    startScrollLeft = track.scrollLeft;
    dragged = false;
    track.setPointerCapture(pointerId);
    track.classList.add('is-dragging');
  }

  function onPointerMove(event) {
    if (event.pointerId !== pointerId) return;
    const delta = event.clientX - startX;
    if (Math.abs(delta) >= DRAG_THRESHOLD) dragged = true;
    if (dragged) {
      event.preventDefault();
      track.scrollLeft = startScrollLeft - delta;
    }
  }

  function onPointerEnd(event) {
    if (event.pointerId !== pointerId) return;
    if (track.hasPointerCapture(pointerId)) track.releasePointerCapture(pointerId);
    pointerId = null;
    track.classList.remove('is-dragging');
    window.setTimeout(() => { dragged = false; }, 0);
  }

  previous.addEventListener('click', () => track.scrollBy({ left: -cardStep(), behavior: 'smooth' }));
  next.addEventListener('click', () => track.scrollBy({ left: cardStep(), behavior: 'smooth' }));
  track.addEventListener('click', onCardClick);
  track.addEventListener('dragstart', onDragStart);
  track.addEventListener('pointerdown', onPointerDown);
  track.addEventListener('pointermove', onPointerMove);
  track.addEventListener('pointerup', onPointerEnd);
  track.addEventListener('pointercancel', onPointerEnd);
  track.addEventListener('scroll', scheduleControls, { passive: true });
  updateControls();

  return () => {
    if (frame) cancelAnimationFrame(frame);
    track.removeEventListener('click', onCardClick);
    track.removeEventListener('dragstart', onDragStart);
    track.removeEventListener('pointerdown', onPointerDown);
    track.removeEventListener('pointermove', onPointerMove);
    track.removeEventListener('pointerup', onPointerEnd);
    track.removeEventListener('pointercancel', onPointerEnd);
    track.removeEventListener('scroll', scheduleControls);
  };
}
