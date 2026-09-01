(() => {
  const nav = document.querySelector('.side-nav');
  if (!nav) return;

  const adminRoles = new Set(['super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran']);
  const adminItems = [
    ['absensi.html', 'Absensi'],
    ['materi.html', 'Materi & tugas'],
    ['tahfidz.html', 'Tahfidz & tahsin'],
    ['nilai.html', 'Nilai & rapor'],
    ['keuangan.html', 'Keuangan'],
    ['notifikasi.html', 'Komunikasi'],
    ['santri.html', 'Data santri'],
    ['kepegawaian.html', 'Kepegawaian'],
    ['cms.html', 'CMS & konten'],
    ['analitik.html', 'Analitik'],
    ['pengaturan.html', 'Pengaturan']
  ];
  const guruItems = [
    ['absensi.html#ringkasan', 'Ringkasan'],
    ['absensi.html#absensi', 'Absensi'],
    ['materi.html', 'Materi & tugas'],
    ['tahfidz.html', 'Tahfidz & tahsin'],
    ['nilai.html', 'Nilai & rapor'],
    ['santri.html', 'Data santri'],
    ['pengaturan.html', 'Pengaturan']
  ];

  const readStoredMode = () => {
    try {
      return sessionStorage.getItem('dwj-ui-role') || localStorage.getItem('dwj-ui-role') || '';
    } catch (error) {
      return '';
    }
  };
  const roleMode = roles => roles.some(role => adminRoles.has(role)) ? 'admin' : 'guru';
  const initialMode = readStoredMode() === 'admin'
    ? 'admin'
    : readStoredMode() === 'guru'
      ? 'guru'
      : document.body?.dataset.portalRole === 'admin' ? 'admin' : 'guru';
  const currentTarget = () => {
    const page = window.location.pathname.split('/').pop() || 'index.html';
    return `${page}${window.location.hash}`;
  };
  const sameTarget = href => {
    const target = new URL(href, window.location.href);
    const page = target.pathname.split('/').pop() || 'index.html';
    return `${page}${target.hash}` === currentTarget()
      || (!window.location.hash && !target.hash && page === (window.location.pathname.split('/').pop() || 'index.html'));
  };
  const saveMode = mode => {
    try {
      sessionStorage.setItem('dwj-ui-role', mode);
    } catch (error) { /* Navigation remains usable when storage is unavailable. */ }
  };
  const render = mode => {
    const items = mode === 'admin' ? adminItems : guruItems;
    nav.setAttribute('aria-label', mode === 'admin' ? 'Menu admin lembaga' : 'Menu ruang kerja guru');
    nav.replaceChildren();
    const label = document.createElement('span');
    label.className = 'nav-label';
    label.textContent = 'Ruang kerja';
    nav.append(label);
    items.forEach(([href, text], index) => {
      const link = document.createElement('a');
      link.className = 'side-link';
      link.href = href;
      const active = sameTarget(href);
      if (active) {
        link.classList.add('active');
        link.setAttribute('aria-current', 'page');
      }
      const icon = document.createElement('span');
      icon.className = 'nav-icon';
      icon.textContent = String(index + 1).padStart(2, '0');
      link.append(icon, document.createTextNode(text));
      nav.append(link);
    });
    nav.dataset.portalNavMode = mode;
  };

  render(initialMode);
  window.addEventListener('darussolah:ready', () => {
    const mode = roleMode(window.DarussolahPortal?.context?.roles || []);
    saveMode(mode);
    render(mode);
  }, { once: true });
})();
