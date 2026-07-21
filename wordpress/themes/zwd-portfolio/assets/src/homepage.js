import { RagAssistant } from './components/RagAssistant';
import { mountProjectCarousel } from './components/ProjectCarousel';

document.documentElement.classList.add('js');

const { createElement: h, createRoot } = window.wp.element;
const roots = [];

const ragNode = document.querySelector('[data-zwd-rag]');
if (ragNode) {
  const root = createRoot(ragNode);
  root.render(h(RagAssistant));
  roots.push(root);
}

const disposeCarousel = mountProjectCarousel(document.querySelector('[data-project-carousel]'));

const sectionLinks = Array.from(document.querySelectorAll('.site-header a[href*="#"]'));
const sections = sectionLinks
  .map(link => document.querySelector(new URL(link.href, window.location.href).hash))
  .filter(Boolean);

if ('IntersectionObserver' in window && sections.length) {
  const observer = new IntersectionObserver(entries => {
    const visible = entries
      .filter(entry => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!visible) return;
    sectionLinks.forEach(link => {
      const active = new URL(link.href, window.location.href).hash === `#${visible.target.id}`;
      link.toggleAttribute('aria-current', active);
    });
  }, { rootMargin: '-20% 0px -65%', threshold: [0, 0.2, 0.6] });
  sections.forEach(section => observer.observe(section));
  window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
}

window.addEventListener('pagehide', () => {
  disposeCarousel();
  roots.forEach(root => root.unmount());
}, { once: true });
