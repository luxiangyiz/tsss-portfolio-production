const { createElement: h } = window.wp.element;

export function ShinyText({ children }) {
  return h('span', { className: 'zwd-shiny-text' }, children);
}
