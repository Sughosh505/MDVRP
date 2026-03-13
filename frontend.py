"""
frontend.py
-----------
Self-contained HTML/CSS/JS frontend.
Map: Leaflet.js + OpenStreetMap (free, no API key required).

Features:
  - Click map to place depots and customers
  - Configure vehicle capacity and number of vehicles per depot
  - POST to /api/solve, render color-coded routes on map
  - Summary table of routes below the map
"""

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MDVRP Solver</title>

<!-- Leaflet.js — free, no API key -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f1117;
    color: #e0e0e0;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ───────────────────────── */
  header {
    background: #1a1d27;
    border-bottom: 1px solid #2a2d3a;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;
  }
  header h1 {
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    letter-spacing: 0.5px;
  }
  header .subtitle {
    font-size: 12px;
    color: #666;
  }

  /* ── Main layout ──────────────────── */
  .main {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* ── Sidebar ──────────────────────── */
  .sidebar {
    width: 280px;
    background: #1a1d27;
    border-right: 1px solid #2a2d3a;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    flex-shrink: 0;
  }

  .section {
    padding: 14px 16px;
    border-bottom: 1px solid #2a2d3a;
  }
  .section-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #666;
    margin-bottom: 10px;
  }

  /* Mode toggle */
  .mode-row {
    display: flex;
    gap: 6px;
  }
  .mode-btn {
    flex: 1;
    padding: 8px 4px;
    border: 1px solid #2a2d3a;
    background: #0f1117;
    color: #aaa;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.15s;
    text-align: center;
  }
  .mode-btn.active {
    border-color: #4f8ef7;
    background: rgba(79,142,247,0.12);
    color: #4f8ef7;
    font-weight: 600;
  }
  .mode-btn:hover:not(.active) {
    border-color: #444;
    color: #ccc;
  }

  /* Input fields */
  .field {
    margin-bottom: 10px;
  }
  label {
    display: block;
    font-size: 11px;
    color: #888;
    margin-bottom: 4px;
  }
  input[type="number"] {
    width: 100%;
    padding: 7px 10px;
    background: #0f1117;
    border: 1px solid #2a2d3a;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
  }
  input[type="number"]:focus { border-color: #4f8ef7; }

  /* Depot/Customer lists */
  .item-list {
    display: flex;
    flex-direction: column;
    gap: 5px;
    max-height: 130px;
    overflow-y: auto;
  }
  .item-row {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #0f1117;
    border: 1px solid #2a2d3a;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
  }
  .item-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .item-label { flex: 1; color: #ccc; }
  .item-remove {
    cursor: pointer;
    color: #555;
    font-size: 14px;
    line-height: 1;
    padding: 0 2px;
  }
  .item-remove:hover { color: #e74c3c; }
  .empty-hint {
    font-size: 11px;
    color: #444;
    text-align: center;
    padding: 8px;
  }

  /* Buttons */
  .btn {
    width: 100%;
    padding: 10px;
    border: none;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-primary {
    background: #4f8ef7;
    color: #fff;
  }
  .btn-primary:hover { background: #3a7de0; }
  .btn-primary:disabled { background: #2a3a5a; color: #555; cursor: not-allowed; }
  .btn-secondary {
    background: #2a2d3a;
    color: #aaa;
    margin-top: 6px;
  }
  .btn-secondary:hover { background: #333645; color: #ddd; }

  /* Status */
  .status-box {
    padding: 10px 12px;
    border-radius: 6px;
    font-size: 12px;
    margin-top: 2px;
  }
  .status-idle    { background: #1a1d27; color: #555; border: 1px solid #2a2d3a; }
  .status-loading { background: rgba(79,142,247,0.1); color: #4f8ef7; border: 1px solid rgba(79,142,247,0.3); }
  .status-ok      { background: rgba(39,174,96,0.1); color: #27ae60; border: 1px solid rgba(39,174,96,0.3); }
  .status-error   { background: rgba(231,76,60,0.1); color: #e74c3c; border: 1px solid rgba(231,76,60,0.3); }

  /* ── Map area ─────────────────────── */
  .map-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  #map {
    flex: 1;
    min-height: 0;
  }

  /* ── Results table ────────────────── */
  .results-panel {
    height: 220px;
    background: #1a1d27;
    overflow-y: auto;
    flex-shrink: 0;
    position: relative;
    max-height: 90vh;
    min-height: 100px;
    display: flex;
    flex-direction: column;
  }
  
  .resizer {
    height: 8px;
    background: #2a2d3a;
    cursor: ns-resize;
    display: flex;
    align-items: center;
    justify-content: center;
    border-top: 1px solid #1a1d27;
    border-bottom: 1px solid #1a1d27;
    z-index: 50;
    flex-shrink: 0;
  }
  .resizer:hover, .resizer.dragging {
    background: #4f8ef7;
  }
  .resizer::after {
    content: "";
    width: 30px;
    height: 2px;
    background: #666;
    border-radius: 2px;
  }

  .table-container {
    flex: 1;
    overflow-y: auto;
  }

  .results-panel table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
  }
  .results-panel thead th {
    background: #14161f;
    color: #888;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.8px;
    padding: 10px 12px;
    text-align: left;
    position: sticky;
    top: 0;
    border-bottom: 1px solid #2a2d3a;
    z-index: 10;
  }
  .results-panel tbody td {
    padding: 10px 12px;
    border-bottom: 1px solid #1e2130;
    color: #ccc;
  }
  .color-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    margin-right: 6px;
    vertical-align: middle;
  }
  .no-results {
    padding: 20px;
    text-align: center;
    color: #444;
    font-size: 12px;
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

  /* ── Results Modal ────────────────── */
  .modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(4px);
    z-index: 1000;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .modal-overlay.open {
    display: flex;
  }
  .modal-box {
    background: #1a1d27;
    border: 1px solid #2a2d3a;
    border-radius: 14px;
    width: 100%;
    max-width: 1100px;
    max-height: 88vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 80px rgba(0,0,0,0.7);
    overflow: hidden;
    animation: modalIn 0.2s ease;
  }
  @keyframes modalIn {
    from { opacity: 0; transform: translateY(20px) scale(0.97); }
    to   { opacity: 1; transform: translateY(0)  scale(1); }
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 24px 14px;
    border-bottom: 1px solid #2a2d3a;
    flex-shrink: 0;
  }
  .modal-title {
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .modal-badge {
    font-size: 11px;
    font-weight: 600;
    background: rgba(79,142,247,0.18);
    color: #4f8ef7;
    border: 1px solid rgba(79,142,247,0.3);
    border-radius: 20px;
    padding: 2px 10px;
  }
  .modal-close {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: 1px solid #2a2d3a;
    background: #0f1117;
    color: #aaa;
    font-size: 18px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
    line-height: 1;
  }
  .modal-close:hover { background: rgba(231,76,60,0.15); border-color: #e74c3c; color: #e74c3c; }
  .modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }
  .modal-body::-webkit-scrollbar { width: 6px; }
  .modal-body::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
  .modal-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }
  .modal-table thead th {
    background: #14161f;
    color: #888;
    font-weight: 700;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 1px;
    padding: 14px 20px;
    text-align: left;
    position: sticky;
    top: 0;
    border-bottom: 2px solid #2a2d3a;
    z-index: 5;
  }
  .modal-table tbody tr {
    transition: background 0.12s;
  }
  .modal-table tbody tr:hover {
    background: rgba(79,142,247,0.06);
  }
  .modal-table tbody td {
    padding: 13px 20px;
    border-bottom: 1px solid #1e2130;
    color: #ddd;
    font-size: 14px;
    vertical-align: middle;
  }
  .modal-table .route-stops {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    color: #aaa;
    word-break: break-all;
    white-space: normal;
  }
  .util-bar {
    display: inline-block;
    height: 6px;
    border-radius: 3px;
    margin-left: 8px;
    vertical-align: middle;
    transition: width 0.3s;
  }
  .modal-footer {
    padding: 12px 24px;
    border-top: 1px solid #2a2d3a;
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    flex-shrink: 0;
  }
  .btn-view-results {
    background: rgba(79,142,247,0.15);
    border: 1px solid rgba(79,142,247,0.4);
    color: #4f8ef7;
    width: 100%;
    padding: 10px;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 6px;
    transition: all 0.15s;
    display: none;
  }
  .btn-view-results:hover { background: rgba(79,142,247,0.28); }
</style>
</head>

<body>

<header>
  <div>
    <h1>MDVRP Solver</h1>
    <div class="subtitle">Multi-Depot Vehicle Routing — Google OR-Tools</div>
  </div>
</header>

<div class="main">

  <!-- ── Sidebar ───────────────────────────── -->
  <div class="sidebar">

    <!-- Place mode -->
    <div class="section">
      <div class="section-title">Place on Map</div>
      <div class="mode-row">
        <div class="mode-btn active" id="btn-depot" onclick="setMode('depot')">🏭 Depot</div>
        <div class="mode-btn" id="btn-customer" onclick="setMode('customer')">📦 Customer</div>
      </div>
    </div>

    <!-- Vehicle settings -->
    <div class="section">
      <div class="section-title">Vehicle Settings</div>
      <div class="field">
        <label>Vehicle Capacity (units)</label>
        <input type="number" id="vehicle-capacity" value="100" min="1" max="10000">
      </div>
      <div class="field">
        <label>Vehicles per Depot (default)</label>
        <input type="number" id="vehicles-per-depot" value="3" min="1" max="20">
      </div>
    </div>

    <!-- Customer demand -->
    <div class="section">
      <div class="section-title">Customer Demand (when placing)</div>
      <div class="field">
        <label>Default Demand</label>
        <input type="number" id="default-demand" value="20" min="1" max="10000">
      </div>
    </div>

    <!-- Depot list -->
    <div class="section">
      <div class="section-title">Depots <span id="depot-count" style="color:#666">(0)</span></div>
      <div class="item-list" id="depot-list">
        <div class="empty-hint">Click map to place depots</div>
      </div>
    </div>

    <!-- Customer list -->
    <div class="section">
      <div class="section-title">Customers <span id="customer-count" style="color:#666">(0)</span></div>
      <div class="item-list" id="customer-list">
        <div class="empty-hint">Click map to place customers</div>
      </div>
    </div>

    <!-- Actions -->
    <div class="section">
      <button class="btn btn-primary" id="solve-btn" onclick="solve()" disabled>
        Solve Routes
      </button>
      <button class="btn btn-secondary" onclick="clearAll()">Clear All</button>
      <button class="btn-view-results" id="view-results-btn" onclick="openResultsModal()">
        📋 View Results Table
      </button>
    </div>

    <!-- Status -->
    <div class="section">
      <div class="status-box status-idle" id="status-box">
        Add depots and customers, then solve.
      </div>
    </div>

  </div><!-- /sidebar -->

  <!-- ── Map + Results ─────────────────────── -->
  <div class="map-panel">
    <div id="map"></div>
    <div class="results-panel" id="results-panel">
      <div class="resizer" id="resizer"></div>
      <div class="table-container" id="table-container">
        <div class="no-results" style="padding:20px;">Solve a problem to see route details</div>
      </div>
    </div>
  </div>

</div><!-- /main -->

<!-- ── Results Modal ─────────────────────────── -->
<div class="modal-overlay" id="results-modal" onclick="onOverlayClick(event)">
  <div class="modal-box">
    <div class="modal-header">
      <div class="modal-title">
        📋 Route Results
        <span class="modal-badge" id="modal-route-count"></span>
      </div>
      <button class="modal-close" onclick="closeResultsModal()" title="Close (Esc)">✕</button>
    </div>
    <div class="modal-body">
      <div id="modal-table-container">
        <div class="no-results" style="padding:40px;text-align:center;color:#444">No results yet</div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" style="width:auto;padding:9px 20px" onclick="closeResultsModal()">Close</button>
    </div>
  </div>
</div>

<script>
// ─────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────

const state = {
  mode: 'depot',        // 'depot' | 'customer'
  depots: [],           // [{id, lon, lat, num_vehicles, marker}]
  customers: [],        // [{id, lon, lat, demand, marker}]
  routeLayers: [],      // Leaflet polylines
  depotCounter: 0,
  customerCounter: 0,
};

// Route colors — one per depot, cycles if more depots than colors
const DEPOT_COLORS = [
  '#4f8ef7','#e74c3c','#2ecc71','#f39c12',
  '#9b59b6','#1abc9c','#e67e22','#e91e63',
];

const ROUTE_SHADES = [
  // Per depot: darker shades for multiple vehicles
  ['#4f8ef7','#2a6adc','#1a4fad'],
  ['#e74c3c','#c0392b','#922b21'],
  ['#2ecc71','#27ae60','#1e8449'],
  ['#f39c12','#d68910','#9a6407'],
  ['#9b59b6','#8e44ad','#6c3483'],
  ['#1abc9c','#17a589','#148f77'],
  ['#e67e22','#ca6f1e','#9a7d0a'],
  ['#e91e63','#c2185b','#880e4f'],
];

// ─────────────────────────────────────────────────────
// Map Setup — Leaflet + OpenStreetMap (free, no key)
// ─────────────────────────────────────────────────────

const map = L.map('map').setView([40.72, -73.96], 12);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 19,
}).addTo(map);

map.on('click', onMapClick);

// ─────────────────────────────────────────────────────
// Marker Icons
// ─────────────────────────────────────────────────────

function depotIcon(color) {
  return L.divIcon({
    className: '',
    html: `<div style="
      width:28px;height:28px;
      background:${color};
      border:3px solid #fff;
      border-radius:6px;
      display:flex;align-items:center;justify-content:center;
      font-size:13px;
      box-shadow:0 2px 8px rgba(0,0,0,0.5);
    ">🏭</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function customerIcon(color, label) {
  return L.divIcon({
    className: '',
    html: `<div style="
      width:22px;height:22px;
      background:${color};
      border:2px solid rgba(255,255,255,0.7);
      border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:9px;font-weight:700;color:#fff;
      box-shadow:0 1px 5px rgba(0,0,0,0.5);
    ">${label}</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

// ─────────────────────────────────────────────────────
// Map click handler
// ─────────────────────────────────────────────────────

function onMapClick(e) {
  const { lat, lng } = e.latlng;

  if (state.mode === 'depot') {
    placeDepot(lng, lat);
  } else {
    placeCustomer(lng, lat);
  }
}

function placeDepot(lon, lat) {
  const id = state.depotCounter++;
  const color = DEPOT_COLORS[id % DEPOT_COLORS.length];
  const numVehicles = parseInt(document.getElementById('vehicles-per-depot').value) || 3;

  const marker = L.marker([lat, lon], { icon: depotIcon(color) })
    .addTo(map)
    .bindPopup(`
      <b>Depot ${id}</b><br>
      Vehicles: ${numVehicles}<br>
      <small>${lat.toFixed(5)}, ${lon.toFixed(5)}</small>
    `);

  state.depots.push({ id, lon, lat, num_vehicles: numVehicles, color, marker });
  updateSidebar();
  updateSolveBtn();
}

function placeCustomer(lon, lat) {
  const id = state.customerCounter++;
  const demand = parseInt(document.getElementById('default-demand').value) || 20;
  const label = id < 100 ? String(id) : '·';

  const marker = L.marker([lat, lon], { icon: customerIcon('#64748b', label) })
    .addTo(map)
    .bindPopup(`
      <b>Customer ${id}</b><br>
      Demand: ${demand}<br>
      <small>${lat.toFixed(5)}, ${lon.toFixed(5)}</small>
    `);

  state.customers.push({ id, lon, lat, demand, marker });
  updateSidebar();
  updateSolveBtn();
}

// ─────────────────────────────────────────────────────
// Sidebar updates
// ─────────────────────────────────────────────────────

function setMode(mode) {
  state.mode = mode;
  document.getElementById('btn-depot').classList.toggle('active', mode === 'depot');
  document.getElementById('btn-customer').classList.toggle('active', mode === 'customer');
}

function updateSidebar() {
  // Depots
  document.getElementById('depot-count').textContent = `(${state.depots.length})`;
  const depotList = document.getElementById('depot-list');
  if (state.depots.length === 0) {
    depotList.innerHTML = '<div class="empty-hint">Click map to place depots</div>';
  } else {
    depotList.innerHTML = state.depots.map(d => `
      <div class="item-row">
        <div class="item-dot" style="background:${d.color}"></div>
        <div class="item-label">Depot ${d.id} · ${d.num_vehicles} vehicles</div>
        <div class="item-remove" onclick="removeDepot(${d.id})">×</div>
      </div>
    `).join('');
  }

  // Customers
  document.getElementById('customer-count').textContent = `(${state.customers.length})`;
  const custList = document.getElementById('customer-list');
  if (state.customers.length === 0) {
    custList.innerHTML = '<div class="empty-hint">Click map to place customers</div>';
  } else {
    custList.innerHTML = state.customers.map(c => `
      <div class="item-row">
        <div class="item-dot" style="background:#64748b"></div>
        <div class="item-label">C${c.id} · demand: ${c.demand}</div>
        <div class="item-remove" onclick="removeCustomer(${c.id})">×</div>
      </div>
    `).join('');
  }
}

function updateSolveBtn() {
  const btn = document.getElementById('solve-btn');
  btn.disabled = state.depots.length === 0 || state.customers.length === 0;
}

// ─────────────────────────────────────────────────────
// Remove items
// ─────────────────────────────────────────────────────

function removeDepot(id) {
  const idx = state.depots.findIndex(d => d.id === id);
  if (idx === -1) return;
  map.removeLayer(state.depots[idx].marker);
  state.depots.splice(idx, 1);
  updateSidebar();
  updateSolveBtn();
}

function removeCustomer(id) {
  const idx = state.customers.findIndex(c => c.id === id);
  if (idx === -1) return;
  map.removeLayer(state.customers[idx].marker);
  state.customers.splice(idx, 1);
  updateSidebar();
  updateSolveBtn();
}

function clearAll() {
  state.depots.forEach(d => map.removeLayer(d.marker));
  state.customers.forEach(c => map.removeLayer(c.marker));
  state.routeLayers.forEach(l => map.removeLayer(l));
  state.depots = [];
  state.customers = [];
  state.routeLayers = [];
  state.depotCounter = 0;
  state.customerCounter = 0;
  updateSidebar();
  updateSolveBtn();
  setStatus('idle', 'Add depots and customers, then solve.');
  document.getElementById('table-container').innerHTML =
    '<div class="no-results" style="padding:20px;">Solve a problem to see route details</div>';
}

// ─────────────────────────────────────────────────────
// Solver call
// ─────────────────────────────────────────────────────

async function solve() {
  if (state.depots.length === 0 || state.customers.length === 0) return;

  // Clear previous routes
  state.routeLayers.forEach(l => map.removeLayer(l));
  state.routeLayers = [];

  setStatus('loading', `Solving ${state.customers.length} customers across ${state.depots.length} depots…`);
  document.getElementById('solve-btn').disabled = true;

  const payload = {
    depots: state.depots.map(d => ({
      id: d.id, lon: d.lon, lat: d.lat, num_vehicles: d.num_vehicles
    })),
    customers: state.customers.map(c => ({
      id: c.id, lon: c.lon, lat: c.lat, demand: c.demand
    })),
    vehicle_capacity: parseInt(document.getElementById('vehicle-capacity').value) || 100,
  };

  try {
    const resp = await fetch('/api/solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await resp.json();

    if (!resp.ok) {
      setStatus('error', `Error: ${data.error}`);
      return;
    }

    await renderRoutes(data);
    renderResultsTable(data);

    const distKm = data.total_distance_km;
    const unserved = data.unserved_customers.length;
    const msg = unserved > 0
      ? `${data.num_routes} routes · ${distKm} km · ⚠ ${unserved} unserved`
      : `${data.num_routes} routes · ${distKm} km total`;
    setStatus('ok', msg);

  } catch (err) {
    setStatus('error', `Request failed: ${err.message}`);
  } finally {
    document.getElementById('solve-btn').disabled = false;
  }
}

// ─────────────────────────────────────────────────────
// Route rendering
// ─────────────────────────────────────────────────────

async function renderRoutes(data) {
  // Build lookup: customerId → {lon, lat}
  const custMap = {};
  state.customers.forEach(c => { custMap[c.id] = c; });

  // depot index → color index
  const depotColorIndex = {};
  state.depots.forEach((d, i) => { depotColorIndex[d.id] = i; });

  // vehicle count per depot (to pick shade)
  const depotVehicleCount = {};

  await Promise.all(data.routes.map(async route => {
    const depotIdx = depotColorIndex[route.depot_id] ?? 0;
    depotVehicleCount[route.depot_id] = depotVehicleCount[route.depot_id] || 0;
    const shadeIdx = depotVehicleCount[route.depot_id] % 3;
    depotVehicleCount[route.depot_id]++;

    const color = (ROUTE_SHADES[depotIdx] || ROUTE_SHADES[0])[shadeIdx];

    // Find depot coords
    const depot = state.depots.find(d => d.id === route.depot_id);
    if (!depot) return;

    // Build coordinate path: depot → customers → depot
    const fallbackCoords = [[depot.lat, depot.lon]];
    const osrmCoords = [`${depot.lon},${depot.lat}`];

    route.customer_ids.forEach(cid => {
      const c = custMap[cid];
      if (c) {
        fallbackCoords.push([c.lat, c.lon]);
        osrmCoords.push(`${c.lon},${c.lat}`);
      }
    });

    fallbackCoords.push([depot.lat, depot.lon]);
    osrmCoords.push(`${depot.lon},${depot.lat}`);

    let pathCoords = fallbackCoords;
    try {
      // Fetch geometry from OSRM
      const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${osrmCoords.join(';')}?overview=full&geometries=geojson`;
      const res = await fetch(osrmUrl);
      if (res.ok) {
        const json = await res.json();
        if (json.code === 'Ok' && json.routes && json.routes.length > 0) {
          // OSRM returns coordinates as [lon, lat]. Leaflet needs [lat, lon].
          pathCoords = json.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
        }
      }
    } catch (e) {
      console.warn("OSRM fetch failed, falling back to straight lines", e);
    }

    // Draw polyline
    const line = L.polyline(pathCoords, {
      color,
      weight: 3,
      opacity: 0.85,
      dashArray: null,
    }).addTo(map);

    // Arrows along line
    line.bindPopup(`
      <b>Depot ${route.depot_id} · Vehicle ${route.vehicle_id}</b><br>
      Customers: ${route.customer_ids.join(', ')}<br>
      Load: ${route.load}<br>
      Distance: ${(route.total_distance_m / 1000).toFixed(2)} km
    `);

    state.routeLayers.push(line);

    // Re-color customer markers with depot color
    route.customer_ids.forEach(cid => {
      const c = custMap[cid];
      if (!c) return;
      c.marker.setIcon(customerIcon(color, cid < 100 ? String(cid) : '·'));
    });
  }));
}

// ─────────────────────────────────────────────────────
// Results table
// ─────────────────────────────────────────────────────

function renderResultsTable(data) {
  // Also update the small inline panel table-container
  const container = document.getElementById('table-container');

  if (data.routes.length === 0) {
    container.innerHTML =
      '<div class="no-results" style="padding:20px;">No routes generated</div>';
    document.getElementById('view-results-btn').style.display = 'none';
    return;
  }

  const depotColorIndex = {};
  state.depots.forEach((d, i) => { depotColorIndex[d.id] = i; });
  const depotVehicleCount = {};
  const cap = parseInt(document.getElementById('vehicle-capacity').value) || 100;

  const rows = data.routes.map(route => {
    const depotIdx = depotColorIndex[route.depot_id] ?? 0;
    depotVehicleCount[route.depot_id] = depotVehicleCount[route.depot_id] || 0;
    const shadeIdx = depotVehicleCount[route.depot_id] % 3;
    depotVehicleCount[route.depot_id]++;
    const color = (ROUTE_SHADES[depotIdx] || ROUTE_SHADES[0])[shadeIdx];

    const util = Math.round((route.load / cap) * 100);
    const distKm = (route.total_distance_m / 1000).toFixed(2);
    const utilColor = util > 90 ? '#e74c3c' : util > 65 ? '#f39c12' : '#27ae60';

    // Compact row for inline panel
    const inlineRow = `<tr>
      <td><span class="color-swatch" style="background:${color}"></span>D${route.depot_id} · V${route.vehicle_id}</td>
      <td>${route.customer_ids.length} stops</td>
      <td>${route.load} / ${cap} <small style="color:#555">(${util}%)</small></td>
      <td>${distKm} km</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#666">
        ${route.customer_ids.join(' → ')}
      </td>
    </tr>`;

    // Rich row for modal
    const modalRow = `<tr>
      <td><span class="color-swatch" style="background:${color};width:14px;height:14px"></span>
          <strong>D${route.depot_id}</strong> · V${route.vehicle_id}</td>
      <td>${route.customer_ids.length} stops</td>
      <td>
        ${route.load} / ${cap}
        <small style="color:${utilColor};font-weight:600"> ${util}%</small>
        <span class="util-bar" style="width:${Math.max(4, util * 0.6)}px;background:${utilColor}"></span>
      </td>
      <td><strong>${distKm}</strong> km</td>
      <td class="route-stops">${route.customer_ids.join(' → ')}</td>
    </tr>`;

    return { inlineRow, modalRow };
  });

  const unservedInline = data.unserved_customers.length > 0
    ? `<tr><td colspan="5" style="color:#e74c3c;padding:8px 12px">
        ⚠ Unserved: ${data.unserved_customers.join(', ')}
       </td></tr>`
    : '';

  const unservedModal = data.unserved_customers.length > 0
    ? `<tr><td colspan="5" style="color:#e74c3c;padding:14px 20px;font-weight:600">
        ⚠ Unserved customers: ${data.unserved_customers.join(', ')}
       </td></tr>`
    : '';

  const tableHeader = `<thead><tr>
    <th>Vehicle</th><th>Stops</th><th>Load</th><th>Distance</th><th>Route Sequence</th>
  </tr></thead>`;

  // Populate inline panel
  container.innerHTML = `
    <table>
      ${tableHeader}
      <tbody>${rows.map(r => r.inlineRow).join('')}${unservedInline}</tbody>
    </table>`;

  // Populate modal
  document.getElementById('modal-table-container').innerHTML = `
    <table class="modal-table">
      ${tableHeader}
      <tbody>${rows.map(r => r.modalRow).join('')}${unservedModal}</tbody>
    </table>`;

  // Update badge and show button
  document.getElementById('modal-route-count').textContent =
    `${data.routes.length} routes · ${data.total_distance_km} km`;
  document.getElementById('view-results-btn').style.display = 'block';

  // Auto-open the modal
  openResultsModal();
}

function openResultsModal() {
  document.getElementById('results-modal').classList.add('open');
}

function closeResultsModal() {
  document.getElementById('results-modal').classList.remove('open');
}

function onOverlayClick(e) {
  if (e.target === document.getElementById('results-modal')) closeResultsModal();
}

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeResultsModal();
});

// ─────────────────────────────────────────────────────
// Resizer Tool
// ─────────────────────────────────────────────────────

const resizer = document.getElementById('resizer');
const panel = document.getElementById('results-panel');
let isResizing = false;
let startY;
let startHeight;

resizer.addEventListener('mousedown', function(e) {
  isResizing = true;
  startY = e.clientY;
  startHeight = parseInt(document.defaultView.getComputedStyle(panel).height, 10);
  resizer.classList.add('dragging');
  
  // Prevent map from capturing mouse events during resize
  document.body.style.cursor = 'ns-resize';
  map.dragging.disable();
  if (map.scrollWheelZoom) map.scrollWheelZoom.disable();
  e.preventDefault();
});

document.addEventListener('mousemove', function(e) {
  if (!isResizing) return;
  const dy = startY - e.clientY; // Negative if moving down
  let newHeight = startHeight + dy;
  
  // constrain height
  if (newHeight < 100) newHeight = 100;
  
  panel.style.height = newHeight + 'px';
  map.invalidateSize(); // Tell Leaflet the map height changed
});

document.addEventListener('mouseup', function() {
  if (!isResizing) return;
  isResizing = false;
  resizer.classList.remove('dragging');
  document.body.style.cursor = '';
  map.dragging.enable();
  if (map.scrollWheelZoom) map.scrollWheelZoom.enable();
  map.invalidateSize();
});

// ─────────────────────────────────────────────────────
// Status helper
// ─────────────────────────────────────────────────────

function setStatus(type, msg) {
  const box = document.getElementById('status-box');
  box.className = `status-box status-${type}`;
  box.textContent = msg;
}

// ─────────────────────────────────────────────────────
// Load sample data (New York area)
// ─────────────────────────────────────────────────────

function loadSample() {
  clearAll();

  // 2 depots
  placeDepot(-74.006, 40.7128);   // Manhattan
  placeDepot(-73.944, 40.6782);   // Brooklyn

  // 12 customers scattered around NYC
  const customers = [
    [-73.987, 40.748], [-73.975, 40.761], [-73.962, 40.771],
    [-73.998, 40.730], [-74.015, 40.718], [-73.952, 40.756],
    [-73.940, 40.700], [-73.958, 40.688], [-73.972, 40.693],
    [-73.931, 40.715], [-73.920, 40.730], [-73.968, 40.740],
  ];
  customers.forEach(([lon, lat]) => placeCustomer(lon, lat));
}

// Auto-load sample on page load
loadSample();
</script>
</body>
</html>
"""
