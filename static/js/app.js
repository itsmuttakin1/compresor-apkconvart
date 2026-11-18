/* ══════════════════════════════════════════════
   APK Converter — JavaScript
══════════════════════════════════════════════ */

// ── Source type tabs ──────────────────────
document.querySelectorAll('.source-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.source-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.source-panel').forEach(p => { p.classList.remove('active'); p.classList.add('hidden'); });
    tab.classList.add('active');
    const panel = document.getElementById('source-' + tab.dataset.source);
    panel.classList.add('active');
    panel.classList.remove('hidden');
  });
});

// ── Icon preview ──────────────────────────
const iconInput     = document.getElementById('icon-input');
const iconPreviewW  = document.getElementById('icon-preview-wrap');
const iconPreview   = document.getElementById('icon-preview');
const iconPlacehol  = document.getElementById('icon-placeholder');
const gameFileInput = document.getElementById('game-file-input');
const gameFileInfo  = document.getElementById('game-file-info');
const buildBtn      = document.getElementById('build-btn');
const apkProgW      = document.getElementById('apk-progress-wrap');
const apkBar        = document.getElementById('apk-bar');
const apkPct        = document.getElementById('apk-pct');
const apkStat       = document.getElementById('apk-status-text');
const apkResult     = document.getElementById('apk-result');

iconInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    iconPreview.src = ev.target.result;
    iconPreviewW.classList.remove('hidden');
    iconPlacehol.style.display = 'none';
  };
  reader.readAsDataURL(file);
});

gameFileInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  gameFileInfo.textContent = `📁 ${file.name}  —  ${fmtSize(file.size)}`;
  gameFileInfo.classList.remove('hidden');
});

// ── Build APK button click ─────────────────
buildBtn.addEventListener('click', async () => {
  const appName    = document.getElementById('app-name').value.trim();
  const pkgName    = document.getElementById('package-name').value.trim();
  const appUrl     = document.getElementById('app-url').value.trim();
  const sourceType = document.querySelector('.source-tab.active').dataset.source;

  if (!appName) { alert('Please enter an App Name'); return; }
  if (!pkgName || pkgName.split('.').length < 2) { 
    alert('Invalid package name. Please use format: com.mrghost.app'); 
    return; 
  }
  if (sourceType === 'url' && !appUrl) { 
    alert('Please enter a website or game URL'); 
    return; 
  }
  if (sourceType === 'file' && !gameFileInput.files[0]) { 
    alert('Please select an HTML or ZIP file'); 
    return; 
  }

  const fd = new FormData();
  fd.append('app_name', appName);
  fd.append('package_name', pkgName);
  fd.append('source_type', sourceType);
  fd.append('app_url', appUrl);
  if (iconInput.files[0])     fd.append('icon', iconInput.files[0]);
  if (gameFileInput.files[0]) fd.append('game_file', gameFileInput.files[0]);

  buildBtn.disabled = true;
  apkProgW.classList.remove('hidden');
  apkResult.classList.add('hidden');
  resetSteps();
  setApkProgress(8, 'Starting build process...');
  activateStep(1);

  try {
    const res  = await fetch('/build-apk', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { showApkError(data.error); return; }
    pollJob(data.job_id);
  } catch(e) {
    showApkError('Request failed: ' + e.message);
  }
});

function setApkProgress(pct, msg) {
  apkBar.style.width = pct + '%';
  apkPct.textContent = pct + '%';
  if (msg) apkStat.textContent = msg;
}

function activateStep(n) {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById('step-' + i);
    if (!el) continue;
    el.classList.remove('done', 'active');
    if (i < n) el.classList.add('done');
    else if (i === n) el.classList.add('active');
  }
}

function resetSteps() {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById('step-' + i);
    if (el) el.classList.remove('done', 'active');
  }
}

function showApkError(msg) {
  apkResult.innerHTML = `<div class="error-box"><i class="fa fa-exclamation-triangle"></i> ${msg}</div>`;
  apkResult.classList.remove('hidden');
  buildBtn.disabled = false;
  setApkProgress(0, 'Failed');
}

// ── Polling ────────────────────────────────
function pollJob(jobId) {
  const interval = setInterval(async () => {
    try {
      const res  = await fetch('/job/' + jobId);
      const data = await res.json();

      const pct = data.progress || 0;
      setApkProgress(pct, data.msg || 'Processing...');
      if (pct >= 25) activateStep(2);
      if (pct >= 55) activateStep(3);
      if (pct >= 85) activateStep(4);

      if (data.status === 'done') {
        clearInterval(interval);
        activateStep(5);
        setApkProgress(100, '✅ APK Ready with "Mr Ghost" Toast!');
        showApkResult(data);
        buildBtn.disabled = false;
      } else if (data.status === 'error') {
        clearInterval(interval);
        showApkError(data.error || 'Build failed');
        buildBtn.disabled = false;
      }
    } catch(e) {}
  }, 1200);
}

function showApkResult(data) {
  apkResult.innerHTML = `
    <h4><i class="fa fa-android"></i> APK Generated Successfully!</h4>
    <div class="result-grid">
      <div class="stat-box">
        <div class="stat-label">App Name</div>
        <div class="stat-value">${data.app_name || '—'}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Package Name</div>
        <div class="stat-value" style="font-size:.85rem">${data.package || '—'}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Toast Added</div>
        <div class="stat-value green">"${data.toast || 'Mr Ghost'}"</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">File Size</div>
        <div class="stat-value green">${data.apk_size || '—'}</div>
      </div>
    </div>
    <a href="${data.download_url}" class="btn btn-green download-btn">
      <i class="fa fa-download"></i> Download APK Now
    </a>
    <p style="margin-top:14px;font-size:.82rem;color:var(--muted);text-align:center;">
      💡 Android ডিভাইসে ইন্সটল করার পর ওপেন করলেই <strong>"Mr Ghost"</strong> টোস্ট মেসেজ দেখতে পাবে!
    </p>`;
  apkResult.classList.remove('hidden');
}

function fmtSize(bytes) {
  const units = ['B','KB','MB','GB'];
  let u = 0;
  while (bytes >= 1024 && u < 3) { bytes /= 1024; u++; }
  return bytes.toFixed(1) + ' ' + units[u];
}
