/* ══════════════════════════════════════════════
   ToolKit Pro — JavaScript
══════════════════════════════════════════════ */

// ── Tab switching ──────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

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

// ── Option button groups ───────────────────
document.querySelectorAll('.btn-group').forEach(group => {
  group.querySelectorAll('.option-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      group.querySelectorAll('.option-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
});

// ════════════════════════════════════════════
//  VIDEO COMPRESSOR
// ════════════════════════════════════════════
let videoFile = null;

const videoInput   = document.getElementById('video-input');
const videoDropZ   = document.getElementById('video-drop-zone');
const videoFileInfo= document.getElementById('video-file-info');
const compressBtn  = document.getElementById('compress-btn');
const videoProgW   = document.getElementById('video-progress-wrap');
const videoBar     = document.getElementById('video-bar');
const videoPct     = document.getElementById('video-pct');
const videoStat    = document.getElementById('video-status-text');
const videoResult  = document.getElementById('video-result');

videoInput.addEventListener('change', e => setVideoFile(e.target.files[0]));
videoDropZ.addEventListener('click', () => videoInput.click());
videoDropZ.addEventListener('dragover', e => { e.preventDefault(); videoDropZ.classList.add('drag-over'); });
videoDropZ.addEventListener('dragleave', () => videoDropZ.classList.remove('drag-over'));
videoDropZ.addEventListener('drop', e => {
  e.preventDefault();
  videoDropZ.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) setVideoFile(e.dataTransfer.files[0]);
});

function setVideoFile(file) {
  videoFile = file;
  videoFileInfo.textContent = `📁 ${file.name}  —  ${fmtSize(file.size)}`;
  videoFileInfo.classList.remove('hidden');
  compressBtn.disabled = false;
}

compressBtn.addEventListener('click', async () => {
  if (!videoFile) return;
  const quality    = document.querySelector('#quality-group .option-btn.active').dataset.val;
  const resolution = document.querySelector('#resolution-group .option-btn.active').dataset.val;

  const fd = new FormData();
  fd.append('video', videoFile);
  fd.append('quality', quality);
  fd.append('resolution', resolution);

  compressBtn.disabled = true;
  videoProgW.classList.remove('hidden');
  videoResult.classList.add('hidden');
  setVideoProgress(5, 'Uploading...');

  try {
    const res  = await fetch('/compress', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { showVideoError(data.error); return; }
    pollJob(data.job_id, 'video');
  } catch(e) {
    showVideoError('Upload failed: ' + e.message);
  }
});

function setVideoProgress(pct, msg) {
  videoBar.style.width = pct + '%';
  videoPct.textContent = pct + '%';
  if (msg) videoStat.textContent = msg;
}

function showVideoError(msg) {
  videoResult.innerHTML = `<div class="error-box"><i class="fa fa-exclamation-triangle"></i> ${msg}</div>`;
  videoResult.classList.remove('hidden');
  compressBtn.disabled = false;
  setVideoProgress(0, 'Error');
}

// ════════════════════════════════════════════
//  APK BUILDER
// ════════════════════════════════════════════
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

buildBtn.addEventListener('click', async () => {
  const appName    = document.getElementById('app-name').value.trim();
  const pkgName    = document.getElementById('package-name').value.trim();
  const appUrl     = document.getElementById('app-url').value.trim();
  const sourceType = document.querySelector('.source-tab.active').dataset.source;

  if (!appName) { alert('Please enter an App Name'); return; }
  if (!pkgName || pkgName.split('.').length < 2) { alert('Invalid package name. Use format: com.name.app'); return; }
  if (sourceType === 'url' && !appUrl) { alert('Please enter a URL'); return; }
  if (sourceType === 'file' && !gameFileInput.files[0]) { alert('Please upload a file'); return; }

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
  setApkProgress(5, 'Starting build...');
  activateStep(1);

  try {
    const res  = await fetch('/build-apk', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { showApkError(data.error); return; }
    pollJob(data.job_id, 'apk');
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
    el.classList.remove('done', 'active');
    if (i < n) el.classList.add('done');
    else if (i === n) el.classList.add('active');
  }
}

function resetSteps() {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById('step-' + i);
    el.classList.remove('done', 'active');
  }
}

function showApkError(msg) {
  apkResult.innerHTML = `<div class="error-box"><i class="fa fa-exclamation-triangle"></i> ${msg}</div>`;
  apkResult.classList.remove('hidden');
  buildBtn.disabled = false;
  setApkProgress(0, 'Error');
}

// ════════════════════════════════════════════
//  SHARED: Job polling
// ════════════════════════════════════════════
function pollJob(jobId, type) {
  const interval = setInterval(async () => {
    try {
      const res  = await fetch('/job/' + jobId);
      const data = await res.json();

      if (type === 'video') {
        setVideoProgress(data.progress || 0, data.msg || 'Processing...');
        if (data.status === 'done') {
          clearInterval(interval);
          setVideoProgress(100, '✅ Done!');
          showVideoResult(data);
          compressBtn.disabled = false;
        } else if (data.status === 'error') {
          clearInterval(interval);
          showVideoError(data.error || 'Unknown error');
        }
      } else {
        const pct = data.progress || 0;
        setApkProgress(pct, data.msg || 'Building...');
        if (pct >= 20) activateStep(2);
        if (pct >= 50) activateStep(3);
        if (pct >= 85) activateStep(4);
        if (data.status === 'done') {
          clearInterval(interval);
          activateStep(5);
          setApkProgress(100, '✅ APK Ready!');
          showApkResult(data);
          buildBtn.disabled = false;
        } else if (data.status === 'error') {
          clearInterval(interval);
          showApkError(data.error || 'Build failed');
          buildBtn.disabled = false;
        }
      }
    } catch(e) {}
  }, 1500);
}

function showVideoResult(data) {
  videoResult.innerHTML = `
    <h4><i class="fa fa-check-circle"></i> Compression Complete!</h4>
    <div class="result-grid">
      <div class="stat-box"><div class="stat-label">Original Size</div><div class="stat-value">${data.original_size || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">Compressed</div><div class="stat-value green">${data.compressed_size || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">Saved</div><div class="stat-value green">${data.reduction || '—'}</div></div>
    </div>
    <a href="${data.download_url}" class="btn btn-primary download-btn">
      <i class="fa fa-download"></i> Download Compressed Video
    </a>`;
  videoResult.classList.remove('hidden');
}

function showApkResult(data) {
  apkResult.innerHTML = `
    <h4><i class="fa fa-android"></i> APK Built Successfully!</h4>
    <div class="result-grid">
      <div class="stat-box"><div class="stat-label">App Name</div><div class="stat-value">${data.app_name || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">Package</div><div class="stat-value" style="font-size:.85rem">${data.package || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">APK Size</div><div class="stat-value green">${data.apk_size || '—'}</div></div>
    </div>
    <a href="${data.download_url}" class="btn btn-green download-btn">
      <i class="fa fa-download"></i> Download APK
    </a>
    <p style="margin-top:12px;font-size:.8rem;color:var(--muted)">
      ⚠️ Enable "Install from unknown sources" on your Android device to install this APK.
    </p>`;
  apkResult.classList.remove('hidden');
}

// ── Utility ──
function fmtSize(bytes) {
  const units = ['B','KB','MB','GB'];
  let u = 0;
  while (bytes >= 1024 && u < 3) { bytes /= 1024; u++; }
  return bytes.toFixed(1) + ' ' + units[u];
}
