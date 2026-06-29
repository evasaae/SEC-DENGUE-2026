/* ============================================================
   EWS DBD Kalbar — Dashboard JS
   ============================================================ */

let map = null;
let geoLayer = null;
let allData = [];
let autoRefreshId = null;
let cityMarkers = [];

// DOM Elements
const clockEl = document.getElementById('clock');
const liveStatusEl = document.getElementById('live-status');
const tbody = document.getElementById('table-body');
const searchInput = document.getElementById('search-input');
const goldenSidebar = document.getElementById('golden-sidebar');
const goldenAreasEl = document.getElementById('golden-areas');
const goldenTab = document.getElementById('golden-tab');
const goldenTabCount = document.getElementById('golden-tab-count');
const loadingOverlay = document.getElementById('map-loading');
const refreshBtn = document.getElementById('refresh-btn');

// Colors
const colors = {
  AMAN: '#10b981',
  WASPADA: '#f59e0b',
  SIAGA: '#e11d48',
  GOLDEN: '#f97316'
};

function getStatusClass(statusStr) {
  if (!statusStr) return 'AMAN';
  const s = statusStr.toUpperCase();
  if (s.includes('SIAGA')) return 'SIAGA';
  if (s.includes('WASPADA')) return 'WASPADA';
  return 'AMAN';
}

// Start Clock
setInterval(() => {
  const now = new Date();
  clockEl.textContent = now.toLocaleTimeString('id-ID', { hour12: false });
}, 1000);

// Initialize Map
async function initMap() {
  map = L.map('map', {
    center: [-0.278, 111.475], // Kalbar center
    zoom: 6,
    zoomControl: false,
    attributionControl: false
  });

  L.control.zoom({ position: 'bottomright' }).addTo(map);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
  }).addTo(map);

  await loadData();
  autoRefreshId = setInterval(loadData, 30000); // refresh 30s
}

// Load GeoJSON and Data
async function loadData() {
  if(refreshBtn) refreshBtn.classList.add('loading');
  
  try {
    const res = await fetch('/api/status');
    const responseData = await res.json();
    allData = responseData.data || responseData;
    
    updateStats(allData);
    renderTable(allData);
    checkGoldenWindow(allData);
    
    await updateMapLayer();
    
    if(loadingOverlay) loadingOverlay.style.display = 'none';
    liveStatusEl.textContent = 'Live · Data diperbarui';
  } catch(err) {
    console.error(err);
    liveStatusEl.textContent = 'Offline · Gagal memuat data';
    showToast('Gagal terhubung ke server API', 'error');
  } finally {
    if(refreshBtn) refreshBtn.classList.remove('loading');
  }
}

async function updateMapLayer() {
  if(!geoLayer) {
    try {
      const geoRes = await fetch('/api/geojson');
      const geojson = await geoRes.json();
      
      geoLayer = L.geoJSON(geojson, {
        style: feature => {
          const kabName = getFeatureName(feature);
          const data = allData.find(d => d.kabupaten.replace(/KOTA /g, '') === kabName.replace(/KOTA /g, ''));
          const status = data ? data.status : 'AMAN';
          
          return {
            fillColor: colors[getStatusClass(status)] || colors.AMAN,
            weight: 2,
            opacity: 1,
            color: 'white',
            fillOpacity: 0.6
          };
        },
        onEachFeature: (feature, layer) => {
          const kabName = getFeatureName(feature);
          const data = allData.find(d => d.kabupaten.replace(/KOTA /g, '') === kabName.replace(/KOTA /g, ''));
          
          if(data) {
            let beritaHTML = "";
            if (data.detail_berita && data.detail_berita.length > 0) {
              beritaHTML = '<div style="margin-top: 8px; border-top: 1px solid #eee; padding-top: 5px;">';
              beritaHTML += '<b style="font-size: 11px; color: #555;">Berita DBD Terkini:</b>';
              data.detail_berita.slice(0, 3).forEach(news => {
                const ringkasJudul = news.judul.length > 40 ? news.judul.substring(0, 40) + '...' : news.judul;
                beritaHTML += `
                  <div style="font-size: 11px; margin-top: 4px; line-height: 1.3;">
                    • <a href="${news.link}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 500;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">${ringkasJudul}</a>
                  </div>
                `;
              });
              beritaHTML += '</div>';
            } else {
              beritaHTML = '<div style="margin-top: 6px; font-size: 11px; color: #777; font-style: italic;">Tidak ada berita DBD terkini.</div>';
            }

            const popupContent = `
              <div class="map-popup" style="color: #222; font-family: sans-serif; min-width: 180px;">
                <h4 style="margin:0; font-weight:bold; font-size: 14px; border-bottom: 1px solid #eee; padding-bottom: 3px; color: #111;">${data.kabupaten}</h4>
                <div style="font-size: 12px; margin-top:6px; line-height: 1.4; color: #444;">
                  Status: <b style="color: ${data.status.includes('AMAN') ? '#28a745' : (data.status.includes('SIAGA') ? '#dc3545' : '#ff9900')}">${data.status.split(' ')[0]}</b><br>
                  Suhu: <b>${data.suhu}°C</b> | Lembap: <b>${data.kelembapan}%</b><br>
                  Curah Hujan 7D: <b>${data.hujan_7d} mm</b><br>
                  Jumlah Berita: <b>${data.berita}</b>
                </div>
                ${beritaHTML}
              </div>
            `;
            layer.bindPopup(popupContent);
          }
        }
      }).addTo(map);
    } catch(err) {
      console.error("GeoJSON Error:", err);
    }
  } else {
    // Refresh styles and popups
    geoLayer.setStyle(feature => {
      const kabName = getFeatureName(feature);
      const data = allData.find(d => d.kabupaten.replace(/KOTA /g, '') === kabName.replace(/KOTA /g, ''));
      const status = data ? data.status : 'AMAN';
      
      return {
        fillColor: colors[getStatusClass(status)] || colors.AMAN,
        fillOpacity: 0.6
      };
    });

    // Rebind popups dengan data terbaru
    geoLayer.eachLayer(layer => {
      const kabName = getFeatureName(layer.feature);
      const data = allData.find(d => d.kabupaten.replace(/KOTA /g, '') === kabName.replace(/KOTA /g, ''));
      if (data) {
        let beritaHTML = "";
        if (data.detail_berita && data.detail_berita.length > 0) {
          beritaHTML = '<div style="margin-top: 8px; border-top: 1px solid #eee; padding-top: 5px;">';
          beritaHTML += '<b style="font-size: 11px; color: #555;">Berita DBD Terkini:</b>';
          data.detail_berita.slice(0, 3).forEach(news => {
            const ringkasJudul = news.judul.length > 40 ? news.judul.substring(0, 40) + '...' : news.judul;
            beritaHTML += `
              <div style="font-size: 11px; margin-top: 4px; line-height: 1.3;">
                • <a href="${news.link}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 500;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">${ringkasJudul}</a>
              </div>
            `;
          });
          beritaHTML += '</div>';
        } else {
          beritaHTML = '<div style="margin-top: 6px; font-size: 11px; color: #777; font-style: italic;">Tidak ada berita DBD terkini.</div>';
        }

        const popupContent = `
          <div class="map-popup" style="color: #222; font-family: sans-serif; min-width: 180px;">
            <h4 style="margin:0; font-weight:bold; font-size: 14px; border-bottom: 1px solid #eee; padding-bottom: 3px; color: #111;">${data.kabupaten}</h4>
            <div style="font-size: 12px; margin-top:6px; line-height: 1.4; color: #444;">
              Status: <b style="color: ${data.status.includes('AMAN') ? '#28a745' : (data.status.includes('SIAGA') ? '#dc3545' : '#ff9900')}">${data.status.split(' ')[0]}</b><br>
              Suhu: <b>${data.suhu}°C</b> | Lembap: <b>${data.kelembapan}%</b><br>
              Curah Hujan 7D: <b>${data.hujan_7d} mm</b><br>
              Jumlah Berita: <b>${data.berita}</b>
            </div>
            ${beritaHTML}
          </div>
        `;
        layer.bindPopup(popupContent);
      }
    });
  }
}

function getFeatureName(feature) {
  const props = feature.properties || {};
  const candidates = [
    props.regency, props.NAME_2, props.name, props.Name, props.KABKOT,
    props.WADMKK, props.kabupaten, props.Kabupaten
  ];
  for(let c of candidates) {
    if(c) return c.toUpperCase();
  }
  return '';
}

function updateStats(data) {
  let aman = 0, waspada = 0, siaga = 0, golden = 0;
  data.forEach(d => {
    const sClass = getStatusClass(d.status);
    if(sClass === 'AMAN') aman++;
    else if(sClass === 'WASPADA') waspada++;
    else if(sClass === 'SIAGA') siaga++;
    if(d.golden_window) golden++;
  });
  
  document.getElementById('stat-aman').textContent = aman;
  document.getElementById('stat-waspada').textContent = waspada;
  document.getElementById('stat-siaga').textContent = siaga;
  document.getElementById('stat-golden').textContent = golden;
}

let selectedKabupaten = '';

function renderTable(data) {
  const term = searchInput.value.toLowerCase();
  tbody.innerHTML = '';
  
  data.filter(d => d.kabupaten.toLowerCase().includes(term)).forEach(d => {
    const tr = document.createElement('tr');
    if(d.golden_window) tr.classList.add('golden-row');
    
    const statusClass = getStatusClass(d.status).toLowerCase();
    
    tr.innerHTML = `
      <td>${d.kabupaten}</td>
      <td><span class="badge badge-${statusClass}">${d.status}</span></td>
      <td>${d.suhu}°C</td>
      <td>${d.berita}</td>
    `;
    tbody.appendChild(tr);
  });
}

function filterTable() {
  renderTable(allData);
}

// Sidebar toggle
function toggleGolden() {
  goldenSidebar.classList.toggle('open');
}

function checkGoldenWindow(data) {
  const golden = data.filter(d => d.golden_window);
  
  if(golden.length > 0) {
    goldenTab.style.display = 'flex';
    goldenTabCount.textContent = golden.length;
    
    goldenAreasEl.innerHTML = '';
    golden.forEach(d => {
      const div = document.createElement('div');
      div.className = 'golden-card';
      div.innerHTML = `
        <div class="golden-card-header">
          <span class="golden-card-title">${d.kabupaten}</span>
        </div>
        <div class="golden-card-body">
          <div class="golden-card-metric"><span>Suhu:</span> <strong>${d.suhu}°C</strong></div>
          <div class="golden-card-metric"><span>Berita:</span> <strong>${d.berita}</strong></div>
        </div>
        <div class="golden-card-actions">
          <button class="btn-abate" onclick="event.stopPropagation(); openInterventionModal('abate', '${d.kabupaten}')">🧪 Abate</button>
          <button class="btn-broadcast" onclick="event.stopPropagation(); openInterventionModal('broadcast', '${d.kabupaten}')">📲 Blast</button>
        </div>
      `;
      div.addEventListener('click', () => {
        focusKabupaten(d.kabupaten);
      });
      goldenAreasEl.appendChild(div);
    });
    
    // Auto open if not explicitly closed
    if(!goldenSidebar.classList.contains('closed-by-user')) {
      goldenSidebar.classList.add('open');
    }
  } else {
    goldenTab.style.display = 'none';
    goldenSidebar.classList.remove('open');
  }
}

// Focus map on selected kabupaten
function focusKabupaten(kabName) {
  if (!geoLayer) return;
  geoLayer.eachLayer(layer => {
    const layerKab = getFeatureName(layer.feature);
    if (layerKab.replace(/KOTA /g, '') === kabName.replace(/KOTA /g, '').toUpperCase()) {
      map.fitBounds(layer.getBounds(), { maxZoom: 8, padding: [50, 50] });
      layer.openPopup();
    }
  });
}

// Modal open with dynamic data
function openInterventionModal(type, kabupaten) {
  selectedKabupaten = kabupaten;
  if (type === 'abate') {
    document.getElementById('abate-wilayah').textContent = kabupaten;
  } else if (type === 'broadcast') {
    document.getElementById('broadcast-wilayah-title').textContent = kabupaten;
    document.getElementById('blast-wilayah').textContent = kabupaten;
  }
  openModal(type);
}

// Modals
function openModal(id) {
  document.getElementById(`modal-${id}`).classList.add('active');
}

function closeModal(id) {
  document.getElementById(`modal-${id}`).classList.remove('active');
}

function confirmAbate() {
  showToast(`Perintah Preemptive Abatization telah dikirim untuk ${selectedKabupaten}!`, 'success');
  closeModal('abate');
}

function confirmBroadcast() {
  showToast(`Simulasi Broadcast Blast WA berhasil dikirim ke warga ${selectedKabupaten}!`, 'success');
  closeModal('broadcast');
}

function showToast(msg, type='info') {
  const container = document.getElementById('toast-container');
  if(!container) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => {
    t.classList.add('fadeout');
    setTimeout(() => t.remove(), 300);
  }, 3000);
}

// Keep track of user closing sidebar manually
document.querySelector('.golden-close').addEventListener('click', () => {
  goldenSidebar.classList.add('closed-by-user');
});

// Init
initMap();
