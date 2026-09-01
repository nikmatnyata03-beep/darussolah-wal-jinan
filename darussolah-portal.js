/* Shared session guard and portal bootstrap for static HTML pages. */
(() => {
  const metaValue = name => document.querySelector(`meta[name="${name}"]`)?.content.trim() || '';
  const source = window.DARUSSOLAH_CONFIG || {};
  const config = Object.freeze({
    apiBase: String(source.apiBase || metaValue('darussolah-api-base')).replace(/\/+$/, ''),
    supabaseUrl: String(source.supabaseUrl || metaValue('darussolah-supabase-url')).replace(/\/+$/, ''),
    supabaseAnonKey: String(source.supabaseAnonKey || metaValue('darussolah-supabase-anon-key')),
    storageBucket: String(source.storageBucket || 'learning-submissions'),
    tenantSlug: String(source.tenantSlug || 'yayasan-darussolah-wal-jinan')
  });
  const role = document.body?.dataset.portalRole || '';
  const allConfigured = Boolean(config.apiBase && config.supabaseUrl && config.supabaseAnonKey);
  const partiallyConfigured = Boolean(config.apiBase || config.supabaseUrl || config.supabaseAnonKey);
  const roleLabels = {
    wali: 'Wali santri',
    guru: 'Guru / ustadz',
    admin: 'Admin lembaga',
    santri: 'Santri',
    super_admin: 'Admin sistem',
    yayasan_admin: 'Admin yayasan',
    lembaga_admin: 'Admin lembaga',
    operator_pendaftaran: 'Operator pendaftaran'
  };
  const adminRoles = ['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran'];
  const allowedRoles = {
    wali: ['wali', ...adminRoles],
    guru: ['guru', ...adminRoles],
    admin: adminRoles,
    santri: ['santri', ...adminRoles]
  };
  const sessionModeKey = 'dwj-session-mode';
  const sessionStorageForAuth = () => {
    try {
      return localStorage.getItem(sessionModeKey) === 'persistent' ? localStorage : sessionStorage;
    } catch (error) {
      return undefined;
    }
  };

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[character]));
  const initials = value => String(value || 'DWJ').trim().split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
  const setStatus = (text, tone = 'neutral') => {
    let nodes = [...document.querySelectorAll('[data-portal-status], .connection, .status-online')];
    if (!nodes.length) {
      const host = document.querySelector('.topbar-actions');
      if (host) {
        const node = document.createElement('span');
        node.className = 'portal-runtime-status';
        host.prepend(node);
        nodes = [node];
      }
    }
    nodes.forEach(node => {
      node.textContent = text;
      node.dataset.portalTone = tone;
    });
  };
  const setIdentity = (context, session, primaryClass) => {
    const profile = context?.profile || {};
    const name = profile.full_name || session?.user?.email || 'Pengguna portal';
    const roles = context?.roles || [];
    const activeRole = roles.find(item => (allowedRoles[role] || []).includes(item)) || roles[0] || role;
    const membership = context?.memberships?.find(item => item.institution_id === primaryClass?.institution_id) || context?.memberships?.[0];
    document.querySelectorAll('.user-card strong, [data-portal-user-name]').forEach(node => { node.textContent = name; });
    document.querySelectorAll('.user-card strong + span, [data-portal-user-role]').forEach(node => { node.textContent = roleLabels[activeRole] || activeRole || 'Pengguna'; });
    document.querySelectorAll('.user-avatar, .top-avatar, [data-portal-user-initials]').forEach(node => { node.textContent = initials(name); });
    if (membership) {
      document.querySelectorAll('.sidebar-context .context-name, [data-portal-institution]').forEach(node => { node.textContent = membership.name || membership.code; });
    }
    document.querySelectorAll('[data-portal-student-count]').forEach(node => { node.textContent = String(context.studentCount ?? node.textContent); });
    document.querySelectorAll('[data-portal-class-count]').forEach(node => { node.textContent = String(context.classCount ?? node.textContent); });
  };
  const activeClassStorageKey = session => `dwj-active-class-${session?.user?.id || 'anonymous'}`;
  const readActiveClassId = session => {
    try { return sessionStorage.getItem(activeClassStorageKey(session)) || ''; } catch (error) { return ''; }
  };
  const rememberActiveClassId = (session, classId) => {
    try { sessionStorage.setItem(activeClassStorageKey(session), classId); } catch (error) { /* Storage can be unavailable in private browsing. */ }
  };
  const addClassPicker = (classes, primaryClass, session) => {
    const host = document.querySelector('.topbar-actions');
    if (!host || role !== 'guru' || document.body.dataset.portalPage !== 'learning' || classes.length < 2) return;
    let picker = host.querySelector('[data-portal-class-picker]');
    if (!picker) {
      picker = document.createElement('select');
      picker.className = 'portal-runtime-class-picker';
      picker.dataset.portalClassPicker = 'true';
      picker.setAttribute('aria-label', 'Pilih kelas aktif');
      picker.addEventListener('change', () => {
        rememberActiveClassId(session, picker.value);
        const url = new URL(window.location.href);
        url.searchParams.set('class_id', picker.value);
        window.location.assign(url.href);
      });
      host.prepend(picker);
    }
    picker.replaceChildren(...classes.map(item => new Option(`${item.institution_code || ''} - ${item.name || item.code}`, item.id)));
    picker.value = primaryClass?.id || '';
  };
  const addSignOut = client => {
    if (document.querySelector('[data-portal-sign-out]')) return;
    const host = document.querySelector('.topbar-actions');
    if (!host) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Keluar';
    button.dataset.portalSignOut = 'true';
    button.className = 'portal-runtime-signout';
    button.addEventListener('click', async () => {
      button.disabled = true;
      await client.auth.signOut();
      try {
        localStorage.removeItem(sessionModeKey);
        sessionStorage.removeItem(sessionModeKey);
        localStorage.removeItem('dwj-ui-role');
        sessionStorage.removeItem('dwj-ui-role');
      } catch (error) { /* Storage can be unavailable in private browsing. */ }
      window.location.replace('login.html');
    });
    host.append(button);
  };
  const showBlocked = (title, detail, { showLogin = false } = {}) => {
    document.documentElement.dataset.dwjPortalState = 'blocked';
    document.querySelector('.portal-runtime-blocker')?.remove();
    const overlay = document.createElement('div');
    overlay.className = 'portal-runtime-blocker';
    overlay.innerHTML = `<div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span><button type="button" data-portal-retry>Coba lagi</button>${showLogin ? '<a href="login.html">Buka halaman login</a>' : ''}</div>`;
    overlay.querySelector('[data-portal-retry]').addEventListener('click', () => window.location.reload());
    document.body.append(overlay);
  };
  const injectStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
      .portal-runtime-status { color: #748079; font: 600 10px/1.2 "DM Sans", sans-serif; }
      .portal-runtime-status[data-portal-tone="live"] { color: #3f8b62; }
      .portal-runtime-status[data-portal-tone="error"] { color: #ae5b47; }
      .portal-runtime-signout { padding: 6px 9px; color: #0d4433; border: 1px solid #e0e4dc; border-radius: 7px; background: #fffdf9; font: 700 10px/1 "DM Sans", sans-serif; }
       .portal-runtime-signout:hover { border-color: #0d4433; }
       .portal-runtime-class-picker { max-width: 175px; height: 29px; padding: 0 7px; color: #0d4433; border: 1px solid #e0e4dc; border-radius: 7px; background: #fffdf9; font: 600 10px "DM Sans", sans-serif; }
       html[data-dwj-portal-state="checking"] body > .app-shell { opacity: .35; pointer-events: none; }
       @media (max-width: 820px) { .side-link, .row-action, .mini-button, .portal-runtime-signout { min-height: 36px; } }
      .portal-runtime-blocker { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; padding: 24px; background: rgba(8,46,37,.96); color: #fff; text-align: center; }
      .portal-runtime-blocker div { width: min(100%, 380px); padding: 28px; border: 1px solid rgba(232,200,121,.3); border-radius: 16px; background: #0d4433; box-shadow: 0 22px 60px rgba(0,0,0,.25); }
      .portal-runtime-blocker strong, .portal-runtime-blocker span { display: block; }
      .portal-runtime-blocker strong { color: #e8c879; font: 400 28px/1.05 Georgia, serif; }
      .portal-runtime-blocker span { margin-top: 12px; color: rgba(255,255,255,.72); font: 12px/1.5 "DM Sans", sans-serif; }
       .portal-runtime-blocker button, .portal-runtime-blocker a { display: inline-flex; margin-top: 20px; padding: 11px 16px; border: 0; border-radius: 8px; color: #082e25; background: #e8c879; font: 700 11px/1 "DM Sans", sans-serif; }
       .portal-runtime-blocker button { cursor: pointer; }
       .portal-runtime-blocker a { margin-left: 8px; }
    `;
    document.head.append(style);
  };
  const privatePath = suffix => `${config.apiBase}/v1/private/${encodeURIComponent(config.tenantSlug)}/${suffix}`;
  const wait = milliseconds => new Promise(resolve => window.setTimeout(resolve, milliseconds));
  const retryableStatus = status => [408, 425, 429].includes(status) || status >= 500;
  const requestPrivate = async (client, suffix, session, options = {}) => {
    let activeSession = session;
    let refreshed = false;
    let lastError = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const current = await client?.auth?.getSession?.();
        activeSession = current?.data?.session || activeSession;
      } catch (error) {
        // The request below can still use the session captured during bootstrap.
      }
      if (!activeSession?.access_token) throw new Error('sesi tidak tersedia');
      try {
        const response = await fetch(privatePath(suffix), {
          ...options,
          headers: {
            Authorization: `Bearer ${activeSession.access_token}`,
            Accept: 'application/json',
            ...(options.headers || {})
          }
        });
        if (response.status === 401 && !refreshed) {
          const refreshedSession = await client.auth.refreshSession();
          activeSession = refreshedSession.data?.session || null;
          refreshed = true;
          if (activeSession?.access_token) continue;
        }
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          const error = new Error(body.detail || `private API returned ${response.status}`);
          error.retryable = retryableStatus(response.status);
          error.authRequired = response.status === 401;
          throw error;
        }
        return response.json();
      } catch (error) {
        lastError = error;
        if (!error.retryable && !(error instanceof TypeError)) throw error;
        if (attempt < 2) await wait(250 * (attempt + 1));
      }
    }
    throw lastError || new Error('koneksi ke API belum tersedia');
  };
  const fetchPrivate = (client, suffix, session) => requestPrivate(client, suffix, session);
  const start = async () => {
    injectStyles();
    if (!partiallyConfigured) {
      setStatus('Mode demo');
      return;
    }
    if (!allConfigured || !window.supabase?.createClient) {
      setStatus('Konfigurasi belum lengkap', 'error');
      showBlocked('Portal belum siap', 'Isi API URL, Supabase URL, dan anon key pada darussolah-config.js.');
      return;
    }
    document.documentElement.dataset.dwjPortalState = 'checking';
     const client = window.supabase.createClient(config.supabaseUrl, config.supabaseAnonKey, {
       auth: { persistSession: true, storage: sessionStorageForAuth() }
     });
    let sessionData;
    let sessionError;
    try {
      ({ data: sessionData, error: sessionError } = await client.auth.getSession());
    } catch (error) {
      setStatus('Sesi belum siap', 'error');
      showBlocked('Sesi belum siap', 'Koneksi sesi belum siap. Coba lagi tanpa keluar dari akun.');
      return;
    }
    if (sessionError) {
      setStatus('Sesi belum siap', 'error');
      showBlocked('Sesi belum siap', 'Koneksi sesi belum siap. Coba lagi tanpa keluar dari akun.');
      return;
    }
    if (!sessionData.session) {
      const redirect = `${window.location.pathname.split('/').pop() || 'index.html'}${window.location.search}`;
      window.location.replace(`login.html?redirect=${encodeURIComponent(redirect)}`);
      return;
    }
    try {
      const session = sessionData.session;
      const [meResponse, studentsResponse, classesResponse] = await Promise.all([
        fetchPrivate(client, 'me', session),
        fetchPrivate(client, 'students', session),
        fetchPrivate(client, 'classes', session)
      ]);
      let attendanceResponse = null;
      let learningResponse = null;
      let learningSubmissionsResponse = null;
       const classes = classesResponse.items || [];
       const supportsClassSelection = role === 'guru' && document.body.dataset.portalPage === 'learning';
       const requestedClassId = supportsClassSelection
         ? new URLSearchParams(window.location.search).get('class_id') || readActiveClassId(session)
         : '';
       const primaryClass = classes.find(item => item.id === requestedClassId)
         || classes.find(item => item.institution_code === 'TPQ')
         || classes[0];
       if (primaryClass && supportsClassSelection) rememberActiveClassId(session, primaryClass.id);
      if (document.body.dataset.portalPage === 'attendance' && primaryClass) {
        try {
          attendanceResponse = await fetchPrivate(
            client,
            `attendance?class_id=${encodeURIComponent(primaryClass.id)}&attendance_date=${new Date().toISOString().slice(0, 10)}`,
            session
          );
        } catch (error) {
          attendanceResponse = null;
        }
      }
      if (document.body.dataset.portalPage === 'learning') {
        const suffix = role === 'wali'
          ? 'learning'
          : primaryClass ? `learning?class_id=${encodeURIComponent(primaryClass.id)}` : 'learning';
        learningResponse = await fetchPrivate(client, suffix, session);
        const submissionsSuffix = role === 'wali'
          ? 'learning/submissions'
          : primaryClass
          ? `learning/submissions?class_id=${encodeURIComponent(primaryClass.id)}`
          : 'learning/submissions';
        learningSubmissionsResponse = await fetchPrivate(client, submissionsSuffix, session);
      }
      const context = {
        ...(meResponse.user || {}),
        studentCount: studentsResponse.items?.length || 0,
        classCount: classesResponse.items?.length || 0
      };
      const actualRoles = context.roles || [];
      if (role && actualRoles.length && !(allowedRoles[role] || []).some(item => actualRoles.includes(item))) {
        throw new Error('akun tidak memiliki peran untuk halaman ini');
      }
       setIdentity(context, session, primaryClass);
       setStatus('Akun terhubung', 'live');
        addSignOut(client);
        addClassPicker(classes, primaryClass, session);
        document.querySelector('.side-link.active, [aria-current="page"]')?.scrollIntoView({ block: 'nearest', inline: 'center' });
       document.documentElement.dataset.dwjPortalState = 'live';
       const students = studentsResponse.items || [];
       window.DarussolahPortal = Object.freeze({
         client, config, session, context, students, classes, primaryClass, requestPrivate,
        attendance: attendanceResponse,
        learning: learningResponse?.items || [],
        learningSubmissions: learningSubmissionsResponse?.items || [],
      });
      window.dispatchEvent(new CustomEvent('darussolah:ready', {
        detail: {
          students,
          classes,
          attendance: attendanceResponse,
          learning: learningResponse?.items || [],
          learningSubmissions: learningSubmissionsResponse?.items || []
        }
      }));
    } catch (error) {
      document.documentElement.dataset.dwjPortalState = 'blocked';
      setStatus('Gagal memuat akun', 'error');
       showBlocked('Data belum dapat dimuat', error.message || 'Periksa koneksi dan konfigurasi API.', { showLogin: Boolean(error.authRequired) });
    }
  };

  window.DarussolahPortal = Object.freeze({ config, start, fetchPrivate, requestPrivate });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
