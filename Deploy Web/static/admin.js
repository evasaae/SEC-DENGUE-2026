/* ============================================================
   EWS DBD Kalbar — Admin Panel JS
   ============================================================ */

const PIN = '4321';
let currentPin = '';
let isAuthenticated = localStorage.getItem('admin_auth') === 'true';

function getStatusClass(statusStr) {
  if (!statusStr) return 'AMAN';
  const s = statusStr.toUpperCase();
  if (s.includes('SIAGA')) return 'SIAGA';
  if (s.includes('WASPADA')) return 'WASPADA';
  return 'AMAN';
}

// Elements
const pinScreen = document.getElementById('pin-screen');
const adminApp = document.getElementById('admin-app');
const pinDots = document.querySelectorAll('.pin-dot');
const pinError = document.getElementById('pin-error');
const adminClock = document.getElementById('admin-clock');

// ── INIT ──
if (isAuthenticated) {
  showAdminApp();
} else {
  pinScreen.style.display = 'flex';
}

setInterval(() => {
  if (adminClock) {
    adminClock.textContent = new Date().toLocaleTimeString('id-ID', { hour12: false });
  }
}, 1000);

// ── PIN LOGIC ──
function pressKey(num) {
  if (currentPin.length < 4) {
    currentPin += num;
    updateDots();
    if (currentPin.length === 4) verifyPin();
  }
}

function deleteKey() {
  if (currentPin.length > 0) {
    currentPin = currentPin.slice(0, -1);
    updateDots();
  }
}

function clearPin() {
  currentPin = '';
  updateDots();
  pinError.textContent = '';
}

function updateDots() {
  pinDots.forEach((dot, idx) => {
    if (idx < currentPin.length) dot.classList.add('filled');
    else dot.classList.remove('filled');
  });
}

function verifyPin() {
  if (currentPin === PIN) {
    localStorage.setItem('admin_auth', 'true');
    isAuthenticated = true;
    showAdminApp();
  } else {
    pinError.textContent = 'PIN Salah!';
    setTimeout(clearPin, 1000);
  }
}

function logout() {
  localStorage.removeItem('admin_auth');
  isAuthenticated = false;
  pinScreen.style.display = 'flex';
  adminApp.style.display = 'none';
  clearPin();
}

function showAdminApp() {
  pinScreen.style.display = 'none';
  adminApp.style.display = 'flex';
  loadAdminData();
  setInterval(loadAdminData, 30000); // refresh 30s
}

// ── DATA LOGIC ──
async function loadAdminData() {
  try {
    const res = await fetch('/api/status');
    const responseData = await res.json();
    const data = responseData.data || responseData;
    
    renderSiaga(data);
    renderFogging(data);
  } catch (err) {
    console.error(err);
    showToast('Gagal memuat data API', 'error');
  }
}

function renderSiaga(data) {
  const siagaAreas = data.filter(d => d.status.toUpperCase().includes('SIAGA'));
  const grid = document.getElementById('siaga-grid');
  document.getElementById('siaga-count-badge').textContent = `${siagaAreas.length} Wilayah`;
  
  if (siagaAreas.length === 0) {
    grid.innerHTML = '<div style="color:var(--text-secondary); padding: 20px;">Belum ada wilayah berstatus SIAGA saat ini.</div>';
    return;
  }
  
  // Create warning banner
  let html = `
    <div class="siaga-warning-banner" style="grid-column: 1 / -1; background: rgba(255, 45, 85, 0.1); border: 1px solid rgba(255, 45, 85, 0.3); padding: 16px; border-radius: 12px; color: var(--red); font-weight: bold; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; font-size: 0.9rem;">
      <span>⚠️</span>
      <span>TINDAKAN MENDESAK: Wilayah berstatus SIAGA (Merah). Segera lakukan Penyelidikan Epidemiologi (PE) dan Fogging Fokus!</span>
    </div>
  `;
  
  siagaAreas.forEach(d => {
    const isFogging = d.fogging_active;
    const btn = isFogging 
      ? `<button class="btn-pe" style="background:rgba(255, 45, 85, 0.1); border: 1px solid rgba(255, 45, 85, 0.3); color:var(--red);" onclick="confirmToggleFogging('${d.kabupaten}', true)">🗑️ Hapus Catatan Fogging</button>` 
      : `<button class="btn-pe" style="background:var(--red);" onclick="confirmToggleFogging('${d.kabupaten}', false)">🔥 Catat Fogging Fokus Selesai</button>`;
    
    const statusClass = getStatusClass(d.status).toLowerCase();
    
    html += `
      <div class="siaga-card">
        <span class="badge badge-${statusClass}" style="float: right;">${d.status}</span>
        <h3>${d.kabupaten}</h3>
        <p style="margin-bottom: 8px; font-size: 0.85rem; color: var(--text-secondary);">
          Suhu: ${d.suhu}°C | Berita: ${d.berita}
        </p>
        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border); padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; font-size: 0.8rem;">
          Status Intervensi: <strong style="color:${isFogging ? 'var(--cyan)' : 'var(--red)'}">${isFogging ? 'Fogging Fokus Selesai (85% Risk Diminished)' : 'Menunggu Fogging Fokus'}</strong>
        </div>
        ${btn}
      </div>
    `;
  });
  grid.innerHTML = html;
}

function renderFogging(data) {
  const tbody = document.getElementById('fogging-tbody');
  tbody.innerHTML = '';
  
  const activeOrSiaga = data.filter(d => d.status.toUpperCase().includes('SIAGA') || d.fogging_active);
  
  if (activeOrSiaga.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-secondary)">Tidak ada wilayah SIAGA atau intervensi aktif saat ini.</td></tr>`;
    return;
  }
  
  activeOrSiaga.forEach(d => {
    const isFogging = d.fogging_active;
    const tr = document.createElement('tr');
    
    // Only SIAGA can perform fogging. If it is already fogging, action button is not shown.
    const actionBtn = (d.status.toUpperCase().includes('SIAGA') && !isFogging)
      ? `<button class="btn-fogging" onclick="confirmToggleFogging('${d.kabupaten}', false)">🔥 Mulai Fogging</button>`
      : '-';
      
    // Hapus / Undo column (replaces drift column)
    const undoBtn = isFogging
      ? `<button class="btn-undo" onclick="confirmToggleFogging('${d.kabupaten}', true)">🗑️ Hapus</button>`
      : '-';

    const statusClass = getStatusClass(d.status).toLowerCase();

    tr.innerHTML = `
      <td>${d.kabupaten}</td>
      <td><span class="badge badge-${statusClass}">${d.status}</span></td>
      <td>${d.suhu}°C</td>
      <td>${d.berita}</td>
      <td>${undoBtn}</td>
      <td>${isFogging ? '<span style="color:var(--cyan); font-weight:bold;">Aktif</span>' : '-'}</td>
      <td>${actionBtn}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function confirmToggleFogging(kab, currentlyActive) {
  const action = currentlyActive ? 'batal/reset' : 'selesai';
  const msg = currentlyActive
    ? `Apakah Anda yakin ingin me-reset status fogging untuk wilayah ${kab}? Tindakan ini akan mengembalikan data risiko wilayah.`
    : `Apakah Anda yakin ingin mencatat FOGGING FOKUS SELESAI untuk wilayah ${kab}? Tindakan ini akan menurunkan bobot risiko sosial wilayah sebesar 85%.`;
    
  if (confirm(msg)) {
    const apiAction = currentlyActive ? 'reset' : 'selesai';
    try {
      const res = await fetch('/api/fogging', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kabupaten: kab, action: apiAction })
      });
      if (res.ok) {
        showToast(`Status fogging untuk ${kab} berhasil diperbarui!`, 'success');
        loadAdminData();
      } else {
        showToast(`Gagal memperbarui status fogging untuk ${kab}`, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast(`Error koneksi server`, 'error');
    }
  }
}

function showToast(msg, type='info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => {
    t.style.opacity = 0;
    setTimeout(() => t.remove(), 300);
  }, 3000);
}
