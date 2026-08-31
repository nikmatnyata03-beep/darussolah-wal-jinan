/* Live assignment submission UI for wali/santri pages. */
(() => {
  const escapeHtml = value => String(value ?? '').replace(/[&<>"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'
  }[character]));
  const showToast = (title, detail) => {
    const titleNode = document.querySelector('#toastTitle, #toast-title');
    const detailNode = document.querySelector('#toastText, #toast-text');
    if (titleNode) titleNode.textContent = title;
    if (detailNode) detailNode.textContent = detail;
    document.querySelector('#toast')?.classList.add('show');
  };
  const state = { resources: [], submissions: [], students: [] };
  const assignments = () => state.resources.filter(item => item.resource_type === 'assignment');
  const submissionFor = (resourceId, studentId) => state.submissions.find(item =>
    item.resource_id === resourceId && item.student_id === studentId
  );
  const closeModal = () => {
    const node = document.querySelector('#learningSubmissionModal');
    if (node) node.hidden = true;
  };
  const ensureModal = () => {
    let node = document.querySelector('#learningSubmissionModal');
    if (node) return node;
    node = document.createElement('div');
    node.id = 'learningSubmissionModal';
    node.className = 'modal';
    node.hidden = true;
    node.innerHTML = `<div class="modal-backdrop" data-close-submission></div><div class="dialog" role="dialog" aria-modal="true" aria-labelledby="learningSubmissionTitle"><button class="dialog-close" type="button" data-close-submission aria-label="Tutup">&times;</button><span class="eyebrow">Pengumpulan tugas</span><h2 class="serif" id="learningSubmissionTitle">Kirim tugas</h2><p>Unggah satu berkas atau tulis catatan untuk guru. Berkas disimpan privat.</p><form id="learningSubmissionForm"><div class="form-grid"><div class="form-field full"><label for="submissionResource">Tugas</label><select id="submissionResource" required></select></div><div class="form-field full"><label for="submissionStudent">Untuk santri</label><select id="submissionStudent" required></select></div><div class="form-field full"><label for="submissionFile">Berkas opsional</label><input id="submissionFile" type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.mp3,.m4a,.mp4,.webm,.mov" /><small>Ukuran maksimal 10 MB.</small></div><div class="form-field full"><label for="submissionNote">Catatan</label><textarea id="submissionNote" maxlength="3000" placeholder="Tulis catatan singkat untuk guru..."></textarea></div></div><button class="btn btn-primary form-submit" type="submit">Kirim pengumpulan</button></form></div>`;
    document.body.append(node);
    node.querySelectorAll('[data-close-submission]').forEach(button => button.addEventListener('click', closeModal));
    node.querySelector('#learningSubmissionForm').addEventListener('submit', submit);
    return node;
  };
  const openModal = resourceId => {
    const portal = window.DarussolahPortal;
    if (!portal?.session) {
      showToast('Mode demo', 'Pengumpulan aktif setelah akun Supabase terhubung.');
      return;
    }
    const available = assignments();
    const node = ensureModal();
    const resourceSelect = node.querySelector('#submissionResource');
    const studentSelect = node.querySelector('#submissionStudent');
    resourceSelect.replaceChildren(...available.map(resource => new Option(resource.title, resource.id)));
    studentSelect.replaceChildren(...state.students.map(student => new Option(student.full_name, student.id)));
    resourceSelect.value = resourceId || available[0]?.id || '';
    studentSelect.value = state.students[0]?.id || '';
    node.hidden = !available.length || !state.students.length;
    if (!available.length || !state.students.length) {
      showToast('Belum siap mengumpulkan', 'Tugas atau data santri belum tersedia.');
      return;
    }
    node.querySelector('#submissionFile').value = '';
    node.querySelector('#submissionNote').value = '';
    node.querySelector('#submissionResource').focus();
  };
  const renderLiveLearning = () => {
    const list = document.querySelector('.learning-list');
    if (!list || !state.resources.length) return;
    list.replaceChildren();
    state.resources.slice(0, 6).forEach(resource => {
      const item = document.createElement('div');
      item.className = 'learning-item';
      const isAssignment = resource.resource_type === 'assignment';
      const student = state.students[0];
      const submission = isAssignment && student ? submissionFor(resource.id, student.id) : null;
      const status = submission?.status === 'reviewed' ? 'Ditinjau' : submission ? 'Dikumpulkan' : isAssignment ? 'Kumpulkan' : 'Baca';
      item.innerHTML = `<span class="learning-icon">${isAssignment ? '&#9998;' : '&#9670;'}</span><div class="learning-copy"><strong>${escapeHtml(resource.title)}</strong><span>${escapeHtml(resource.subject || (isAssignment ? 'Tugas' : 'Materi'))}${resource.due_date ? ` - Tenggat ${escapeHtml(resource.due_date)}` : ''}</span></div>${isAssignment && !submission ? `<button class="learning-status waiting learning-submit" type="button" data-submit-resource="${escapeHtml(resource.id)}">${status}</button>` : `<span class="learning-status${isAssignment ? '' : ' waiting'}">${status}</span>`}`;
      item.querySelector('[data-submit-resource]')?.addEventListener('click', () => openModal(resource.id));
      list.append(item);
    });
  };
  async function submit(event) {
    event.preventDefault();
    const portal = window.DarussolahPortal;
    const node = event.currentTarget.closest('#learningSubmissionModal');
    const resourceId = node.querySelector('#submissionResource').value;
    const studentId = node.querySelector('#submissionStudent').value;
    const file = node.querySelector('#submissionFile').files[0];
    const note = node.querySelector('#submissionNote').value.trim();
    if (!file && !note) {
      showToast('Pengumpulan masih kosong', 'Pilih berkas atau tulis catatan untuk guru.');
      return;
    }
    if (file && file.size > 10 * 1024 * 1024) {
      showToast('Berkas terlalu besar', 'Gunakan berkas dengan ukuran maksimal 10 MB.');
      return;
    }
    const submitButton = node.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    let filePath = null;
    try {
      if (file) {
        const tenantId = portal.context?.profile?.tenant_id;
        if (!tenantId) throw new Error('tenant akun belum tersedia');
        const safeName = file.name.toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'berkas';
        filePath = `submissions/${tenantId}/${studentId}/${resourceId}/${Date.now()}-${safeName}`;
        const upload = await portal.client.storage.from(portal.config.storageBucket).upload(filePath, file, {
          contentType: file.type || 'application/octet-stream', upsert: false
        });
        if (upload.error) throw upload.error;
      }
      const created = await portal.requestPrivate(
        portal.client,
        'learning/submissions',
        portal.session,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resource_id: resourceId, student_id: studentId, file_path: filePath, note: note || null }) }
      );
      state.submissions.push(created);
      closeModal();
      renderLiveLearning();
      showToast('Tugas terkirim', 'Pengumpulan tersimpan dan dapat dilihat guru.');
    } catch (error) {
      if (filePath) await portal.client.storage.from(portal.config.storageBucket).remove([filePath]).catch(() => {});
      showToast('Pengumpulan belum tersimpan', error.message || 'Periksa koneksi lalu coba lagi.');
    } finally {
      submitButton.disabled = false;
    }
  }
  window.addEventListener('darussolah:ready', event => {
    state.resources = event.detail.learning || [];
    state.submissions = event.detail.learningSubmissions || [];
    state.students = event.detail.students || [];
    renderLiveLearning();
  }, { once: true });
})();
