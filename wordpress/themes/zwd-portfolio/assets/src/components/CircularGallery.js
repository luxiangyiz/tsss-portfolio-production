const { createElement: h } = window.wp.element;

export function CircularGallery({ items }) {
  return h('div', {
    className: 'zwd-gallery-enhancement', role: 'navigation',
    'aria-label': '页面导航画廊',
  }, items.map(item => h('a', {
      href: item.href,
      key: item.href,
      className: 'zwd-gallery-card',
    },
      h('span', { className: 'zwd-gallery-card__number' }, item.number),
      h('span', { className: 'zwd-gallery-card__art', 'aria-hidden': 'true' }),
      h('strong', null, item.title)
    )));
}
