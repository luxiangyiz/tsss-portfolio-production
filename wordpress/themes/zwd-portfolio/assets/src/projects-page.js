/**
 * 项目归档页入口脚本 — 加载 3D 旋转画廊
 *
 * 从 WordPress REST API 获取已发布项目数据，
 * 生成每张卡片的视觉图片，挂载 OGL 3D 圆弧画廊组件。
 *
 * 依赖：
 *   - wp.element（WordPress 内置 React）
 *   - ogl（WebGL 渲染引擎）
 *   - 组件：CircularGallery3D
 */
const { createElement: h, createRoot } = window.wp.element;
import CircularGallery3D from './components/CircularGallery3D';

/* ------------------------------------------------------------------ */
/*  为项目生成渐变卡片图片（Canvas → DataURL）                          */
/*                                                                    */
/*  每张卡片使用不同的配色方案，基于项目索引计算，                       */
/*  保证视觉区分度且无需外部图片资源。                                  */
/* ------------------------------------------------------------------ */

/** 配色方案库 —— 每组 [背景起始色, 背景结束色, 强调色] */
const COLOR_PALETTES = [
  ['#1a1a2e', '#16213e', '#e94560'],   // 深靛红
  ['#0f3460', '#533483', '#e94560'],    // 深紫红
  ['#1b262c', '#0f4c75', '#bbe1fa'],    // 深蓝冰
  ['#222831', '#393e46', '#00adb5'],     // 深灰青
  ['#2d132c', '#801336', '#ee4540'],     // 暗酒红
  ['#1a1a2e', '#0f3460', '#00fff5'],     // 靛蓝霓虹
  ['#232526', '#414345', '#f5af19'],     // 深灰金
  ['#141e30', '#243b55', '#00d2ff'],     // 午夜蓝
];

/**
 * 生成一张 800×600 的渐变卡片图片（DataURL）
 * 包含项目序号、标题文字和配色渐变背景
 *
 * @param {Object} project - 项目数据
 * @param {number} index - 项目索引（从 0 开始）
 * @returns {string} data:image/png;... 格式的图片 URL
 */
function generateProjectCardImage(project, index) {
  const palette = COLOR_PALETTES[index % COLOR_PALETTES.length];
  const [bgStart, bgEnd, accent] = palette;

  const canvas = document.createElement('canvas');
  const W = 800;
  const H = 600;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  /* 背景渐变 */
  const bgGrad = ctx.createLinearGradient(0, 0, W, H);
  bgGrad.addColorStop(0, bgStart);
  bgGrad.addColorStop(1, bgEnd);
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  /* 装饰圆/几何图形 */
  ctx.globalAlpha = 0.08;
  ctx.fillStyle = accent;
  ctx.beginPath();
  ctx.arc(W * 0.85, H * 0.15, Math.max(W, H) * 0.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(W * 0.1, H * 0.85, Math.max(W, H) * 0.25, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;

  /* 左侧序号条 */
  const numStr = String(index + 1).padStart(2, '0');
  ctx.fillStyle = accent;
  ctx.font = 'bold 180px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  ctx.fillText(numStr, 50, H / 2);

  /* 分隔线 */
  ctx.strokeStyle = accent;
  ctx.globalAlpha = 0.5;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(220, H * 0.25);
  ctx.lineTo(220, H * 0.75);
  ctx.stroke();
  ctx.globalAlpha = 1;

  /* 标题文字 */
  ctx.fillStyle = '#ffffff';
  const title = project.title?.rendered || 'Untitled';
  const maxTitleWidth = W - 300;
  let fontSize = 52;
  ctx.font = `bold ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
  while (ctx.measureText(title).width > maxTitleWidth && fontSize > 24) {
    fontSize -= 2;
    ctx.font = `bold ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
  }
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.fillText(title, 260, H * 0.28);

  /* 摘要/描述（截取一行） */
  const excerpt = project.excerpt?.rendered
    ? project.excerpt.rendered.replace(/<[^>]+>/g, '').trim().slice(0, 60)
    : '';
  if (excerpt) {
    ctx.fillStyle = 'rgba(255,255,255,0.65)';
    ctx.font = '22px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(excerpt + (excerpt.length >= 60 ? '…' : ''), 260, H * 0.28 + fontSize + 24);
  }

  /* 技能标签行 */
  if (project.project_skill?.length) {
    const tags = project.project_skill.slice(0, 4);
    ctx.font = '600 18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    let tagX = 260;
    const tagY = H * 0.28 + fontSize + 60;
    tags.forEach((tag) => {
      const text = typeof tag === 'string' ? tag : tag.name || String(tag);
      const tw = ctx.measureText(text).width + 20;
      ctx.fillStyle = accent;
      ctx.globalAlpha = 0.2;
      roundRect(ctx, tagX, tagY - 4, tw, 28, 4);
      ctx.fill();
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = '#ffffff';
      ctx.textBaseline = 'middle';
      ctx.textAlign = 'left';
      ctx.fillText(text, tagX + 10, tagY + 10);
      tagX += tw + 10;
    });
  }

  /* 底部提示条 */
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.fillRect(0, H - 50, W, 50);
  ctx.fillStyle = 'rgba(255,255,255,0.6)';
  ctx.font = '500 16px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  ctx.fillText('查看详情 →', W - 30, H - 25);

  return canvas.toDataURL('image/png');
}

/**
 * 圆角矩形辅助函数
 */
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/* ------------------------------------------------------------------ */
/*  主逻辑：获取数据 → 生成图片 → 挂载组件                              */
/* ------------------------------------------------------------------ */

async function initProjectGallery() {
  const mountNode = document.querySelector('[data-zwd-project-gallery]');
  if (!mountNode) return;

  /* 显示加载状态 */
  mountNode.innerHTML = '<p class="project-gallery-loading" style="padding:3rem;text-align:center;color:var(--zwd-muted,#666);">正在加载项目画廊…</p>';

  /* WebGL 支持检测 */
  try {
    const testCanvas = document.createElement('canvas');
    const gl = testCanvas.getContext('webgl2') || testCanvas.getContext('webgl');
    if (!gl) {
      mountNode.innerHTML = '<p class="project-gallery-error">您的浏览器不支持 WebGL，无法显示 3D 画廊。</p>';
      return;
    }
  } catch (e) {
    mountNode.innerHTML = '<p class="project-gallery-error">WebGL 初始化失败。</p>';
    return;
  }

  /* 检查 wp.element 是否可用 */
  if (typeof window.wp === 'undefined' || !window.wp.element) {
    console.error('[ZWD Project Gallery] wp.element 未就绪');
    mountNode.innerHTML = '<p class="project-gallery-error">页面组件未就绪，请刷新重试。</p>';
    return;
  }

  const restUrl = mountNode.dataset.restUrl || '/wp-json/wp/v2/project?per_page=20&_embed';
  const nonce = mountNode.dataset.nonce || '';

  try {
    /* 获取 WordPress 项目数据 */
    const headers = {};
    if (nonce) headers['X-WP-Nonce'] = nonce;
    const resp = await fetch(restUrl, { headers });
    if (!resp.ok) throw new Error(`REST API error: ${resp.status}`);
    const projects = await resp.json();

    if (!projects.length) {
      mountNode.innerHTML = '<p class="project-gallery-empty">暂无已发布的项目。</p>';
      return;
    }

    /* 将 WP 数据映射为画廊 items */
    const galleryItems = projects.map((p, i) => ({
      image: generateProjectCardImage(p, i),
      text: p.title?.rendered || 'Untitled',
      link: p.link,
      slug: p.slug,
    }));

    /* 点击回调：跳转到项目详情页 */
    function handleItemClick(itemIndex) {
      /* itemIndex 可能超过原数组长度（因为画廊内部做了拼接循环） */
      const realIndex = itemIndex % projects.length;
      const project = projects[realIndex];
      if (project?.link) {
        window.location.href = project.link;
      }
    }

    /* 挂载 React 组件 */
    const root = createRoot(mountNode);
    root.render(
      h(CircularGallery3D, {
        items: galleryItems,
        bend: 1,
        textColor: '#ffffff',
        borderRadius: 0.04,
        font: 'bold 26px sans-serif',
        scrollSpeed: 2.5,
        scrollEase: 0.06,
        onItemClick: handleItemClick,
      }),
    );

    /* 清理 */
    window.addEventListener(
      'pagehide',
      () => {
        root.unmount();
      },
      { once: true },
    );
  } catch (err) {
    console.error('[ZWD Project Gallery]', err);
    mountNode.innerHTML =
      '<p class="project-gallery-error">项目加载失败，请刷新页面重试。</p>';
  }
}

/* DOM 就绪后初始化 */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProjectGallery);
} else {
  initProjectGallery();
}
