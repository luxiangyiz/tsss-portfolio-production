import { ShinyText } from './components/ShinyText';
import { mountPrism } from './components/Prism';
import { RagAssistant } from './components/RagAssistant';
import { CircularGallery } from './components/CircularGallery';
import { navigationItems } from './data/navigation-items';

const { createElement: h, createRoot } = window.wp.element;
const roots = [];

function render(selector, component) {
  const node = document.querySelector(selector);
  if (!node) return;
  const root = createRoot(node);
  root.render(component);
  roots.push(root);
}

render('[data-zwd-shiny]', h(ShinyText, null, '欢迎来到我的网站'));
render('[data-zwd-rag]', h(RagAssistant));
render('[data-zwd-gallery]', h(CircularGallery, { items: navigationItems }));
const disposePrism = mountPrism(document.querySelector('[data-zwd-prism]'));

window.addEventListener('pagehide', () => {
  disposePrism();
  roots.forEach(root => root.unmount());
}, { once: true });
