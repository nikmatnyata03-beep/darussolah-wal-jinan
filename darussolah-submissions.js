/* Live assignment submission UI for wali/santri pages. */
(() => {
  const showToast = (title, detail) => {
    const titleNode = document.querySelector('#toastTitle, #toast-title');
    const detailNode = document.querySelector('#toastText, #toast-text');
    if (titleNode) titleNode.textContent = title;
    if (detailNode) detailNode.textContent = detail;
    document.querySelector('#toast')?.classList.add('show');
  };
  const state = { resources: [], submissions: [], students: [], currentStudent: null };
   const resourcesForStudent = () => {
     const student = state.currentStudent;
     if (!student) return state.resources;
     return state.resources.filter(item =>
       (!item.institution_id || item.institution_id === student.institution_id)
       && (!item.class_id || item.class_id === student.class_id)
     );
   };
   const assignments = () => resourcesForStudent().filter(item => item.resource_type === 'assignment');
  const submissionFor = (resourceId, studentId) => state.submissions.find(item =>
    item.resource_id === resourceId && item.student_id === studentId
  );
  const closeModal = () => {
    const node = document.querySelector('#learningSubmissionModal');
    if (node) node.hidden = true;
  };
  const openResource = async resource => {
    const portal = window.DarussolahPortal;
    if (!resource.file_path) {
      showToast('Berkas belum tersedia', 'Materi ini belum memiliki file yang dapat dibuka.');
      return;
    }
    if (!portal?.client?.storage) {
      showToast('Materi belum siap', 'Sesi portal belum tersedia untuk membuka berkas privat.');
      return;
    }
    const popup = window.open('', '_blank');
    try {
      const result = await portal.client.storage.from(portal.config.resourceStorageBucket).createSignedUrl(resource.file_path, 300);
      if (result.error || !result.data?.signedUrl) throw result.error || new Error('tautan materi tidak tersedia');
      if (popup) {
        popup.opener = null;
        popup.location.href = result.data.signedUrl;
      } else {
        window.location.assign(result.data.signedUrl);
      }
    } catch (error) {
      popup?.close();
      showToast('Materi belum dapat dibuka', error.message || 'Periksa koneksi lalu coba lagi.');
    }
  };
  const ensureModal = () => {
    let node = document.querySelector('#learningSubmissionModal');
    if (node) return node;
    node = document.createElement('div');
    node.id = 'learningSubmissionModal';
    node.className = 'modal';
    node.hidden = true;
     const backdrop = document.createElement('div');
     backdrop.className = 'modal-backdrop';
     backdrop.dataset.closeSubmission = '';
     const dialog = document.createElement('div');
     dialog.className = 'dialog';
     dialog.setAttribute('role', 'dialog');
     dialog.setAttribute('aria-modal', 'true');
     dialog.setAttribute('aria-labelledby', 'learningSubmissionTitle');
     const close = document.createElement('button');
     close.className = 'dialog-close';
     close.type = 'button';
     close.dataset.closeSubmission = '';
     close.setAttribute('aria-label', 'Tutup');
     close.textContent = '×';
     const eyebrow = document.createElement('span');
     eyebrow.className = 'eyebrow';
     eyebrow.textContent = 'Pengumpulan tugas';
     const heading = document.createElement('h2');
     heading.className = 'serif';
     heading.id = 'learningSubmissionTitle';
     heading.textContent = 'Kirim tugas';
     const description = document.createElement('p');
     description.textContent = 'Unggah satu berkas atau tulis catatan untuk guru. Berkas disimpan privat.';
     const form = document.createElement('form');
     form.id = 'learningSubmissionForm';
     const grid = document.createElement('div');
     grid.className = 'form-grid';
     const field = (labelText, control) => {
       const wrapper = document.createElement('div');
       wrapper.className = 'form-field full';
       const label = document.createElement('label');
       label.htmlFor = control.id;
       label.textContent = labelText;
       wrapper.append(label, control);
       return wrapper;
     };
     const resourceSelect = document.createElement('select');
     resourceSelect.id = 'submissionResource';
     resourceSelect.required = true;
     const studentSelect = document.createElement('select');
     studentSelect.id = 'submissionStudent';
     studentSelect.required = true;
     const fileInput = document.createElement('input');
     fileInput.id = 'submissionFile';
     fileInput.type = 'file';
     fileInput.accept = '.pdf,.doc,.docx,.jpg,.jpeg,.png,.mp3,.m4a,.mp4,.webm,.mov';
     const fileHint = document.createElement('small');
     fileHint.textContent = 'Ukuran maksimal 10 MB.';
     const fileField = field('Berkas opsional', fileInput);
     fileField.append(fileHint);
     const note = document.createElement('textarea');
     note.id = 'submissionNote';
     note.maxLength = 3000;
     note.placeholder = 'Tulis catatan singkat untuk guru...';
     grid.append(field('Tugas', resourceSelect), field('Untuk santri', studentSelect), fileField, field('Catatan', note));
     const submitButton = document.createElement('button');
     submitButton.className = 'btn btn-primary form-submit';
     submitButton.type = 'submit';
     submitButton.textContent = 'Kirim pengumpulan';
     form.append(grid, submitButton);
     dialog.append(close, eyebrow, heading, description, form);
     node.append(backdrop, dialog);
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
     const activeStudents = state.currentStudent ? [state.currentStudent] : state.students;
     studentSelect.replaceChildren(...activeStudents.map(student => new Option(student.full_name, student.id)));
    resourceSelect.value = resourceId || available[0]?.id || '';
    studentSelect.value = (state.currentStudent || state.students[0])?.id || '';
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
     if (!list) return;
     list.replaceChildren();
     const resources = resourcesForStudent();
     if (!resources.length) {
       const empty = document.createElement('p');
       empty.className = 'empty-state';
       empty.textContent = 'Belum ada materi atau tugas untuk kelas anak ini.';
       list.append(empty);
       return;
     }
     resources.slice(0, 6).forEach(resource => {
       const item = document.createElement('div');
       item.className = 'learning-item';
       const isAssignment = resource.resource_type === 'assignment';
       const student = state.currentStudent || state.students[0];
       const submission = isAssignment && student ? submissionFor(resource.id, student.id) : null;
       const status = submission?.status === 'reviewed' ? 'Ditinjau' : submission ? 'Dikumpulkan' : isAssignment ? 'Kumpulkan' : 'Baca';
       const icon = document.createElement('span');
       icon.className = 'learning-icon';
       icon.textContent = isAssignment ? '✎' : '◆';
       const copy = document.createElement('div');
       copy.className = 'learning-copy';
       const title = document.createElement('strong');
       title.textContent = resource.title || 'Tanpa judul';
       const meta = document.createElement('span');
       meta.textContent = `${resource.subject || (isAssignment ? 'Tugas' : 'Materi')}${resource.due_date ? ` - Tenggat ${resource.due_date}` : ''}`;
       copy.append(title, meta);
       let action;
       if (isAssignment && !submission) {
         action = document.createElement('button');
         action.className = 'learning-status waiting learning-submit';
         action.type = 'button';
         action.dataset.submitResource = resource.id;
         action.textContent = status;
         action.addEventListener('click', () => openModal(resource.id));
       } else if (!isAssignment && resource.file_path) {
         action = document.createElement('button');
         action.className = 'learning-status waiting learning-open';
         action.type = 'button';
         action.dataset.openResource = resource.id;
         action.textContent = status;
         action.addEventListener('click', () => openResource(resource));
       } else {
         action = document.createElement('span');
         action.className = `learning-status${isAssignment ? '' : ' waiting'}`;
         action.textContent = status;
       }
       item.append(icon, copy, action);
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
    state.currentStudent = state.students[0] || null;
    renderLiveLearning();
  }, { once: true });
  window.addEventListener('darussolah:child-selected', event => {
    const student = event.detail?.student;
    if (!student) return;
    state.currentStudent = student;
    renderLiveLearning();
  });
})();
