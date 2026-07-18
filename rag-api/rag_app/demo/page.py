"""本地RAG演示页面。"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()


DEMO_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI求职知识库 · 本地RAG演示</title>
  <style>
    :root {
      --ink: #17231f;
      --muted: #66736e;
      --paper: #f4f1e8;
      --surface: rgba(255,255,255,.78);
      --line: rgba(23,35,31,.13);
      --green: #176b52;
      --green-2: #25906e;
      --orange: #d56436;
      --shadow: 0 18px 48px rgba(37,55,48,.10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 4%, rgba(37,144,110,.13), transparent 28rem),
        radial-gradient(circle at 92% 16%, rgba(213,100,54,.12), transparent 24rem),
        var(--paper);
      font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.55;
    }
    .privacy-bar {
      position: sticky; top: 0; z-index: 20;
      padding: .65rem 1rem;
      color: #fff; background: #17231f;
      text-align: center; font-size: .86rem; letter-spacing: .02em;
    }
    .shell { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 52px 0 72px; }
    .hero { display: grid; grid-template-columns: 1.45fr .75fr; gap: 24px; align-items: stretch; }
    .hero-copy, .mode-card, .panel {
      border: 1px solid var(--line); background: var(--surface);
      backdrop-filter: blur(16px); border-radius: 24px; box-shadow: var(--shadow);
    }
    .hero-copy { padding: 42px; position: relative; overflow: hidden; }
    .hero-copy::after {
      content: ""; position: absolute; right: -70px; bottom: -90px;
      width: 230px; height: 230px; border: 38px solid rgba(23,107,82,.08); border-radius: 50%;
    }
    .eyebrow { color: var(--green); font-size: .8rem; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; }
    h1 { margin: 12px 0 14px; max-width: 720px; font-family: Georgia, "Noto Serif SC", serif; font-size: clamp(2.2rem, 5vw, 4.6rem); line-height: 1.05; letter-spacing: -.045em; }
    .lede { max-width: 650px; margin: 0; color: var(--muted); font-size: 1.05rem; }
    .mode-card { padding: 28px; display: flex; flex-direction: column; justify-content: space-between; }
    .mode-pill { display: inline-flex; align-items: center; gap: 9px; width: fit-content; padding: 7px 12px; border-radius: 999px; background: #e7f3ee; color: var(--green); font-size: .76rem; font-weight: 800; letter-spacing: .08em; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green-2); box-shadow: 0 0 0 5px rgba(37,144,110,.13); }
    .mode-title { margin: 22px 0 5px; font-size: 1.6rem; }
    .mode-meta { color: var(--muted); font-size: .9rem; }
    .warning { margin-top: 22px; padding: 14px; border-left: 3px solid var(--orange); background: #fff4ed; color: #75412e; border-radius: 4px 12px 12px 4px; font-size: .85rem; }
    .status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 24px 0; }
    .status-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 16px; background: rgba(255,255,255,.58); }
    .status-card span { display: block; color: var(--muted); font-size: .76rem; }
    .status-card strong { display: block; margin-top: 4px; font-size: 1.02rem; }
    .workspace { display: grid; grid-template-columns: .78fr 1.22fr; gap: 24px; margin-top: 24px; }
    .panel { padding: 26px; }
    .panel h2 { margin: 0 0 5px; font-family: Georgia, "Noto Serif SC", serif; font-size: 1.45rem; }
    .sub { margin: 0 0 20px; color: var(--muted); font-size: .88rem; }
    .stack { display: grid; gap: 12px; }
    .row { display: grid; grid-template-columns: 1fr auto; gap: 10px; }
    label { display: grid; gap: 6px; color: var(--muted); font-size: .78rem; font-weight: 700; }
    input, select, textarea, button { font: inherit; }
    input, select, textarea {
      width: 100%; color: var(--ink); background: rgba(255,255,255,.88);
      border: 1px solid var(--line); border-radius: 12px; padding: 11px 13px; outline: none;
    }
    input:focus, select:focus, textarea:focus { border-color: var(--green-2); box-shadow: 0 0 0 3px rgba(37,144,110,.12); }
    textarea { min-height: 96px; resize: vertical; }
    button {
      border: 0; border-radius: 12px; padding: 11px 15px; cursor: pointer;
      background: var(--green); color: #fff; font-weight: 750;
      transition: transform .15s ease, background .15s ease;
    }
    button:hover { background: #10563f; transform: translateY(-1px); }
    button.secondary { color: var(--green); background: #e7f3ee; }
    button.secondary:hover { background: #d8ebe3; }
    button:disabled { cursor: wait; opacity: .55; transform: none; }
    .button-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .result {
      min-height: 170px; max-height: 520px; overflow: auto; margin-top: 16px; padding: 16px;
      border: 1px solid var(--line); border-radius: 16px; background: #17231f; color: #dce9e4;
      white-space: pre-wrap; overflow-wrap: anywhere; font: .82rem/1.65 ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    .result.empty { display: grid; place-items: center; color: #97a9a2; font-family: inherit; text-align: center; }
    .tabs { display: flex; gap: 8px; margin-bottom: 16px; }
    .tab { background: transparent; color: var(--muted); border: 1px solid var(--line); }
    .tab.active { color: #fff; background: var(--green); }
    .footer-note { margin: 28px 0 0; color: var(--muted); font-size: .82rem; text-align: center; }
    @media (max-width: 850px) {
      .hero, .workspace { grid-template-columns: 1fr; }
      .status-grid { grid-template-columns: repeat(2, 1fr); }
      .hero-copy { padding: 30px; }
    }
    @media (max-width: 520px) {
      .shell { width: min(100% - 20px, 1180px); padding-top: 24px; }
      .status-grid, .button-grid { grid-template-columns: 1fr; }
      .row { grid-template-columns: 1fr; }
      .panel, .mode-card { padding: 20px; border-radius: 18px; }
    }
  </style>
</head>
<body>
  <div class="privacy-bar">本页面仅在本机运行。private scope可能包含个人敏感信息，请勿截图或公开分享。</div>
  <main class="shell">
    <section class="hero">
      <div class="hero-copy">
        <div class="eyebrow">Personal Knowledge Retrieval</div>
        <h1>AI求职知识库<br>本地RAG控制台</h1>
        <p class="lede">预览知识文档、构建分层索引，并在private、internal与public三个访问范围内测试检索和引用问答。</p>
      </div>
      <aside class="mode-card">
        <div>
          <div class="mode-pill"><span class="dot"></span><span id="mode-pill">正在检测</span></div>
          <h2 class="mode-title" id="mode-title">本地运行模式</h2>
          <div class="mode-meta" id="model-meta">正在连接服务…</div>
        </div>
        <div class="warning" id="mode-warning">当前为离线演示模式，不代表真实语义检索和问答质量。</div>
      </aside>
    </section>

    <section class="status-grid" aria-label="服务状态">
      <div class="status-card"><span>服务</span><strong id="status-service">检测中</strong></div>
      <div class="status-card"><span>向量库</span><strong id="status-qdrant">检测中</strong></div>
      <div class="status-card"><span>Embedding</span><strong id="status-embedding">检测中</strong></div>
      <div class="status-card"><span>LLM</span><strong id="status-llm">检测中</strong></div>
    </section>

    <section class="workspace">
      <div class="panel">
        <h2>知识库与索引</h2>
        <p class="sub">先预览纳入范围，再执行全量或增量构建。原始Markdown不会被修改。</p>
        <div class="stack">
          <label>建库范围
            <select id="ingest-scope">
              <option value="all">全部范围</option>
              <option value="private">private</option>
              <option value="internal">internal</option>
              <option value="public">public</option>
            </select>
          </label>
          <div class="button-grid">
            <button class="secondary" data-action="preview">Preview</button>
            <button data-action="full">全量建库</button>
            <button data-action="incremental">增量更新</button>
          </div>
          <button class="secondary" data-action="stats">刷新索引统计</button>
        </div>
        <div id="admin-result" class="result empty">操作结果将在这里显示</div>
      </div>

      <div class="panel">
        <h2>检索与引用问答</h2>
        <p class="sub">选择访问范围后测试。public范围不会跨越到private或internal内容。</p>
        <div class="tabs" role="tablist">
          <button class="tab active" data-tab="search">检索</button>
          <button class="tab" data-tab="ask">问答</button>
        </div>
        <div class="stack">
          <label>访问范围
            <select id="query-scope">
              <option value="internal">internal</option>
              <option value="private">private</option>
              <option value="public">public</option>
            </select>
          </label>
          <label id="query-label">检索问题
            <textarea id="query" placeholder="例如：我有哪些经历可以证明RAG能力？"></textarea>
          </label>
          <div class="row">
            <label>返回数量
              <select id="top-k"><option>3</option><option selected>5</option><option>10</option></select>
            </label>
            <button data-action="run-query">执行检索</button>
          </div>
        </div>
        <div id="query-result" class="result empty">检索结果、回答状态、引用和pending提示将在这里显示</div>
      </div>
    </section>
    <p class="footer-note">仅限127.0.0.1本地开发演示 · 不允许公网访问 · 不代表真实模型质量</p>
  </main>
  <script>
    const state = { tab: 'search' };
    const $ = (selector) => document.querySelector(selector);
    const pretty = (value) => JSON.stringify(value, null, 2);
    const show = (target, value) => {
      target.classList.remove('empty');
      target.textContent = typeof value === 'string' ? value : pretty(value);
    };
    const busy = (button, active) => { button.disabled = active; };

    async function request(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      const data = await response.json().catch(() => ({ detail: '响应不是有效JSON' }));
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      return data;
    }

    async function refreshHealth() {
      try {
        const data = await request('/health');
        $('#status-service').textContent = data.status;
        $('#status-qdrant').textContent = data.qdrant;
        $('#status-embedding').textContent = data.embedding;
        $('#status-llm').textContent = data.llm;
        $('#mode-pill').textContent = data.runtime_label;
        $('#mode-title').textContent = data.runtime_label === 'OFFLINE DEMO' ? '离线工程演示' : '真实模型调试';
        $('#model-meta').textContent = `Embedding：${data.embedding_model} · LLM：${data.llm_model}`;
        const warning = $('#mode-warning');
        warning.hidden = data.runtime_label !== 'OFFLINE DEMO';
        if (data.limitations && data.limitations.length) warning.textContent = data.limitations.join('；');
      } catch (error) {
        $('#status-service').textContent = '连接失败';
        $('#model-meta').textContent = error.message;
      }
    }

    async function adminAction(action, button) {
      busy(button, true);
      try {
        let data;
        if (action === 'preview') data = await request('/ingest/preview', { method: 'POST' });
        if (action === 'stats') {
          const raw = await request('/index/stats');
          data = { scopes: raw.collections.map(item => ({
            scope: item.collection_name.replace(/^kb_/, ''),
            documents: item.document_count,
            chunks: item.chunk_count,
            errors: item.error_count,
          })) };
        }
        if (action === 'full' || action === 'incremental') {
          data = await request('/ingest', {
            method: 'POST',
            body: JSON.stringify({ mode: action, scope: $('#ingest-scope').value }),
          });
        }
        show($('#admin-result'), data);
        if (action !== 'stats') await refreshHealth();
      } catch (error) {
        show($('#admin-result'), `操作失败：${error.message}`);
      } finally { busy(button, false); }
    }

    async function runQuery(button) {
      const text = $('#query').value.trim();
      if (!text) { show($('#query-result'), '请先输入问题。'); return; }
      busy(button, true);
      try {
        const scope = $('#query-scope').value;
        const topK = Number($('#top-k').value);
        const isAsk = state.tab === 'ask';
        const data = await request(isAsk ? '/ask' : '/search', {
          method: 'POST',
          body: JSON.stringify(isAsk
            ? { question: text, index_scope: scope, top_k: topK, filters: {} }
            : { query: text, index_scope: scope, top_k: topK, filters: {} }),
        });
        show($('#query-result'), data);
      } catch (error) {
        show($('#query-result'), `请求失败：${error.message}`);
      } finally { busy(button, false); }
    }

    document.querySelectorAll('[data-action]').forEach(button => {
      button.addEventListener('click', () => {
        const action = button.dataset.action;
        if (action === 'run-query') runQuery(button);
        else adminAction(action, button);
      });
    });
    document.querySelectorAll('[data-tab]').forEach(button => {
      button.addEventListener('click', () => {
        state.tab = button.dataset.tab;
        document.querySelectorAll('[data-tab]').forEach(item => item.classList.toggle('active', item === button));
        $('#query-label').childNodes[0].textContent = state.tab === 'ask' ? '问答问题\n            ' : '检索问题\n            ';
        $('[data-action="run-query"]').textContent = state.tab === 'ask' ? '执行问答' : '执行检索';
      });
    });
    refreshHealth();
  </script>
</body>
</html>"""


@router.get("/demo", response_class=HTMLResponse)
async def demo_page():
    return HTMLResponse(
        content=DEMO_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'self'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:; frame-ancestors 'none'"
            ),
        },
    )
