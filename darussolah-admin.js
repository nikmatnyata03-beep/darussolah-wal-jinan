/* Live data and actions for the management workspace. */
(() => {
  const page = window.location.pathname.split('/').pop() || '';
  const managed = new Set(['absensi.html', 'santri.html', 'materi.html', 'kepegawaian.html', 'tahfidz.html', 'nilai.html', 'keuangan.html', 'cms.html', 'analitik.html', 'notifikasi.html', 'pengaturan.html']);
  if (!managed.has(page)) return;
  const state = { students: [], classes: [], staff: [], records: {}, content: [] };
  let installPrompt = null;
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; });
  const portal = () => window.DarussolahPortal;
  const safe = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const initials = value => String(value || 'SN').trim().split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
  const toast = (title, detail) => {
    const node = document.getElementById('toast');
    if (!node) return;
    const titleNode = node.querySelector('#toastTitle, #toast-title');
    const detailNode = node.querySelector('#toastText, #toast-detail');
    if (titleNode) titleNode.textContent = title;
    if (detailNode) detailNode.textContent = detail;
    node.classList.add('show');
    window.clearTimeout(node._timer);
    node._timer = window.setTimeout(() => node.classList.remove('show'), 3600);
  };
  const api = (suffix, options = {}) => {
    const p = portal();
    if (!p?.requestPrivate) return Promise.reject(new Error('sesi portal belum siap'));
    return p.requestPrivate(p.client, suffix, p.session, options);
  };
  const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const closeModal = id => { const modal = document.getElementById(id); if (modal) { modal.hidden = true; modal.setAttribute('aria-hidden', 'true'); } };
  const openModal = id => { const modal = document.getElementById(id); if (modal) { modal.hidden = false; modal.setAttribute('aria-hidden', 'false'); modal.querySelector('input,textarea')?.focus(); } };
  const download = (name, text, type = 'text/csv;charset=utf-8') => {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([text], { type }));
    link.download = name; link.click(); URL.revokeObjectURL(link.href);
  };
  const csv = rows => rows.map(row => row.map(value => `"${String(value ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
  const fmtMoney = value => new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(Number(value) || 0);
  const fmtDate = value => value ? new Intl.DateTimeFormat('id-ID', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value)) : '—';
  const records = async module => {
    const response = await api(`admin/records?module=${encodeURIComponent(module)}`);
    state.records[module] = response.items || [];
    return state.records[module];
  };
  const saveRecord = (module, recordKey, payload, entityId = null) => api('admin/records', json('POST', { module, record_key: recordKey, entity_id: entityId, payload }));
  const institutions = () => {
    const list = [];
    state.classes.forEach(item => { if (item.institution_id && !list.some(existing => existing.id === item.institution_id)) list.push({ id: item.institution_id, name: item.institution_name || item.institution_code }); });
    return list;
  };

  async function loadStudents() {
    const response = await api('admin/students');
    state.students = response.items || [];
    const classSelect = document.getElementById('studentClass');
    if (classSelect && state.classes.length) classSelect.innerHTML = state.classes.map(item => `<option value="${safe(item.id)}">${safe(item.name || item.code)}</option>`).join('');
    renderStudents();
  }
  function renderStudents() {
    const rows = document.getElementById('studentRows');
    if (!rows) return;
    rows.innerHTML = state.students.map(student => {
      const complete = Boolean(student.guardian_connected);
      const status = student.status === 'active' ? 'Aktif' : student.status || 'Belum aktif';
      return `<tr data-status="${safe(student.status)}"><td><div class="student-cell"><span class="payer-avatar">${safe(initials(student.full_name))}</span><span class="student-detail">${safe(student.full_name)}<small>${safe(student.nis || student.id)}</small></span></div></td><td>${safe(student.class_name || 'Belum ditempatkan')}</td><td>${safe(student.guardian_name || 'Belum dihubungkan')}</td><td><span class="status-pill${student.status === 'active' ? '' : ' pending'}">${safe(status)}</span></td><td><span class="status-pill${complete ? '' : ' pending'}">${complete ? 'Lengkap' : 'Kurang'}</span></td><td><button class="row-action" type="button" data-live-student="${safe(student.id)}">Detail</button></td></tr>`;
    }).join('') || '<tr><td colspan="6">Belum ada data santri.</td></tr>';
    const total = state.students.length;
    const active = state.students.filter(item => item.status === 'active').length;
    const linked = state.students.filter(item => item.guardian_connected).length;
    document.getElementById('studentTotal')?.replaceChildren(document.createTextNode(String(total)));
    document.getElementById('activeTotal')?.replaceChildren(document.createTextNode(String(active)));
    document.getElementById('guardianTotal')?.replaceChildren(document.createTextNode(String(linked)));
    const activeFoot = document.getElementById('activeFoot'); if (activeFoot) activeFoot.textContent = `${total ? ((active / total) * 100).toFixed(1).replace('.', ',') : '0'}% dari total`;
    const guardianFoot = document.getElementById('guardianFoot'); if (guardianFoot) guardianFoot.textContent = `${total - linked} perlu dilengkapi`;
    const chip = document.getElementById('studentChip'); if (chip) chip.textContent = `${total} santri`;
  }

  async function loadStaff() {
    const response = await api('admin/staff'); state.staff = response.items || [];
    const select = document.getElementById('staffUnit');
    if (select && institutions().length) select.innerHTML = institutions().map(item => `<option value="${safe(item.id)}">${safe(item.name)}</option>`).join('');
    renderStaff();
  }
  function renderStaff() {
    const rows = document.getElementById('staffRows'); if (!rows) return;
    rows.innerHTML = state.staff.map(item => `<tr data-staff="${safe(item.employment_type || 'fixed')}"><td><div class="teacher-cell"><span class="teacher-avatar">${safe(initials(item.display_name))}</span><span class="teacher-detail">${safe(item.display_name)}<small>${safe(item.institution_name || '')}</small></span></div></td><td><span class="qualification">${safe(item.education || 'Belum diisi')}<small>${safe(item.subject || item.role_title || '')}</small></span></td><td><span class="employment">${item.employment_type === 'honor' ? 'Honorer' : 'Tetap'}</span></td><td class="jtm-number">${Number(item.weekly_hours) || 0} jam</td><td class="attendance-good">—</td><td><button class="row-action" type="button" data-live-staff="${safe(item.id)}">Detail</button></td></tr>`).join('') || '<tr><td colspan="6">Belum ada data guru.</td></tr>';
    const active = state.staff.filter(item => item.status === 'active').length;
    const hours = state.staff.reduce((sum, item) => sum + (Number(item.weekly_hours) || 0), 0);
    const values = document.querySelectorAll('.metrics-grid .metric-value'); if (values[0]) values[0].textContent = String(active); if (document.getElementById('jtmMetric')) document.getElementById('jtmMetric').textContent = String(hours);
    const chip = document.querySelector('#staffHeading')?.closest('.panel')?.querySelector('.data-chip'); if (chip) chip.textContent = `${active} guru aktif`;
  }

  async function loadTahfidz() {
    await records('tahfidz');
    const list = document.getElementById('student-list'); if (!list) return;
    const latest = new Map(); (state.records.tahfidz || []).forEach(item => { if (!latest.has(item.entity_id)) latest.set(item.entity_id, item.payload || {}); });
    list.innerHTML = state.students.map(student => { const item = latest.get(student.id) || {}; const stage = item.stage || 'setoran'; const progress = Math.max(0, Math.min(100, Number(item.progress) || 0)); return `<article class="student-card" data-name="${safe(student.full_name.toLowerCase())}" data-stage="${safe(stage)}" data-student="${safe(student.full_name)}" data-student-id="${safe(student.id)}"><span class="student-avatar">${safe(initials(student.full_name))}</span><span><strong class="student-name">${safe(student.full_name)}</strong><span class="student-sub">${safe(item.kind || 'Tahfidz')} · ${safe(item.target || 'Belum ada setoran')}</span><span class="stage-chip${stage === 'murojaah' ? ' warn' : ''}">${stage === 'murojaah' ? 'Perlu murojaah' : 'Siap dicatat'}</span></span><span class="progress-copy"><span class="progress-line"><span>Progres</span><strong>${progress}%</strong></span><span class="track"><span class="fill" style="width:${progress}%"></span></span></span><button class="student-action" type="button" data-live-record-student="${safe(student.id)}">Catat <span>→</span></button></article>`; }).join('');
    const select = document.getElementById('record-student'); if (select) select.innerHTML = state.students.map(student => `<option value="${safe(student.id)}">${safe(student.full_name)}</option>`).join('');
    const review = (state.records.tahfidz || []).filter(item => item.payload?.stage === 'murojaah').length; const reviewNode = document.getElementById('review-count'); if (reviewNode) reviewNode.textContent = String(review).padStart(2, '0');
    const query = document.getElementById('student-search')?.value.trim().toLowerCase() || ''; list.querySelectorAll('.student-card').forEach(card => { card.hidden = Boolean(query) && !card.dataset.name.includes(query); });
  }
  async function loadGrades() {
    await records('grades');
    const classSelect = document.getElementById('class-select'); if (classSelect && state.classes.length) classSelect.innerHTML = state.classes.map(item => `<option value="${safe(item.id)}">${safe(item.name || item.code)} · ${safe(item.institution_code || '')}</option>`).join('');
    renderGrades();
  }
  function gradeKey(studentId) { return `grades:${studentId}:${document.getElementById('class-select')?.value || 'all'}:${document.getElementById('term-select')?.value || 'term-1'}`; }
  function renderGrades() {
    const rows = document.getElementById('grade-rows'); if (!rows) return;
    const map = new Map((state.records.grades || []).map(item => [item.record_key, item]));
    rows.innerHTML = state.students.map(student => { const item = map.get(gradeKey(student.id)); const scores = item?.payload?.scores || {}; const needs = ['tahsin', 'tahfidz', 'adab'].some(subject => scores[subject] !== undefined && Number(scores[subject]) < 75); return `<tr data-student-id="${safe(student.id)}" data-needs="${needs}"><td><div class="student-cell"><span class="student-avatar">${safe(initials(student.full_name))}</span><span class="student-detail">${safe(student.full_name)}<small>${safe(student.class_name || '')}</small></span></div></td>${['tahsin', 'tahfidz', 'adab'].map(subject => `<td><input class="score-input${Number(scores[subject]) < 75 ? ' low' : ''}" type="number" min="0" max="100" value="${scores[subject] ?? ''}" data-grade-subject="${subject}" data-student-id="${safe(student.id)}" /></td>`).join('')}<td>—</td><td><span class="status-pill${needs ? ' needs-review' : ''}">${needs ? 'Perlu perhatian' : 'Belum dinilai'}</span></td><td><button class="note-button" type="button" data-live-note="${safe(student.id)}">…</button></td></tr>`; }).join('');
    const inputs = [...document.querySelectorAll('[data-grade-subject]')]; const saved = inputs.filter(input => input.value !== '').length; const passed = inputs.filter(input => input.value !== '' && Number(input.value) >= 75).length; if (document.getElementById('saved-count')) document.getElementById('saved-count').textContent = String(saved); if (document.getElementById('kkm-rate')) document.getElementById('kkm-rate').textContent = `${inputs.length ? Math.round((passed / inputs.length) * 100) : 0}%`;
  }

  async function loadFinance() {
    await records('finance'); renderFinance();
  }
  function renderFinance() {
    const items = state.records.finance || [], invoices = items.filter(item => item.payload?.type === 'invoice'), transactions = items.filter(item => item.payload?.type !== 'invoice');
    const bills = document.getElementById('billRows'); if (bills) bills.innerHTML = invoices.map(item => { const p = item.payload || {}; const status = p.status || 'pending'; return `<tr data-status="${safe(status)}"><td><div class="payer-cell"><span class="payer-avatar">${safe(initials(p.student_name || p.payer_name))}</span><span class="payer-detail">${safe(p.student_name || 'Santri')}<small>Wali: ${safe(p.guardian_name || 'Belum dihubungkan')}</small></span></div></td><td>${safe(fmtDate(p.due_date))}</td><td class="amount">${safe(fmtMoney(p.amount))}</td><td><span class="status-pill${status === 'paid' ? '' : ' pending'}">${status === 'paid' ? 'Lunas' : status === 'overdue' ? 'Terlambat' : 'Menunggu'}</span></td><td><button class="pay-button" type="button" data-live-finance="${safe(item.id)}" data-action="${status === 'paid' ? 'receipt' : 'remind'}">${status === 'paid' ? 'Kwitansi' : 'Ingatkan'}</button></td></tr>`; }).join('') || '<tr><td colspan="5">Belum ada tagihan tersimpan.</td></tr>';
    const table = document.querySelectorAll('.bill-table')[1]; if (table) table.querySelector('tbody').innerHTML = transactions.map(item => { const p = item.payload || {}; return `<tr><td><div class="payer-cell"><span class="payer-avatar">${safe(initials(p.payer_name || p.program))}</span><span class="payer-detail">${safe(p.description || p.program || 'Transaksi')}<small>${safe(item.record_key)}</small></span></div></td><td>${safe(fmtDate(item.created_at))}</td><td>${safe(p.method || 'Manual')}</td><td class="amount">+ ${safe(fmtMoney(p.amount))}</td><td><span class="status-pill">Tercatat</span></td></tr>`; }).join('') || '<tr><td colspan="5">Belum ada transaksi.</td></tr>';
    const income = transactions.reduce((sum, item) => sum + (Number(item.payload?.amount) || 0), 0); const billed = invoices.reduce((sum, item) => sum + (Number(item.payload?.amount) || 0), 0); const overdue = invoices.filter(item => item.payload?.status === 'overdue').length; const donation = transactions.filter(item => item.payload?.type === 'donation').reduce((sum, item) => sum + (Number(item.payload?.amount) || 0), 0);
    const set = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = value; }; set('incomeValue', fmtMoney(income)); set('billedValue', fmtMoney(billed)); set('overdueValue', String(overdue)); set('donationValue', fmtMoney(donation));
  }

  async function loadCms() {
    const response = await api('admin/content'); state.content = response.items || [];
    const rows = document.getElementById('contentRows'); if (!rows) return;
    rows.innerHTML = state.content.map((item, index) => `<tr data-content="${safe(item.status)}"><td><div class="article-cell"><span class="article-thumb">${String(index + 1).padStart(2, '0')}</span><span class="article-copy">${safe(item.title)}<small>${safe(fmtDate(item.updated_at))}</small></span></div></td><td><span class="type-label">${safe(item.content_type)}</span></td><td>${safe(item.institution_name || 'Yayasan')}</td><td><span class="publish-pill${item.status === 'draft' ? ' draft' : ''}">${item.status === 'published' ? 'Tayang' : item.status === 'archived' ? 'Arsip' : 'Draft'}</span></td><td><button class="row-action" type="button" data-live-content="${safe(item.id)}">Edit</button></td></tr>`).join('') || '<tr><td colspan="5">Belum ada konten.</td></tr>';
    const chip = document.querySelector('#libraryHeading')?.closest('.panel')?.querySelector('.data-chip'); if (chip) chip.textContent = `${state.content.length} konten`;
  }
  async function loadNotifications() {
    await records('notifications'); await records('calendar'); await records('settings');
    const rows = document.getElementById('deliveryRows'); if (!rows) return;
    rows.innerHTML = (state.records.notifications || []).map(item => { const p = item.payload || {}; const delivery = p.status || 'sent'; return `<tr data-delivery="${safe(delivery)}"><td><div class="message-cell"><span class="message-icon">${p.channel === 'email' ? '@' : 'WA'}</span><span class="message-detail">${safe(p.title || 'Pesan')}<small>${safe(p.target || 'Penerima')} · ${safe(p.mode || 'Manual')}</small></span></div></td><td>${safe(p.target || '—')}</td><td>${safe(fmtDate(item.created_at))}</td><td>${safe(p.read_rate || '—')}</td><td><span class="delivery-status${delivery === 'scheduled' ? ' scheduled' : ''}">${delivery === 'scheduled' ? 'Terjadwal' : delivery === 'failed' ? 'Gagal' : 'Berhasil'}</span></td></tr>`; }).join('') || '<tr><td colspan="5">Belum ada riwayat pengiriman.</td></tr>';
    const sent = (state.records.notifications || []).filter(item => item.payload?.status !== 'scheduled').length; const sentNode = document.getElementById('sentValue'); if (sentNode) sentNode.textContent = String(sent); const rules = (state.records.settings || []).filter(item => item.payload?.type === 'notification_rule' && item.payload?.enabled).length; const ruleNode = document.getElementById('ruleValue'); if (ruleNode) ruleNode.textContent = String(rules).padStart(2, '0');
  }
  async function loadAnalytics() {
    const summary = await api('admin/summary');
    const set = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = value; };
    set('studentTotal', summary.students_active ?? 0); set('admissionTotal', summary.registrations_pending ?? 0);
    const finance = await records('finance'); const income = (finance || []).filter(item => item.payload?.type !== 'invoice').reduce((sum, item) => sum + (Number(item.payload?.amount) || 0), 0); set('incomeTotal', fmtMoney(income));
    const attendance = summary.attendance_sessions_today ? 'Tercatat' : 'Belum ada'; set('attendanceTotal', attendance);
    const scope = document.getElementById('scopeSelect'); if (scope) { scope.innerHTML = '<option value="all">Seluruh yayasan</option>' + (state.classes || []).map(item => `<option value="${safe(item.id)}">${safe(item.name)}</option>`).join(''); }
  }
  async function loadSettingsPage() {
    await records('alumni');
    const list = document.querySelector('.alumni-list'); if (!list) return;
    list.innerHTML = (state.records.alumni || []).map(item => { const p = item.payload || {}; return `<article class="alumni-card"><div class="alumni-top"><span class="alumni-avatar">${safe(initials(p.name))}</span><span><strong>${safe(p.name)}</strong><small>Angkatan ${safe(p.year)} · ${safe(p.unit)}</small></span></div><span class="alumni-note">${safe(p.note || 'Profil alumni tersimpan di direktori.')}</span><span class="alumni-action">Profil tersimpan</span></article>`; }).join('') || '<p>Belum ada profil alumni.</p>';
  }
  async function exportModule(module, name, rows) {
    try { const data = rows || (await records(module)); download(name, csv(data.map(item => [item.id, item.record_key, JSON.stringify(item.payload), item.status, item.updated_at]))); toast('Ekspor selesai', 'File rekap berhasil diunduh.'); } catch (error) { toast('Ekspor gagal', error.message); }
  }
  async function saveGrade(input) {
    const row = input.closest('tr'); const studentId = input.dataset.studentId; const scores = {}; row.querySelectorAll('[data-grade-subject]').forEach(item => { scores[item.dataset.gradeSubject] = item.value === '' ? null : Number(item.value); });
    try { const saved = await saveRecord('grades', gradeKey(studentId), { scores, approval_status: 'draft' }, studentId); const existing = state.records.grades.findIndex(item => item.record_key === saved.record_key); if (existing >= 0) state.records.grades[existing] = saved; else state.records.grades.unshift(saved); input.classList.toggle('low', Number(input.value) < 75); toast('Nilai tersimpan', 'Perubahan sudah tersimpan ke server.'); renderGrades(); } catch (error) { toast('Nilai belum tersimpan', error.message); }
  }
  async function handleSubmit(event) {
    const form = event.target; if (!(form instanceof HTMLFormElement)) return;
    if (form.id === 'studentForm') { event.preventDefault(); event.stopImmediatePropagation(); const payload = { full_name: document.getElementById('studentName').value.trim(), nis: document.getElementById('studentNis').value.trim() || null, status: 'active', class_id: document.querySelector('#studentClass')?.value || null, guardian_name: document.getElementById('studentGuardian').value.trim() || null }; try { await api('admin/students', json('POST', payload)); closeModal('studentModal'); await loadStudents(); toast('Santri tersimpan', 'Data induk sudah masuk ke server.'); } catch (error) { toast('Santri belum tersimpan', error.message); } return; }
    if (form.id === 'staffForm') { event.preventDefault(); event.stopImmediatePropagation(); const payload = { display_name: document.getElementById('staffName').value.trim(), education: document.getElementById('staffQualification').value.trim(), employment_type: document.getElementById('staffStatus').value, institution_id: document.getElementById('staffUnit').value, weekly_hours: Number(document.getElementById('staffJtm').value) || 0, status: 'active' }; try { await api('admin/staff', json('POST', payload)); closeModal('staffModal'); await loadStaff(); toast('Guru tersimpan', 'Data kepegawaian sudah masuk ke server.'); } catch (error) { toast('Guru belum tersimpan', error.message); } return; }
    if (form.id === 'record-form') { event.preventDefault(); event.stopImmediatePropagation(); const studentId = document.getElementById('record-student').value; const score = document.querySelector('[data-score].active')?.dataset.score || 'lancar'; const payload = { kind: document.querySelector('[data-kind].active')?.dataset.kind === 'tahsin' ? 'Tahsin' : 'Tahfidz', target: document.getElementById('record-target').value.trim(), score, stage: ['bimbingan', 'ulang'].includes(score) ? 'murojaah' : 'setoran', note: document.getElementById('record-note').value.trim(), progress: 0, recorded_at: new Date().toISOString() }; try { await saveRecord('tahfidz', `${studentId}:${Date.now()}`, payload, studentId); await loadTahfidz(); toast('Capaian tersimpan', 'Setoran sudah tercatat di server.'); } catch (error) { toast('Capaian belum tersimpan', error.message); } return; }
    if (form.id === 'invoiceForm' || form.id === 'donationForm') { event.preventDefault(); event.stopImmediatePropagation(); const invoice = form.id === 'invoiceForm'; const payload = invoice ? { type: 'invoice', student_name: document.getElementById('studentName').value.trim(), amount: Number(document.getElementById('invoiceAmount').value), due_date: document.getElementById('invoiceDue').value, category: document.getElementById('invoiceType').value, status: 'pending' } : { type: 'donation', payer_name: document.getElementById('donorName').value.trim(), amount: Number(document.getElementById('donationAmount').value), program: document.getElementById('donationProgram').value, description: `Donasi ${document.getElementById('donationProgram').value}`, method: 'Manual' }; try { await saveRecord('finance', `${payload.type}:${Date.now()}`, payload); closeModal(invoice ? 'invoiceModal' : 'donationModal'); await loadFinance(); toast(invoice ? 'Tagihan tersimpan' : 'Donasi tersimpan', 'Catatan keuangan sudah tersimpan.'); } catch (error) { toast('Transaksi belum tersimpan', error.message); } return; }
    if (form.id === 'articleForm') { event.preventDefault(); event.stopImmediatePropagation(); const status = document.getElementById('articlePublish').value === 'publish' ? 'published' : 'draft'; const payload = { site_kind: 'foundation', content_type: document.getElementById('articleType').value, slug: document.getElementById('articleName').value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''), title: document.getElementById('articleName').value.trim(), body: document.getElementById('articleCopy').value.trim(), status }; try { if (state.editingContent) await api(`admin/content/${state.editingContent}`, json('PUT', payload)); else await api('admin/content', json('POST', payload)); state.editingContent = null; closeModal('articleModal'); await loadCms(); toast('Konten tersimpan', 'Konten publik sudah tersimpan sebagai draft atau tayang.'); } catch (error) { toast('Konten belum tersimpan', error.message); } return; }
    if (form.id === 'mediaForm') { event.preventDefault(); event.stopImmediatePropagation(); const file = document.getElementById('mediaFile').files[0]; const payload = { type: 'media', filename: file?.name || '', category: document.getElementById('mediaCategory').value.trim(), size: file?.size || 0 }; try { let fileUrl = ''; const p = portal(); if (file && p?.client?.storage) { const path = `${p.context?.profile?.tenant_id || 'tenant'}/${Date.now()}-${file.name.replace(/[^a-zA-Z0-9._-]/g, '-')}`; const upload = await p.client.storage.from('site-media').upload(path, file, { upsert: false }); if (upload.error) throw upload.error; fileUrl = p.client.storage.from('site-media').getPublicUrl(path).data.publicUrl; } await saveRecord('media', `media:${Date.now()}`, { ...payload, file_url: fileUrl }); closeModal('mediaModal'); toast('Media tersimpan', 'File media dan metadata sudah tersimpan.'); } catch (error) { toast('Media belum tersimpan', error.message); } return; }
    if (form.id === 'pageForm' || form.id === 'bannerForm') { event.preventDefault(); event.stopImmediatePropagation(); const pageForm = form.id === 'pageForm'; const title = document.getElementById(pageForm ? 'pageName' : 'bannerName').value.trim(); const body = pageForm ? document.getElementById('pageCopy').value.trim() : ''; const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); const payload = { site_kind: 'foundation', content_type: pageForm ? 'page' : 'banner', slug, title, body, excerpt: pageForm ? '' : document.getElementById('bannerCta').value.trim(), status: pageForm || document.getElementById('bannerStatus').value === 'Aktif' ? 'published' : 'draft' }; try { await api('admin/content', json('POST', payload)); closeModal(pageForm ? 'pageModal' : 'bannerModal'); await loadCms(); toast('Konten tersimpan', 'Perubahan CMS sudah masuk ke database.'); } catch (error) { toast('Konten belum tersimpan', error.message); } return; }
    if (form.id === 'broadcastForm') { event.preventDefault(); event.stopImmediatePropagation(); openModal('previewModal'); return; }
    if (form.id === 'calendarForm') { event.preventDefault(); event.stopImmediatePropagation(); const payload = { type: 'calendar', title: document.getElementById('eventName').value.trim(), date: document.getElementById('eventDate').value }; try { await saveRecord('calendar', `calendar:${Date.now()}`, payload); closeModal('calendarModal'); toast('Acara tersimpan', 'Acara kalender sudah tersimpan.'); } catch (error) { toast('Acara belum tersimpan', error.message); } }
    if (form.id === 'alumniForm') { event.preventDefault(); event.stopImmediatePropagation(); const payload = { type: 'alumni', name: document.getElementById('alumniName').value.trim(), year: document.getElementById('alumniYear').value, unit: document.getElementById('alumniUnit').value, note: document.getElementById('alumniNote').value.trim() }; try { await saveRecord('alumni', `alumni:${Date.now()}`, payload); closeModal('alumniModal'); toast('Alumni tersimpan', 'Profil alumni sudah masuk direktori.'); } catch (error) { toast('Alumni belum tersimpan', error.message); } }
  }
  async function handleClick(event) {
    const target = event.target.closest('button, [role="button"]'); if (!target) return;
    if (target.matches('[data-live-record-student]')) { event.preventDefault(); event.stopImmediatePropagation(); const select = document.getElementById('record-student'); if (select) select.value = target.dataset.liveRecordStudent; document.getElementById('record-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
    if (target.matches('[data-live-finance]')) { event.preventDefault(); event.stopImmediatePropagation(); const item = (state.records.finance || []).find(record => record.id === target.dataset.liveFinance); if (!item) return; const p = item.payload || {}; if (target.dataset.action === 'remind') { try { await api(`admin/records/${item.id}`, json('PUT', { payload: { ...p, reminded_at: new Date().toISOString() } })); toast('Pengingat tercatat', 'Status tindak lanjut sudah disimpan.'); } catch (error) { toast('Pengingat gagal', error.message); } } else { download(`kwitansi-${item.record_key}.csv`, csv([['Santri', 'Nominal', 'Jatuh tempo', 'Status'], [p.student_name || '', p.amount || 0, p.due_date || '', p.status || 'paid']])); toast('Kwitansi diunduh', 'File kwitansi berhasil dibuat.'); } return; }
    if (target.id === 'exportButton' || target.id === 'exportStaff') { event.preventDefault(); event.stopImmediatePropagation(); await exportModule(page === 'kepegawaian.html' ? 'staff' : 'students', page === 'kepegawaian.html' ? 'rekap-kepegawaian.csv' : 'rekap-santri.csv', page === 'kepegawaian.html' ? state.staff : state.students); return; }
    if (target.dataset.modal === 'articleModal') state.editingContent = null;
    if (target.dataset.liveContent) { event.preventDefault(); event.stopImmediatePropagation(); const item = state.content.find(content => content.id === target.dataset.liveContent); if (!item) return; state.editingContent = item.id; document.getElementById('articleName').value = item.title || ''; document.getElementById('articleCopy').value = item.body || ''; document.getElementById('articleType').value = item.content_type || 'Artikel'; document.getElementById('articlePublish').value = item.status === 'published' ? 'publish' : 'draft'; openModal('articleModal'); return; }
    if (target.dataset.action === 'export') { event.preventDefault(); event.stopImmediatePropagation(); if (page === 'keuangan.html') await exportModule('finance', 'laporan-keuangan.csv'); else if (page === 'notifikasi.html') await exportModule('notifications', 'riwayat-komunikasi.csv'); else await exportModule('records', 'rekap-data.csv'); return; }
    if (target.id === 'confirmBroadcast') { event.preventDefault(); event.stopImmediatePropagation(); const payload = { type: 'broadcast', channel: document.querySelector('[data-channel].active')?.dataset.channel || 'whatsapp', target: document.getElementById('broadcastTarget')?.selectedOptions[0]?.text || '', title: document.getElementById('broadcastTitle').value.trim(), message: document.getElementById('broadcastMessage').value.trim(), mode: document.getElementById('sendMode')?.value || 'now', status: document.getElementById('sendMode')?.value === 'now' ? 'sent' : 'scheduled' }; try { await saveRecord('notifications', `broadcast:${Date.now()}`, payload); closeModal('previewModal'); await loadNotifications(); toast(payload.status === 'sent' ? 'Broadcast tercatat' : 'Broadcast terjadwal', 'Riwayat komunikasi sudah diperbarui.'); } catch (error) { toast('Broadcast belum tersimpan', error.message); } return; }
    if (target.matches('[data-rule]')) { event.preventDefault(); event.stopImmediatePropagation(); target.classList.toggle('on'); target.setAttribute('aria-pressed', String(target.classList.contains('on'))); saveRecord('settings', `notification-rule:${target.dataset.rule || target.textContent.trim()}`, { type: 'notification_rule', enabled: target.classList.contains('on'), name: target.dataset.rule || target.textContent.trim() }).then(() => toast('Aturan tersimpan', 'Preferensi otomatis sudah tersimpan.')).catch(error => toast('Aturan belum tersimpan', error.message)); return; }
    if (target.id === 'backupButton' || target.id === 'backupTop') { event.preventDefault(); event.stopImmediatePropagation(); try { const result = await api('admin/export'); download(`backup-darussolah-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(result, null, 2), 'application/json'); const time = document.getElementById('backupTime'); if (time) time.textContent = 'Baru saja'; toast('Backup selesai', 'Salinan data berhasil diunduh.'); } catch (error) { toast('Backup gagal', error.message); } return; }
    if (target.id === 'restoreButton') { event.preventDefault(); event.stopImmediatePropagation(); try { const result = await api('admin/summary'); toast('Uji pemulihan selesai', `${result.students_total || 0} santri dan ${result.teachers_active || 0} guru terbaca.`); } catch (error) { toast('Uji pemulihan gagal', error.message); } return; }
    if (target.id === 'download-report') { event.preventDefault(); event.stopImmediatePropagation(); window.print(); return; }
    if (target.id === 'approval-button') { event.preventDefault(); event.stopImmediatePropagation(); const student = state.students[0]; if (!student) return; try { await saveRecord('grades', gradeKey(student.id), { scores: {}, approval_status: 'pending', submitted_at: new Date().toISOString() }, student.id); const node = document.getElementById('approval-status'); if (node) node.textContent = 'Menunggu persetujuan kepala lembaga'; toast('Rapor diajukan', 'Status persetujuan sudah tersimpan.'); } catch (error) { toast('Pengajuan gagal', error.message); } return; }
    if (target.matches('[data-live-note]')) { event.preventDefault(); event.stopImmediatePropagation(); const studentId = target.dataset.liveNote; const current = (state.records.grades || []).find(item => item.entity_id === studentId && item.record_key === gradeKey(studentId)); const note = window.prompt('Catatan perkembangan santri', current?.payload?.note || ''); if (note === null) return; try { await saveRecord('grades', gradeKey(studentId), { ...(current?.payload || {}), note: note.trim(), scores: current?.payload?.scores || {} }, studentId); await loadGrades(); toast('Catatan tersimpan', 'Catatan akan masuk ke ringkasan rapor.'); } catch (error) { toast('Catatan belum tersimpan', error.message); } return; }
    if ((target.id === 'journal-button' || target.id === 'journal-card-button') && ['nilai.html', 'materi.html'].includes(page)) { event.preventDefault(); event.stopImmediatePropagation(); const text = window.prompt('Ringkasan jurnal pertemuan', ''); if (!text?.trim()) return; try { await saveRecord('journals', `journal:${Date.now()}`, { type: 'meeting', text: text.trim(), date: new Date().toISOString().slice(0, 10) }); toast('Jurnal tersimpan', 'Jurnal pertemuan sudah masuk ke server.'); } catch (error) { toast('Jurnal belum tersimpan', error.message); } return; }
    if (target.id === 'akhlak-button') { event.preventDefault(); event.stopImmediatePropagation(); const student = state.students[0]; if (!student) return; const text = window.prompt('Catatan akhlak dan kedisiplinan', ''); if (text === null) return; const current = (state.records.grades || []).find(item => item.entity_id === student.id && item.record_key === gradeKey(student.id)); try { await saveRecord('grades', gradeKey(student.id), { ...(current?.payload || {}), akhlak: text.trim(), scores: current?.payload?.scores || {} }, student.id); await loadGrades(); toast('Catatan akhlak tersimpan', 'Catatan sudah disiapkan untuk rapor.'); } catch (error) { toast('Catatan belum tersimpan', error.message); } return; }
    if (target.id === 'progress-button') { event.preventDefault(); event.stopImmediatePropagation(); download('progres-tahfidz.json', JSON.stringify(state.records.tahfidz || [], null, 2), 'application/json'); toast('Progres dibagikan', 'File progres live berhasil diunduh.'); return; }
    if (target.id === 'scheduleButton') { event.preventDefault(); event.stopImmediatePropagation(); const title = window.prompt('Nama jadwal mengajar', 'Sesi mengajar baru'); if (!title?.trim()) return; try { await saveRecord('schedule', `schedule:${Date.now()}`, { title: title.trim(), date: new Date().toISOString().slice(0, 10), teacher: portal()?.context?.profile?.full_name || '' }); toast('Jadwal tersimpan', 'Jadwal baru sudah masuk ke server.'); } catch (error) { toast('Jadwal belum tersimpan', error.message); } return; }
    if (target.id === 'confirmEmis') { event.preventDefault(); event.stopImmediatePropagation(); try { const result = await api('admin/export'); download(`emis-darussolah-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(result, null, 2), 'application/json'); closeModal('emisModal'); toast('Ekspor data selesai', 'Paket data live berhasil diunduh.'); } catch (error) { toast('Ekspor gagal', error.message); } return; }
    if (target.id === 'institutionDetail') { event.preventDefault(); event.stopImmediatePropagation(); download('sebaran-santri.csv', csv([['Nama santri', 'Lembaga', 'Kelas'], ...state.students.map(student => [student.full_name, student.institution_name || '', student.class_name || ''])])); toast('Detail lembaga diunduh', 'Rekap sebaran santri berhasil dibuat.'); return; }
    if (target.id === 'installButton') { event.preventDefault(); event.stopImmediatePropagation(); if (installPrompt) { await installPrompt.prompt(); installPrompt = null; } else toast('Pemasangan belum dipicu', 'Gunakan menu browser Tambahkan ke layar utama untuk memasang aplikasi.'); return; }
    if (target.id === 'close-session') { event.preventDefault(); event.stopImmediatePropagation(); const p = portal(); const rows = [...document.querySelectorAll('#student-rows tr[data-student-id]')]; if (!p?.primaryClass || !rows.length) return toast('Sesi belum siap', 'Data kelas dan santri belum termuat.'); const map = { belum: 'pending', hadir: 'present', izin: 'excused', sakit: 'sick', alpa: 'absent', terlambat: 'late' }; try { await api('attendance', json('PUT', { class_id: p.primaryClass.id, attendance_date: new Date().toISOString().slice(0, 10), close_session: true, records: rows.map(row => ({ student_id: row.dataset.studentId, status: map[row.dataset.status] || 'pending' })) })); target.textContent = 'Sesi ditutup'; toast('Sesi absensi ditutup', 'Status final sudah tersimpan di server.'); } catch (error) { toast('Sesi belum ditutup', error.message); } }
  }
  async function start(detail) {
    state.students = detail?.students || portal()?.students || [];
    state.classes = detail?.classes || portal()?.classes || [];
    try { if (page === 'absensi.html') return; if (page === 'santri.html') await loadStudents(); if (page === 'kepegawaian.html') await loadStaff(); if (page === 'tahfidz.html') await loadTahfidz(); if (page === 'nilai.html') await loadGrades(); if (page === 'keuangan.html') await loadFinance(); if (page === 'cms.html') await loadCms(); if (page === 'analitik.html') await loadAnalytics(); if (page === 'notifikasi.html') await loadNotifications(); if (page === 'pengaturan.html') await loadSettingsPage(); } catch (error) { toast('Data admin belum termuat', error.message); }
  }
  document.addEventListener('submit', handleSubmit, true);
  document.addEventListener('click', handleClick, true);
  document.addEventListener('change', event => {
    if (event.target.matches('[data-grade-subject]')) saveGrade(event.target);
    if (page === 'nilai.html' && ['class-select', 'term-select'].includes(event.target.id)) renderGrades();
    if (page === 'analitik.html' && event.target.id === 'scopeSelect' && event.target.value !== 'all') {
      const students = state.students.filter(item => item.class_id === event.target.value);
      const node = document.getElementById('studentTotal'); if (node) node.textContent = String(students.length);
    } else if (page === 'analitik.html' && event.target.id === 'scopeSelect') {
      const node = document.getElementById('studentTotal'); if (node) node.textContent = String(state.students.filter(item => item.status === 'active').length);
    }
    if (page === 'tahfidz.html' && event.target.id === 'record-student') document.querySelector('#record-target')?.focus();
  }, true);
  document.addEventListener('input', event => { if (event.target.id === 'student-search') { const query = event.target.value.toLowerCase(); document.querySelectorAll('#student-list .student-card').forEach(card => { card.hidden = !card.dataset.name.includes(query); }); } if (event.target.id === 'studentSearch') document.querySelectorAll('#studentRows tr').forEach(row => { row.hidden = !row.textContent.toLowerCase().includes(event.target.value.toLowerCase()); }); }, true);
  window.addEventListener('darussolah:ready', event => start(event.detail), { once: true });
})();
