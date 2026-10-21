/* Optional bounded V3 trial. Native module APIs own all durable task state. */
(() => {
  'use strict';
  const api = '/api/integrations/render-bridge/v1/native';
  const profiles = { 'codex-image': '本机生成', 'midjourney-manual': '人工交回', 'fake-image': '生成测试图' };
  const states = { plan_pending: '正在准备', queued: '排队中', running: '正在制作', uploading: '正在接收图片',
    review_pending: '图片已登记，审核处理中', registered: '已登记 · 仅供审核', plan_unknown: '准备结果待核对，请勿重复新建',
    import_unknown: '登记结果待核对，请勿重复新建', plan_blocked: '当前要求暂不支持', cancel_requested: '正在取消',
    canceled: '已取消', rejected: '图片未通过登记检查', failed: '本次未完成', expired: '任务已过期',
    blocked_scope: '项目权限或连接已变化', blocked_revision: '项目已变化，请重新确认',
    remote_unavailable: '连接暂不可用，后台会继续核对同一任务', protocol_error: '返回内容不符合要求',
    action_required: '需要在本机处理' };
  const reviews = { finalizing: '处理中', blocked: '待处理', generated: '已完成审核流程', failed: '未完成',
    selected: '已登记', ready: '已登记', passed: '通过', rejected: '未通过' };
  let dialog, context = null, epoch = 0, abort = null, timer = null, ready = false, sending = false;
  let pollBusy = false, initializing = false;
  const previews = new Map(), viewed = new Set();
  const $ = name => dialog.querySelector(`[data-bridge="${name}"]`);
  function token() { try { return localStorage.getItem('alchemy_veyra_access_token') || ''; } catch { return ''; } }
  function node(tag, text, className) { const el = document.createElement(tag); if (text) el.textContent = text; if (className) el.className = className; return el; }
  function notice(text) { $('notice').textContent = text; }
  function current(id) {
    if (!context || epoch !== id || !dialog.open) return false;
    if (context.session !== token()) { close(); return false; }
    return true;
  }
  function close() {
    epoch++; abort?.abort(); abort = null; clearInterval(timer); timer = null;
    context = null; ready = false; sending = false; pollBusy = false; initializing = false;
    for (const value of previews.values()) if (value.url) URL.revokeObjectURL(value.url);
    previews.clear(); viewed.clear();
    if (dialog?.open) dialog.close();
    if (dialog) { $('tasks').replaceChildren(); $('prompt').value = ''; $('project').textContent = ''; $('references').replaceChildren(); }
  }
  async function request(path, options = {}) {
    const session = context?.session || '';
    const headers = { ...options.headers };
    if (session) headers.Authorization = `Bearer ${session}`;
    const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      signal: abort?.signal, ...options, headers });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(value.detail?.code || `HTTP ${response.status}`); error.status = response.status; throw error; }
    return value;
  }
  function failure(error) {
    if ([401, 403].includes(error.status)) return '请先登录有权使用这个项目的账号，再重新打开试用。';
    if (error.status === 404) return '管理员可能尚未开启桥接试用，或当前项目已不可用。请联系管理员确认；原来的生成方式不受影响。';
    return '暂时无法连接。请稍后点“刷新”；不要重复新建任务。';
  }
  function update() {
    $('start').disabled = !ready || sending;
    $('refresh').disabled = initializing || sending;
    $('settings').disabled = !ready || sending;
    $('start').textContent = sending ? '正在提交…' : '开始试用';
    const profile = dialog.querySelector('[name="bridge-profile"]:checked')?.value;
    $('profile-note').textContent = profile === 'fake-image' ? '只验证流程，测试图不会按文字或参考图内容制作。'
      : profile === 'midjourney-manual' ? '需要在执行端人工制作并交回原图，不会自动出图。'
      : profile === 'codex-image' ? '由已配置的工具制作；需要本机确认时，会在记录中提示。' : '';

  }
  function build() {
    if (dialog) return;
    dialog = node('dialog', '', 'v3-bridge-trial');
    dialog.setAttribute('aria-labelledby', 'v3BridgeTrialTitle');
    dialog.innerHTML = `
      <div class="bridge-head"><h2 id="v3BridgeTrialTitle">本地桥接试用</h2><button type="button" data-bridge="close" aria-label="关闭桥接试用">关闭</button></div>
      <p data-bridge="project"></p>
      <p class="bridge-hint">这是独立的单图试用，只带入文字需求。原页面的数量、模式、参考图和高级设置不会带入，也不会被修改。</p>
      <p class="bridge-hint">结果仅供审核，不会自动成为正式作品。真实工具和参考图效果尚未验收。</p>
      <p data-bridge="notice" role="status" aria-live="polite"></p>
      <form data-bridge="form"><fieldset data-bridge="settings" disabled>
        <label class="bridge-field">想做什么图<textarea data-bridge="prompt" rows="3" maxlength="16000" required></textarea></label>
        <fieldset class="bridge-choices"><legend>怎么制作</legend><div data-bridge="profiles"></div><p data-bridge="profile-note" class="bridge-hint"></p></fieldset>
        <fieldset class="bridge-choices"><legend>图片形状（每次一张）</legend><div>
          <label><input type="radio" name="bridge-size" value="1024x1024" checked>方图</label>
          <label><input type="radio" name="bridge-size" value="1024x768">横图</label>
          <label><input type="radio" name="bridge-size" value="768x1024">竖图</label>
        </div></fieldset>
        <details><summary>参考图与格式（可不改）</summary>
          <p class="bridge-hint">只列出已加入本项目、允许使用的原图，按选择顺序最多两张。当前页面尚未上传或尚未加入项目的图片不会带入。人工交回不支持参考图。</p>
          <div data-bridge="references"></div>
          <label class="bridge-field">图片格式<select data-bridge="format"><option value="png">PNG</option><option value="jpeg">JPEG</option></select></label>
          <p class="bridge-hint">不改变原图格式或大小。暂不支持高保真、质量档位及其他高级选项；要求不满足时会停止，而不是降低要求。</p>
        </details>
        <label class="bridge-ack"><input type="checkbox" data-bridge="ack" required>我知道这是单图试用，不是正式交付</label>
      </fieldset><button type="submit" data-bridge="start" disabled>开始试用</button></form>
      <div class="bridge-head"><h3>本项目的试用记录</h3><button type="button" data-bridge="refresh">刷新</button></div>
      <p class="bridge-hint">关闭后后台仍会处理。再次打开可查看进度；相同内容重复点击会核对同一请求。</p>
      <div data-bridge="tasks" aria-live="polite"></div>`;
    document.body.append(dialog);
    $('close').onclick = close;
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    $('form').addEventListener('submit', submit);
    $('profiles').addEventListener('change', update);
    $('refresh').onclick = () => initialize(epoch);
    // Record explicit order without inferring reference selection from the host.
    $('references').addEventListener('change', event => {
      if (!context || !event.target.matches('input')) return;
      const id = event.target.value;
      if (event.target.checked && context.references.length >= 2) {
        event.target.checked = false; notice('最多选两张参考图，请先取消一张。'); return;
      }
      context.references = context.references.filter(value => value !== id);
      if (event.target.checked) context.references.push(id);
    });
  }
  async function initialize(id) {
    if (!current(id) || !context.eligible || sending || initializing) return;
    initializing = true; ready = false; update(); notice('正在检查连接…');
    try {
      const status = await request(`${api}/status`);
      if (!current(id)) return;
      const previous = dialog.querySelector('[name="bridge-profile"]:checked')?.value;
      $('profiles').replaceChildren();
      for (const [profile, label] of Object.entries(profiles)) {
        if (!(status.profiles || []).includes(profile)) continue;
        const item = node('label'); const radio = node('input'); radio.type = 'radio'; radio.name = 'bridge-profile'; radio.value = profile; radio.required = true;
        radio.checked = previous === profile; item.append(radio, document.createTextNode(label)); $('profiles').append(item);
      }
      const profileChanged = Boolean(previous && !dialog.querySelector('[name="bridge-profile"]:checked'));
      if (profileChanged) $('ack').checked = false;
      if (!previous) { const first = $('profiles').querySelector('input'); if (first) first.checked = true; }
      if (!status.available || status.error) { notice('桥接尚未准备好，请联系管理员检查连接。仍可使用原来的生成按钮。'); await refresh(id); return; }
      if (status.mode !== 'enabled') { notice('桥接暂停接收新任务，已有记录仍可查看。请联系管理员开启后再试。'); await refresh(id); return; }
      if (!$('profiles').querySelector('input')) { notice('还没有可用的制作方式，请联系管理员启用。'); await refresh(id); return; }
      const refs = await request(`${api}/references?project_id=${encodeURIComponent(context.projectId)}`);
      if (!current(id)) return;
      const allowed = new Set((refs.references || []).map(item => item.asset_id));
      const missing = context.references.some(value => !allowed.has(value));
      if (missing) { context.references = []; $('ack').checked = false; notice('先前选择的参考图已不可用，已取消选择。请重新选择参考图，或确认不使用参考图，再勾选试用确认。'); }
      $('references').replaceChildren();
      for (const item of refs.references || []) {
        const label = node('label', '', 'bridge-reference'); const input = node('input'); input.type = 'checkbox'; input.value = item.asset_id;
        input.checked = context.references.includes(item.asset_id); label.append(input, document.createTextNode(item.label || '项目参考图')); $('references').append(label);
      }
      if (!allowed.size) $('references').append(node('p', '暂无符合要求的项目参考图，可以直接做文字试用。', 'bridge-hint'));
      ready = true; update();
      if (profileChanged) notice('先前的制作方式已不可用。请重新选择制作方式，并再次勾选试用确认。');
      else if (!missing) notice('入口已准备好。点击“开始试用”后会先检查制作能力，不符合要求时会停止。');
      await refresh(id);
    } catch (error) { if (current(id)) { ready = false; update(); notice(failure(error)); $('tasks').replaceChildren(); } }
    finally { if (current(id)) { initializing = false; update(); } }
  }
  async function showPreview(outputId, holder, id) {
    if (!current(id)) return;
    holder.textContent = '正在读取审核图片…';
    try {
      let entry = previews.get(outputId);
      if (!entry) {
        entry = {};
        const session = context.session;
        entry.promise = (async () => {
          const response = await fetch(`/api/v3/creative-agent/outputs/${encodeURIComponent(outputId)}/preview`, {
            credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: abort?.signal,
            headers: session ? { Authorization: `Bearer ${session}` } : {},
          });
          if (!response.ok) throw new Error('preview_unavailable');
          const blob = await response.blob();
          if (!current(id)) return null;
          if (!['image/png', 'image/jpeg', 'image/webp'].includes(blob.type) || !blob.size || blob.size > 16 * 1024 * 1024) throw new Error('invalid_preview');
          entry.url = URL.createObjectURL(blob);
          return entry.url;
        })();
        previews.set(outputId, entry);
      }
      const url = await entry.promise;
      if (!url || !current(id) || !holder.isConnected) return;
      const image = node('img'); image.alt = '桥接试用图片，仅供审核，非正式交付'; image.src = url;
      image.onerror = () => { if (current(id) && holder.isConnected) holder.textContent = '预览暂不可用，请稍后刷新。'; };
      holder.replaceChildren(image, node('p', '仅供审核，不是正式作品。', 'bridge-hint'));
    } catch {
      if (current(id)) {
        const entry = previews.get(outputId); if (entry?.url) URL.revokeObjectURL(entry.url);
        previews.delete(outputId);
        if (holder.isConnected) holder.textContent = '预览暂不可用，请稍后刷新。';
      }
    }
  }
  async function refresh(id) {
    if (!current(id) || pollBusy) return;
    pollBusy = true;
    try {
      const value = await request(`${api}/tasks?project_id=${encodeURIComponent(context.projectId)}`);
      if (!current(id)) return;
      $('tasks').replaceChildren();
      for (const task of value.tasks || []) {
        if (task.project_id !== context.projectId) continue;
        const box = node('article', '', 'bridge-task');
        box.append(node('strong', task.review_pending ? states.review_pending : (states[task.state] || '正在核对状态')));
        box.append(node('p', `${profiles[task.profile_id] || '桥接试用'} · ${task.size || ''} · ${task.test_fixture ? '合成测试图' : '真实工具尚未验收'}`, 'bridge-hint'));
        if (task.action_required_detail?.message) box.append(node('p', task.action_required_detail.message));
        if (task.review_status) box.append(node('p', `审核：${reviews[task.review_status] || '正在核对'}。仅供审核，不代表正式交付。`));
        if (task.native_registration === 'registered') box.append(node('p', '图片已登记；不会自动选中、导出或设为后续参考。', 'bridge-hint'));
        if (task.native_registration === 'registered' && typeof task.native_registration_ref === 'string') {
          const outputId = task.native_registration_ref;
          const preview = node('div', '', 'bridge-review-preview');
          const view = node('button', '查看审核图片'); view.type = 'button';
          view.onclick = () => { if (current(id)) { viewed.add(outputId); view.hidden = true; showPreview(outputId, preview, id); } };
          box.append(view, preview);
          if (viewed.has(outputId)) { view.hidden = true; queueMicrotask(() => showPreview(outputId, preview, id)); }
        }
        if (task.last_error || task.native_registration_ref) {
          const details = node('details'); details.append(node('summary', '查看详情'));
          details.append(node('p', `记录：${task.integration_job_id}`));
          if (task.last_error) details.append(node('p', task.last_error));
          if (task.native_registration_ref) details.append(node('p', `登记：${task.native_registration_ref}`));
          box.append(details);
        }
        if (task.native_registration !== 'registered' && !['registered', 'review_pending', 'canceled', 'failed', 'expired', 'rejected', 'plan_blocked'].includes(task.state)) {
          const button = node('button', '取消这次试用'); button.type = 'button';
          button.onclick = async () => {
            if (!current(id)) return; button.disabled = true;
            try {
              await request(`${api}/tasks/${encodeURIComponent(task.integration_job_id)}/cancel`, { method: 'POST', headers: { 'X-Alchemy-Bridge-Preview': '1' } });
              if (current(id)) await refresh(id);
            } catch (error) { if (current(id)) { notice(failure(error)); button.disabled = false; } }
          }; box.append(button);
        }
        $('tasks').append(box);
      }
      if (!$('tasks').children.length) $('tasks').append(node('p', '还没有试用记录。', 'bridge-hint'));
    } catch (error) {
      if (current(id)) { $('tasks').replaceChildren(); notice(failure(error)); if ([401, 403, 404].includes(error.status)) { ready = false; update(); } }
    } finally { if (current(id)) pollBusy = false; }
  }
  async function submit(event) {
    event.preventDefault(); const id = epoch;
    if (!current(id) || !ready || sending || !$('form').reportValidity()) return;
    const profile = dialog.querySelector('[name="bridge-profile"]:checked')?.value;
    const size = dialog.querySelector('[name="bridge-size"]:checked')?.value;
    const format = $('format').value;
    if (!Object.hasOwn(profiles, profile) || !['1024x1024', '1024x768', '768x1024'].includes(size) || !['png', 'jpeg'].includes(format)) { notice('请选择页面提供的制作方式、形状和格式。'); return; }
    if (profile === 'midjourney-manual' && context.references.length) { notice('人工交回不支持参考图。请先取消参考图选择，或改用本机生成。'); return; }
    if (!$('prompt').value.trim()) { notice('请先写一句文字需求。'); return; }
    const body = { project_id: context.projectId, user_input: $('prompt').value, uploaded_asset_ids: [...context.references],
      profile_id: profile, size, output_format: format, acknowledge_native_development: true };
    sending = true; update();
    try {
      // Save a stable, session/account-bound key before the network effect. No
      // prompt, token or reference bytes are persisted in browser storage.
      const bytes = new TextEncoder().encode(context.session + '\n' + JSON.stringify(body));
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
      if (!current(id)) return;
      const storageKey = `alchemy.bridge.trial.v1.${hash}`;
      let key;
      try { key = sessionStorage.getItem(storageKey) || crypto.randomUUID(); sessionStorage.setItem(storageKey, key); }
      catch { notice('浏览器无法保存本次请求，请允许本页的会话存储后再试，避免重复生成。'); return; }
      body.client_request_id = key;
      await request(`${api}/tasks`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Alchemy-Bridge-Preview': '1' }, body: JSON.stringify(body) });
      if (!current(id)) return;
      notice('请求已保存。可以关闭窗口，稍后回来查看审核进度。'); await refresh(id);
    } catch (error) {
      if (current(id)) {
        if ([401, 403, 404].includes(error.status)) { ready = false; notice(failure(error)); }
        else if ([409, 422].includes(error.status)) notice('这次请求暂不支持，或项目状态已变化。请刷新后检查制作方式和参考图；不会自动降低要求。');
        else notice('提交结果暂未确认。可刷新记录，或保持相同内容再次点击；不会另建一次生成。');
      }
    }
    finally { if (current(id)) { sending = false; update(); } }
  }
  function open(input) {
    build(); close();
    context = { projectId: input.projectId, eligible: Boolean(input.eligible && input.projectId), session: token(), references: [] };
    const id = epoch; abort = new AbortController();
    $('project').textContent = input.title || '当前项目'; $('prompt').value = input.prompt || '';
    $('form').reset(); $('prompt').value = input.prompt || ''; $('profiles').replaceChildren();
    dialog.showModal(); update();
    if (!input.eligible || !input.projectId) {
      notice('目前仅支持标准工作区的通用项目。请打开这类项目后再试；其他页面仍使用原来的生成方式。'); return;
    }
    initialize(id);
    timer = setInterval(() => { if (!document.hidden) refresh(id); }, 5000);
  }
  window.AlchemyBridgeTrial = Object.freeze({ open, close,
    syncProject(projectId) { if (context && context.projectId !== projectId) close(); } });
  window.addEventListener('pagehide', close);
  window.addEventListener('popstate', close);
  window.addEventListener('storage', event => { if (event.key === 'alchemy_veyra_access_token' || event.key === null) close(); });
})();
