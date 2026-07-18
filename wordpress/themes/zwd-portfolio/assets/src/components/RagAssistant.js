const { createElement: h, useState } = window.wp.element;

function citationLabel(citation, index) {
  const title = citation.title || `公开资料 ${index + 1}`;
  return citation.heading_path ? `${title} · ${citation.heading_path}` : title;
}

function statusLabel(status) {
  const labels = {
    answered: '基于公开资料的回答',
    insufficient_context: '当前公开资料不足',
    privacy_blocked: '该问题涉及非公开信息',
    configuration_error: '问答服务配置异常',
  };
  return labels[status] || '基于公开资料的回答';
}

export function RagAssistant() {
  const [question, setQuestion] = useState('');
  const [state, setState] = useState({ status: 'idle', answer: '', citations: [] });

  async function submit(event) {
    event.preventDefault();
    const value = question.trim();
    if (!value) return;
    setState({ status: 'loading', answer: '', citations: [] });
    const config = window.zwdHomepageConfig || {};
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), config.timeoutMs || 30000);
    try {
      const response = await fetch(config.askUrl || '/public/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: value }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || '服务暂时不可用，请稍后再试。');
      setState({
        status: data.status || 'answered',
        answer: data.answer || data.message || '当前公开资料不足以回答这个问题。',
        citations: Array.isArray(data.citations) ? data.citations : [],
      });
    } catch (error) {
      setState({
        status: 'error',
        answer: error.name === 'AbortError' ? '回答超时，请稍后重新提问。' : error.message,
        citations: [],
      });
    } finally {
      window.clearTimeout(timeout);
    }
  }

  return h('div', { className: 'zwd-rag-enhancement' },
    h('form', { className: 'zwd-rag-form', onSubmit: submit },
      h('label', { className: 'screen-reader-text', htmlFor: 'zwd-rag-question' }, '向个人助手提问'),
      h('input', {
        id: 'zwd-rag-question', value: question, maxLength: 500,
        placeholder: '问我任何关于经历、项目或能力的问题…',
        onChange: event => setQuestion(event.target.value),
      }),
      h('button', { type: 'submit', disabled: state.status === 'loading' }, state.status === 'loading' ? '回答中…' : '发送')
    ),
    state.status !== 'idle' && h('div', { className: `zwd-rag-answer is-${state.status}`, role: 'status', 'aria-live': 'polite' },
      h('p', { className: 'zwd-rag-status' }, state.status === 'loading' ? '正在检索已审核的公开资料…' : state.status === 'error' ? '暂时无法回答' : statusLabel(state.status)),
      state.answer && h('p', { className: 'zwd-rag-answer__body' }, state.answer),
      state.citations.length > 0 && h('div', { className: 'zwd-rag-citations' },
        h('h3', null, '公开资料引用'),
        h('ol', null, state.citations.map((citation, index) => h('li', { key: citation.id || index }, citationLabel(citation, index))))
      )
    ),
    h('p', { className: 'zwd-rag-privacy' }, 'AI 回答仅基于已审核的公开资料')
  );
}
