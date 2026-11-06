/**
 * Main application logic for Refribreak Inventory Core (RIC).
 * Vanilla JavaScript (No frameworks) handling SPA navigation, reactive tables,
 * modals, and OE physical document rendering.
 */

// Application state
const state = {
  currentView: 'dashboard',
  activeWarehouseId: '',
  warehouses: [],
  categories: [],
  products: [],
  customers: [],
  suppliers: [],
  inventoryItems: [],
  orders: [],
  lots: [],
  activeOrderToPrint: null
};

// Utilities
function formatCOP(amount) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0
  }).format(amount || 0);
}

function formatDate(isoStr) {
  if (!isoStr) return '-';
  try {
    const parts = isoStr.split('T')[0].split('-');
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  } catch (e) {
    return isoStr;
  }
}

function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : '✕'}</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

// Navigation
function switchView(viewName) {
  state.currentView = viewName;
  
  // Update sidebar active link
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === viewName);
  });

  // Switch visible panel
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `view-${viewName}`);
  });

  // Load view-specific data
  if (viewName === 'dashboard') loadDashboard();
  else if (viewName === 'inventory') loadInventory();
  else if (viewName === 'purchases') loadPurchasesView();
  else if (viewName === 'orders') loadOrders();
  else if (viewName === 'lots') loadLots();
  else if (viewName === 'kardex') loadKardex();
  else if (viewName === 'audit') loadAudit();
}

// Data loaders
async function loadInitialMetadata() {
  try {
    const [whs, cats, prods, custs, sups] = await Promise.all([
      apiClient.getWarehouses(),
      apiClient.getCategories(),
      apiClient.getProducts(),
      apiClient.getCustomers(),
      apiClient.getSuppliers()
    ]);

    state.warehouses = whs;
    state.categories = cats;
    state.products = prods;
    state.customers = custs;
    state.suppliers = sups;

    // Populate warehouse selects
    const whSelect = document.getElementById('globalWarehouseSelect');
    if (whSelect) {
      whSelect.innerHTML = `<option value="">Todas las Sedes / Bodegas</option>` + 
        whs.map(w => `<option value="${w.id}">${w.name} (${w.code})</option>`).join('');
    }

    // Populate category filter in inventory
    const catFilter = document.getElementById('filterCategorySelect');
    if (catFilter) {
      catFilter.innerHTML = `<option value="">Todas las Categorías</option>` +
        cats.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    }

    // Populate modals selects
    populateModalSelects();

  } catch (err) {
    showToast('Error cargando metadatos iniciales: ' + err.message, 'error');
  }
}

function populateModalSelects() {
  // Modal Entrada
  const entryWh = document.getElementById('entryWarehouse');
  if (entryWh) {
    entryWh.innerHTML = state.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
  }
  const entryProd = document.getElementById('entryProduct');
  if (entryProd) {
    entryProd.innerHTML = state.products.map(p => `<option value="${p.id}">${p.name} (${p.sku})</option>`).join('');
  }
  const entrySup = document.getElementById('entrySupplier');
  if (entrySup) {
    entrySup.innerHTML = state.suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  }

  // Modal Orden OE
  const oeCust = document.getElementById('oeCustomer');
  if (oeCust) {
    oeCust.innerHTML = state.customers.map(c => `<option value="${c.id}">${c.name} - NIT ${c.nit}</option>`).join('');
  }
  const oeWh = document.getElementById('oeWarehouse');
  if (oeWh) {
    oeWh.innerHTML = state.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
  }
}

// 1. Dashboard View
async function loadDashboard() {
  try {
    const summary = await apiClient.getDashboardSummary(state.activeWarehouseId);

    document.getElementById('metricTotalValue').textContent = formatCOP(summary.total_inventory_value_cop);
    document.getElementById('metricTotalUnits').textContent = summary.total_available_units.toLocaleString('es-CO');
    document.getElementById('metricExpiringCount').textContent = summary.expiring_soon_lots_count;
    document.getElementById('metricCriticalStock').textContent = summary.critical_stock_count;
    document.getElementById('metricPendingOrders').textContent = summary.pending_delivery_orders;
    document.getElementById('metricMonthlyWaste').textContent = formatCOP(summary.monthly_waste_value_cop);

    // Update nav badge
    const badge = document.getElementById('navAlertBadge');
    if (badge) {
      badge.textContent = summary.expiring_soon_lots_count;
      badge.style.display = summary.expiring_soon_lots_count > 0 ? 'inline-block' : 'none';
    }

    // Load recent alerts list inside dashboard
    const lots = await apiClient.getLots(state.activeWarehouseId);
    const criticalLots = lots.filter(l => l.days_to_expiration <= 7);
    
    const container = document.getElementById('dashboardAlertsList');
    if (container) {
      if (criticalLots.length === 0) {
        container.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:#64748b;">No hay lotes en riesgo de vencimiento próximo en los próximos 7 días.</td></tr>`;
      } else {
        container.innerHTML = criticalLots.map(l => {
          const badgeClass = l.days_to_expiration < 0 ? 'badge-red' : (l.days_to_expiration <= 2 ? 'badge-red' : 'badge-amber');
          const statusText = l.days_to_expiration < 0 ? 'Vencido' : `Vence en ${l.days_to_expiration} días`;
          return `
            <tr>
              <td><strong>${l.lot_number}</strong></td>
              <td>${l.product_name}</td>
              <td>${l.warehouse_name}</td>
              <td><strong>${l.remaining_qty}</strong> remanentes</td>
              <td><span class="badge-pill ${badgeClass}">${statusText}</span></td>
            </tr>
          `;
        }).join('');
      }
    }
  } catch (err) {
    showToast('Error cargando métricas: ' + err.message, 'error');
  }
}

// 2. Inventory View (Sellerskills & Airtable style)
async function loadInventory() {
  try {
    const catId = document.getElementById('filterCategorySelect')?.value || '';
    const query = document.getElementById('inventorySearchInput')?.value || '';

    const items = await apiClient.getInventory(state.activeWarehouseId, catId, query);
    state.inventoryItems = items;

    const tbody = document.getElementById('inventoryTableBody');
    if (!tbody) return;

    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:28px; color:#64748b;">No se encontraron productos con los filtros seleccionados.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map(item => {
      // FEFO Pill
      let fefoBadge = '<span class="badge-pill badge-gray">No Perecedero</span>';
      if (item.is_perishable) {
        if (item.expiration_status === 'EXPIRED') {
          fefoBadge = `<span class="badge-pill badge-red">Vencido (${formatDate(item.earliest_expiration)})</span>`;
        } else if (item.expiration_status === 'WARNING_EXPIRING_SOON') {
          fefoBadge = `<span class="badge-pill badge-amber">Vence en ${item.days_to_expiration}d</span>`;
        } else if (item.earliest_expiration) {
          fefoBadge = `<span class="badge-pill badge-green">Vigente (${formatDate(item.earliest_expiration)})</span>`;
        } else {
          fefoBadge = `<span class="badge-pill badge-gray">Sin lote</span>`;
        }
      }

      // Stock Pill
      let stockPill = `<strong style="font-size:14px;">${item.available_qty}</strong> ${item.unit}`;
      if (item.is_under_min) {
        stockPill = `<span class="badge-pill badge-red">${item.available_qty} ${item.unit} (Mín: ${item.min_stock})</span>`;
      }

      return `
        <tr>
          <td><input type="checkbox" class="row-checkbox"></td>
          <td>
            <strong>${item.product_name}</strong>
            <div style="font-size:11px; color:#64748b;">${item.warehouse_name}</div>
          </td>
          <td><span class="badge-pill badge-purple">${item.sku}</span></td>
          <td><span class="badge-pill badge-blue">${item.category_name}</span></td>
          <td>${stockPill}</td>
          <td>${item.reserved_qty}</td>
          <td>${formatCOP(item.weighted_avg_cost)}</td>
          <td><strong>${formatCOP(item.total_value_cop)}</strong></td>
          <td>${fefoBadge}</td>
        </tr>
      `;
    }).join('');

    document.getElementById('inventoryCountLabel').textContent = `${items.length} productos listados`;
  } catch (err) {
    showToast('Error cargando inventario: ' + err.message, 'error');
  }
}

// 3. Orders View (Shopware inspired + Refribreak physical preview)
async function loadOrders() {
  try {
    const orders = await apiClient.getOrders();
    state.orders = orders;

    const tbody = document.getElementById('ordersTableBody');
    if (!tbody) return;

    if (orders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:28px; color:#64748b;">No hay órdenes de entrega registradas.</td></tr>`;
      return;
    }

    tbody.innerHTML = orders.map(ord => {
      let statusBadge = '<span class="badge-pill badge-amber">Aprobada</span>';
      if (ord.status === 'DISPATCHED') {
        statusBadge = '<span class="badge-pill badge-green">Despachada FEFO</span>';
      } else if (ord.status === 'DRAFT') {
        statusBadge = '<span class="badge-pill badge-gray">Borrador</span>';
      }

      const canDispatch = ord.status !== 'DISPATCHED';

      return `
        <tr>
          <td><input type="checkbox"></td>
          <td><strong>${ord.consecutive_oe}</strong></td>
          <td>
            <strong>${ord.customer_name}</strong>
            <div style="font-size:11px; color:#64748b;">${ord.delivery_address}</div>
          </td>
          <td>
            ${ord.delivery_day_name} ${formatDate(ord.delivery_date)}
            <div style="font-size:11px; color:#64748b;">${ord.arrival_time || '-'} a ${ord.end_time || '-'}</div>
          </td>
          <td>
            <strong>${ord.quantity}</strong> x ${ord.service_type} (${ord.service_description})
          </td>
          <td>${statusBadge}</td>
          <td>${ord.advisor_name || 'Nays Navarro'}</td>
          <td>
            <div class="action-btn-group">
              <button class="btn btn-secondary btn-sm" onclick="openPrintModal('${ord.id}')" title="Ver formato de confirmación físico">
                📄 Ver Remisión
              </button>
              ${canDispatch ? `
                <button class="btn btn-success btn-sm" onclick="handleDispatchOrder('${ord.id}')" title="Despachar y descontar lotes FEFO">
                  🚚 Despachar
                </button>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join('');

    document.getElementById('ordersCountLabel').textContent = `${orders.length} órdenes registradas`;
  } catch (err) {
    showToast('Error cargando órdenes: ' + err.message, 'error');
  }
}

// 4. Lots View
async function loadLots() {
  try {
    const lots = await apiClient.getLots(state.activeWarehouseId);
    state.lots = lots;

    const tbody = document.getElementById('lotsTableBody');
    if (!tbody) return;

    if (lots.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:28px; color:#64748b;">No hay lotes registrados para esta sede.</td></tr>`;
      return;
    }

    tbody.innerHTML = lots.map(l => {
      let badge = '<span class="badge-pill badge-green">Vigente</span>';
      if (l.is_expired) {
        badge = '<span class="badge-pill badge-red">Expirado</span>';
      } else if (l.is_expiring_soon) {
        badge = `<span class="badge-pill badge-amber">Expira en ${l.days_to_expiration}d</span>`;
      }

      return `
        <tr>
          <td><strong>${l.lot_number}</strong></td>
          <td><strong>${l.product_name}</strong></td>
          <td>${l.warehouse_name}</td>
          <td>${l.supplier_name || 'No especificado'}</td>
          <td><strong>${l.remaining_qty}</strong> / ${l.initial_qty}</td>
          <td>${formatCOP(l.unit_cost)}</td>
          <td>${formatDate(l.expiration_date)}</td>
          <td>${badge}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    showToast('Error cargando lotes: ' + err.message, 'error');
  }
}

// 5. Kardex View
async function loadKardex() {
  try {
    const movs = await apiClient.getMovements(state.activeWarehouseId);
    const tbody = document.getElementById('kardexTableBody');
    if (!tbody) return;

    if (movs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:28px; color:#64748b;">No hay movimientos registrados.</td></tr>`;
      return;
    }

    const typeLabels = {
      'IN_PURCHASE': '<span class="badge-pill badge-green">Entrada Compra</span>',
      'OUT_DISPATCH': '<span class="badge-pill badge-blue">Salida Despacho FEFO</span>',
      'WASTE': '<span class="badge-pill badge-red">Merma / Baja</span>',
      'ADJUSTMENT': '<span class="badge-pill badge-purple">Ajuste Conteo</span>'
    };

    tbody.innerHTML = movs.map(m => `
      <tr>
        <td><strong>${m.consecutive}</strong></td>
        <td>${typeLabels[m.movement_type] || m.movement_type}</td>
        <td>${m.warehouse_name}</td>
        <td>${m.operator_name}</td>
        <td>${formatCOP(m.total_cost)}</td>
        <td><small>${m.notes || m.reference_doc || '-'}</small></td>
        <td>${new Date(m.created_at).toLocaleString('es-CO')}</td>
      </tr>
    `).join('');
  } catch (err) {
    showToast('Error cargando kardex: ' + err.message, 'error');
  }
}

// 6. Audit View
async function loadAudit() {
  try {
    const logs = await apiClient.getAuditLogs();
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;

    tbody.innerHTML = logs.map(l => `
      <tr>
        <td><small>${new Date(l.timestamp).toLocaleString('es-CO')}</small></td>
        <td><strong>${l.user_alias}</strong></td>
        <td><span class="badge-pill badge-gray">${l.action}</span></td>
        <td>${l.entity_type} (${l.entity_id || '-'})</td>
        <td><code>${JSON.stringify(l.details).substring(0, 90)}...</code></td>
      </tr>
    `).join('');
  } catch (err) {
    showToast('Error cargando bitácora de auditoría: ' + err.message, 'error');
  }
}

// Actions & Handlers
async function handleDispatchOrder(orderId) {
  if (!confirm('¿Desea despachar esta orden y descontar automáticamente los lotes FEFO?')) return;
  try {
    const res = await apiClient.dispatchOrder(orderId);
    showToast(`Orden ${res.consecutive_oe} despachada correctamente. Lotes FEFO descontados.`);
    loadOrders();
    loadDashboard();
  } catch (err) {
    showToast('Error despachando orden: ' + err.message, 'error');
  }
}

// Modals Handling
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

// Open Remisión OE Modal (renders identical physical sheet to Image 4)
async function openPrintModal(orderId) {
  try {
    const order = await apiClient.getOrderDetail(orderId);
    state.activeOrderToPrint = order;

    // Fill sheet fields defensively
    const setSafeText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val != null ? String(val) : '';
    };

    setSafeText('printOeConsecutive', order.consecutive_oe || 'OE 7217');
    setSafeText('printOeDate', `${order.delivery_day_name || 'Viernes'} ${order.delivery_date || ''}`);
    setSafeText('printOeCustomer', order.customer_name || 'Liid Comunicacion y Creatividad SAS');
    setSafeText('printOeAddress', order.delivery_address || 'Trv 23 97 -73 Ofc 212 Bogota');
    setSafeText('printOeArrivalTime', order.arrival_time || '7:30 AM');
    setSafeText('printOeStartTime', order.start_time || '8:30 AM');
    setSafeText('printOeEndTime', order.end_time || '11:30 AM');
    setSafeText('printOeDepartureTime', order.departure_time || '6:40 AM');
    setSafeText('printOeTransporter', order.transporter_name || 'Carlos Rodríguez');
    setSafeText('printOeTransportMode', order.transport_mode || 'Carro');
    setSafeText('printOePlate', order.vehicle_plate || 'WMA-452');
    setSafeText('printOeAdvisor', order.advisor_name || 'Nays Navarro');
    setSafeText('printOeRequestedBy', order.requested_by || 'Leonardo Ramírez');
    setSafeText('printOeReceivedBy', order.received_by || 'Leonardo Ramírez');
    setSafeText('printOePhone', order.receiver_phone || '3504163975');

    // Products table
    setSafeText('printOeQty', order.quantity != null ? order.quantity : 1);
    setSafeText('printOeType', order.service_type || 'Desayuno');
    setSafeText('printOeDesc', order.service_description || 'Servido');
    setSafeText('printOeProductDetail', order.product_detail || '');

    // Equipment items (copia correo autorización)
    const eq = order.equipment || {};
    const eqContainer = document.getElementById('printOeEquipmentGrid');
    if (eqContainer) {
      const keys = Object.keys(eq);
      const half = Math.ceil(keys.length / 2);
      const col1 = keys.slice(0, half);
      const col2 = keys.slice(half);

      const renderCol = (list) => list.map(k => `
        <div class="oe-equipment-row">
          <span>${k.replace(/_/g, ' ')}</span>
          <span class="qty">${eq[k]}</span>
        </div>
      `).join('');

      eqContainer.innerHTML = `
        <div class="oe-equipment-col">${renderCol(col1)}</div>
        <div class="oe-equipment-col">${renderCol(col2)}</div>
      `;
    }

    openModal('modalPrintOE');
  } catch (err) {
    showToast('Error cargando orden para impresión: ' + err.message, 'error');
  }
}

// AI Invoice Simulation Handler
async function handleSimulateAiInvoice() {
  const btn = document.getElementById('btnRunAi');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Extrayendo con Agente IA...';
  }

  try {
    const res = await apiClient.simulateAiExtraction();
    showToast(`✓ Agente IA procesó factura de ${res.supplier_identified.name} en ${res.ai_processing_time_ms}ms`);

    // Auto-fill first item
    const item = res.extracted_items[0];
    if (item) {
      document.getElementById('entryProduct').value = item.suggested_product_id;
      document.getElementById('entryLot').value = item.lot_number;
      document.getElementById('entryQty').value = item.quantity;
      document.getElementById('entryCost').value = item.unit_cost;
      document.getElementById('entryExpDate').value = item.suggested_expiration;
      document.getElementById('entryDocRef').value = res.invoice_metadata.invoice_number;
      document.getElementById('entrySupplier').value = res.supplier_identified.id;
    }
  } catch (err) {
    showToast('Error en extracción IA: ' + err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '⚡ Simular Extracción Factura IA';
    }
  }
}

// Form Submissions
async function submitPurchaseEntry(e) {
  e.preventDefault();
  const data = {
    warehouse_id: document.getElementById('entryWarehouse').value,
    product_id: document.getElementById('entryProduct').value,
    lot_number: document.getElementById('entryLot').value,
    expiration_date: document.getElementById('entryExpDate').value,
    quantity: parseFloat(document.getElementById('entryQty').value),
    unit_cost: parseFloat(document.getElementById('entryCost').value),
    supplier_id: document.getElementById('entrySupplier').value,
    reference_doc: document.getElementById('entryDocRef').value,
    notes: document.getElementById('entryNotes').value,
    operator_name: 'Nicolas Santa'
  };

  try {
    const res = await apiClient.registerPurchaseEntry(data);
    showToast(`✓ Entrada ${res.consecutive} confirmada. Nuevo costo prom: ${formatCOP(res.new_weighted_avg_cost)}`);
    closeModal('modalPurchaseEntry');
    document.getElementById('formPurchaseEntry').reset();
    loadDashboard();
    if (state.currentView === 'inventory') loadInventory();
    if (state.currentView === 'lots') loadLots();
  } catch (err) {
    showToast('Error al registrar entrada: ' + err.message, 'error');
  }
}

async function submitCreateOrder(e) {
  e.preventDefault();
  const data = {
    customer_id: document.getElementById('oeCustomer').value,
    warehouse_id: document.getElementById('oeWarehouse').value,
    delivery_date: document.getElementById('oeDeliveryDate').value,
    delivery_day_name: document.getElementById('oeDayName').value,
    delivery_address: document.getElementById('oeAddress').value,
    order_date: new Date().toISOString().split('T')[0],
    arrival_time: document.getElementById('oeArrivalTime').value,
    start_time: document.getElementById('oeStartTime').value,
    end_time: document.getElementById('oeEndTime').value,
    departure_time: document.getElementById('oeDepartureTime').value,
    transporter_name: document.getElementById('oeTransporter').value,
    transport_mode: document.getElementById('oeTransportMode').value,
    vehicle_plate: document.getElementById('oePlate').value,
    advisor_name: document.getElementById('oeAdvisor').value,
    requested_by: document.getElementById('oeRequestedBy').value,
    received_by: document.getElementById('oeReceivedBy').value,
    receiver_phone: document.getElementById('oeReceiverPhone').value,
    service_type: document.getElementById('oeServiceType').value,
    service_description: document.getElementById('oeServiceDesc').value,
    product_detail: document.getElementById('oeProductDetail').value,
    quantity: parseInt(document.getElementById('oeQuantity').value, 10),
    observations: document.getElementById('oeObservations').value
  };

  try {
    const res = await apiClient.createOrder(data);
    showToast(`✓ ${res.message}`);
    closeModal('modalCreateOE');
    document.getElementById('formCreateOE').reset();
    loadOrders();
    loadDashboard();
  } catch (err) {
    showToast('Error creando orden: ' + err.message, 'error');
  }
}

// Setup Event Listeners
document.addEventListener('DOMContentLoaded', async () => {
  // Navigation
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      switchView(el.dataset.view);
    });
  });

  // Global Warehouse Selector
  const whSelect = document.getElementById('globalWarehouseSelect');
  if (whSelect) {
    whSelect.addEventListener('change', (e) => {
      state.activeWarehouseId = e.target.value;
      switchView(state.currentView);
    });
  }

  // Global Search in Header
  const globalSearch = document.getElementById('globalSearchInput');
  if (globalSearch) {
    globalSearch.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      if (state.currentView === 'inventory') {
        const invSearch = document.getElementById('inventorySearchInput');
        if (invSearch) {
          invSearch.value = q;
          loadInventory();
        }
      }
    });
  }

  // Inventory Table search & category filter
  document.getElementById('inventorySearchInput')?.addEventListener('input', () => loadInventory());
  document.getElementById('filterCategorySelect')?.addEventListener('change', () => loadInventory());

  // Siigo +Crear dropdown
  const btnToggleCreate = document.getElementById('btnToggleCreateMenu');
  const createDropdown = document.getElementById('createMenuDropdown');

  if (btnToggleCreate && createDropdown) {
    btnToggleCreate.addEventListener('click', (e) => {
      e.stopPropagation();
      createDropdown.classList.toggle('active');
    });

    document.addEventListener('click', () => {
      createDropdown.classList.remove('active');
    });
  }

  // Forms
  document.getElementById('formPurchaseEntry')?.addEventListener('submit', submitPurchaseEntry);
  document.getElementById('formCreateOE')?.addEventListener('submit', submitCreateOrder);
  document.getElementById('btnRunAi')?.addEventListener('click', handleSimulateAiInvoice);
  document.getElementById('formAddQuotation')?.addEventListener('submit', handleAddQuotationSubmit);

  // Initialize
  await loadInitialMetadata();
  switchView('dashboard');
});

function closeCreateMenu() {
  document.getElementById('createMenuDropdown')?.classList.remove('active');
}
/* =========================================================================
   PROCUREMENT, COMPARATOR & REPLENISHMENT MODULE (RIC Unified)
   ========================================================================= */

const purchaseState = {
  currentTab: 'suggestions',
  suggestions: [],
  rfqList: [],
  selectedRfqId: null,
  comparisonMatrix: null,
  purchaseOrders: []
};

function switchPurchaseTab(tab) {
  purchaseState.currentTab = tab;

  // Toggle tab buttons
  document.querySelectorAll('.sub-tab-btn').forEach(btn => {
    const btnTab = btn.id.replace('tab-', '');
    btn.classList.toggle('active', btnTab === tab);
  });

  // Toggle tab panes
  ['suggestions', 'comparator', 'purchase-orders'].forEach(t => {
    const pane = document.getElementById('pane-' + t);
    if (pane) {
      pane.style.display = (t === tab) ? 'block' : 'none';
      pane.classList.toggle('active', t === tab);
    }
  });

  if (tab === 'suggestions') {
    loadReplenishmentSuggestions();
  } else if (tab === 'comparator') {
    loadRFQList();
  } else if (tab === 'purchase-orders') {
    loadPurchaseOrders();
  }
}

async function loadPurchasesView() {
  const whSel = document.getElementById('suggWarehouseFilter');
  if (whSel && state.warehouses && state.warehouses.length > 0) {
    whSel.innerHTML = '<option value="">Todas las sedes</option>' +
      state.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
    if (state.activeWarehouseId) {
      whSel.value = state.activeWarehouseId;
    }
  }
  switchPurchaseTab(purchaseState.currentTab);
}

// -----------------------------------------------------------------------------
// TAB 1: REPLENISHMENT SUGGESTIONS
// -----------------------------------------------------------------------------
async function loadReplenishmentSuggestions() {
  const tbody = document.getElementById('suggestionsTableBody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:28px; color:#64748b;">Calculando necesidades de stock y reservas...</td></tr>';

  const whId = document.getElementById('suggWarehouseFilter')?.value || state.activeWarehouseId || '';
  try {
    const data = await apiClient.getReplenishmentSuggestions(whId);
    purchaseState.suggestions = data || [];
    renderSuggestions();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:#dc2626; padding:20px;">Error al cargar sugerencias: ${err.message}</td></tr>`;
  }
}

function renderSuggestions() {
  const tbody = document.getElementById('suggestionsTableBody');
  if (!tbody) return;

  const list = purchaseState.suggestions;
  if (!list || list.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align:center; padding:40px; color:#16a34a;">
          <div style="font-size:32px; margin-bottom:8px;">✅</div>
          <strong>¡Todo el inventario cumple con el nivel de stock mínimo!</strong>
          <p style="font-size:12px; color:#64748b; margin-top:4px;">No hay déficit en las sedes consultadas.</p>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = list.map((s, idx) => {
    const urgencyClass = s.urgency === 'CRITICAL' ? 'critical' : s.urgency === 'LOW_STOCK' ? 'low-stock' : 'normal';
    const urgencyLabel = s.urgency === 'CRITICAL' ? '🔴 CRÍTICO (Agotado)' : s.urgency === 'LOW_STOCK' ? '🟡 Bajo Stock' : '🟢 Normal';
    const deficitColor = s.deficit_qty > 0 ? '#dc2626' : '#16a34a';

    return `
      <tr>
        <td><input type="checkbox" class="sugg-chk" data-idx="${idx}" value="${idx}" checked></td>
        <td><strong>${s.product_name}</strong><div style="font-size:11px; color:#64748b;">${s.sku}</div></td>
        <td><span class="badge-pill badge-gray">${s.category_name}</span></td>
        <td>${s.warehouse_name}</td>
        <td style="text-align:right;">${s.available_qty} ${s.unit}</td>
        <td style="text-align:right;">${s.min_stock} ${s.unit}</td>
        <td style="text-align:right; color:${deficitColor}; font-weight:700;">${s.deficit_qty > 0 ? '-' + s.deficit_qty : '0'} ${s.unit}</td>
        <td style="text-align:right; font-weight:700; color:#0074e8;">${s.suggested_qty} ${s.unit}</td>
        <td style="text-align:right; font-weight:600;">${formatCOP(s.estimated_total_cost)}</td>
        <td><span class="urgency-badge ${urgencyClass}">${urgencyLabel}</span></td>
      </tr>
    `;
  }).join('');
}

function toggleSelectAllSuggestions(master) {
  document.querySelectorAll('.sugg-chk').forEach(chk => chk.checked = master.checked);
}

function getSelectedSuggestions() {
  const checked = Array.from(document.querySelectorAll('.sugg-chk:checked'));
  return checked.map(chk => purchaseState.suggestions[parseInt(chk.dataset.idx)]).filter(Boolean);
}

async function openCreateRFQFromSuggestions() {
  const selected = getSelectedSuggestions();
  if (selected.length === 0) {
    showToast('Selecciona al menos un producto de la lista de sugerencias', 'error');
    return;
  }

  const warehouseId = selected[0].warehouse_id;
  const items = selected.map(s => ({
    product_id: s.product_id,
    requested_qty: s.suggested_qty,
    target_unit_price: s.last_cost || 0,
    notes: `Déficit: ${s.deficit_qty} ${s.unit} (Stock Mín: ${s.min_stock})`
  }));

  try {
    const rfq = await apiClient.createPurchaseRequisition({
      warehouse_id: warehouseId,
      notes: `Reabastecimiento sugerido por inventario (${selected.length} productos)`,
      items: items
    });

    showToast(`✅ Solicitud de Compra creada: ${rfq.code}`, 'success');
    purchaseState.selectedRfqId = rfq.id;
    switchPurchaseTab('comparator');
  } catch (err) {
    showToast(`Error creando solicitud: ${err.message}`, 'error');
  }
}

// -----------------------------------------------------------------------------
// TAB 2: QUOTATION COMPARATOR
// -----------------------------------------------------------------------------
async function loadRFQList() {
  const sel = document.getElementById('rfqSelectForComparison');
  if (!sel) return;

  sel.innerHTML = '<option value="">Cargando solicitudes de compra...</option>';

  try {
    const list = await apiClient.getPurchaseRequisitions('', '');
    purchaseState.rfqList = list || [];

    if (purchaseState.rfqList.length === 0) {
      sel.innerHTML = '<option value="">— No hay Solicitudes de Compra registradas —</option>';
      loadComparisonMatrix();
      return;
    }

    sel.innerHTML = '<option value="">— Selecciona una Solicitud de Compra (RFQ) —</option>' +
      purchaseState.rfqList.map(r =>
        `<option value="${r.id}" ${r.id === purchaseState.selectedRfqId ? 'selected' : ''}>${r.code} — ${r.warehouse_name} (${r.status})</option>`
      ).join('');

    if (purchaseState.selectedRfqId) {
      sel.value = purchaseState.selectedRfqId;
      loadComparisonMatrix();
    } else if (purchaseState.rfqList.length > 0) {
      // Auto-select the first pending RFQ if available
      const pendingRfq = purchaseState.rfqList.find(r => r.status === 'PENDING') || purchaseState.rfqList[0];
      sel.value = pendingRfq.id;
      purchaseState.selectedRfqId = pendingRfq.id;
      loadComparisonMatrix();
    }
  } catch (err) {
    showToast(`Error cargando solicitudes: ${err.message}`, 'error');
  }
}

async function loadComparisonMatrix() {
  const sel = document.getElementById('rfqSelectForComparison');
  const reqId = sel?.value;
  purchaseState.selectedRfqId = reqId || null;

  const container = document.getElementById('comparisonMatrixContainer');
  if (!container) return;

  if (!reqId) {
    container.innerHTML = `
      <div style="text-align:center; padding:60px; color:#64748b;">
        <div style="font-size:48px; margin-bottom:12px;">⚖️</div>
        <p style="font-size:16px; font-weight:700; color:#0f172a;">Selecciona una solicitud de compra para ver el comparador</p>
        <p style="font-size:13px; color:#64748b; margin-top:4px;">El sistema contrasta lado a lado las cotizaciones recibidas de proveedores y calcula la mejor opción técnica y económica.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = '<div style="text-align:center; padding:40px; color:#64748b;">Calculando matriz comparativa y mejor oferta...</div>';

  try {
    purchaseState.comparisonMatrix = await apiClient.getQuotationComparison(reqId);
    renderComparisonMatrix();
  } catch (err) {
    container.innerHTML = `
      <div style="text-align:center; padding:40px; color:#dc2626;">
        <p style="font-size:15px; font-weight:600;">⚠️ ${err.message}</p>
        <p style="font-size:13px; color:#64748b; margin-top:8px;">Agrega al menos una cotización de proveedor con el botón "+ Agregar Cotización de Proveedor" para ver la comparativa.</p>
      </div>
    `;
  }
}

function renderComparisonMatrix() {
  const mx = purchaseState.comparisonMatrix;
  const container = document.getElementById('comparisonMatrixContainer');
  if (!container || !mx) return;

  if (!mx.quotations || mx.quotations.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:60px; color:#64748b; background:#f8fafc; border-radius:12px; border:1px dashed #cbd5e1;">
        <div style="font-size:48px; margin-bottom:12px;">📋</div>
        <p style="font-size:16px; font-weight:700; color:#0f172a;">Sin cotizaciones aún para esta solicitud (${mx.requisition_code})</p>
        <p style="font-size:13px; margin-top:6px;">Haz clic en <strong>"+ Agregar Cotización de Proveedor"</strong> para ingresar ofertas de distintos proveedores y compararlas.</p>
        <button class="btn btn-primary btn-sm" style="margin-top:14px;" onclick="openAddQuotationModal()">+ Agregar Primera Cotización</button>
      </div>
    `;
    return;
  }

  const quotes = mx.quotations;
  const products = mx.products || [];
  const winner = mx.winner;
  const fastest = mx.fastest_delivery;

  let html = '';

  // Winner highlight card
  if (winner) {
    const saving = mx.savings_vs_most_expensive;
    html += `
      <div class="winner-card" style="display:flex; justify-content:space-between; align-items:center; background:#ecfdf5; border:2px solid #10b981; border-radius:12px; padding:16px 20px; margin-bottom:20px;">
        <div style="display:flex; align-items:center; gap:16px;">
          <div style="font-size:36px;">🏆</div>
          <div>
            <div style="font-size:12px; font-weight:700; color:#059669; text-transform:uppercase; letter-spacing:0.5px;">🟢 Mejor Precio — Proveedor Recomendado</div>
            <div style="font-size:18px; font-weight:800; color:#064e3b; margin-top:2px;">${winner.supplier_name}</div>
            <div style="font-size:13px; color:#047857; margin-top:2px;">
              Total: <strong>${formatCOP(winner.grand_total)}</strong>
              ${saving && saving.amount_cop > 0 ? ` · Ahorro estimado: <strong style="color:#047857;">${formatCOP(saving.amount_cop)} (${saving.pct}%)</strong> vs la cotización más cara` : ''}
              · Entrega en <strong>${winner.delivery_days} días</strong>
            </div>
          </div>
        </div>
        <div>
          ${winner.status === 'PENDING' ? `
            <button class="btn btn-primary" style="background:#059669; border-color:#059669; font-weight:700; padding:10px 18px;" onclick="awardQuotation('${winner.id}')">
              🏆 Adjudicar esta OC al Ganador
            </button>
          ` : `
            <span class="urgency-badge normal" style="font-size:13px; padding:6px 12px;">✅ Orden Adjudicada</span>
          `}
        </div>
      </div>
    `;
  }

  // Comparison Matrix Table
  html += `
    <div class="card-table-container">
      <div class="table-responsive">
        <table class="custom-table" style="font-size:13px;">
          <thead>
            <tr style="background:#0f172a; color:#ffffff;">
              <th style="color:#ffffff; font-weight:700; min-width:200px;">Criterio / Producto</th>
              ${quotes.map(q => {
                let badges = '';
                if (q.id === winner?.id) badges += '<span style="display:inline-block; margin-left:6px; background:#10b981; color:#ffffff; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px;">🟢 MEJOR PRECIO</span>';
                if (q.id === fastest?.id && fastest?.id !== winner?.id) badges += '<span style="display:inline-block; margin-left:6px; background:#eab308; color:#ffffff; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px;">🟡 MÁS RÁPIDO</span>';
                return `<th style="color:#ffffff; text-align:right; font-weight:700; min-width:180px;">${q.supplier_name}<br>${badges}</th>`;
              }).join('')}
            </tr>
          </thead>
          <tbody>
  `;

  // Product rows
  products.forEach(prod => {
    html += `
      <tr>
        <td>
          <strong>${prod.product_name}</strong>
          <div style="font-size:11px; color:#64748b;">Cant. requerida: <strong>${prod.requested_qty} ${prod.unit}</strong></div>
        </td>
    `;

    quotes.forEach(q => {
      const item = (q.items || []).find(i => i.product_id === prod.product_id);
      const price = item?.unit_price;
      const isBest = prod.best_price_quote_id === q.id;
      const isWorst = prod.worst_price_quote_id === q.id && quotes.length > 1;
      const cellBg = isBest ? '#f0fdf4' : isWorst ? '#fef2f2' : 'transparent';
      const cellColor = isBest ? '#166534' : isWorst ? '#991b1b' : '#0f172a';
      const bestPill = isBest ? '<span style="color:#16a34a; font-size:11px; font-weight:700; margin-left:4px;">★</span>' : '';

      html += `
        <td style="text-align:right; background:${cellBg}; color:${cellColor}; font-weight:600;">
          ${price != null ? formatCOP(price) + bestPill : '—'}
          <div style="font-size:11px; color:#64748b; font-weight:normal;">Total: ${price != null ? formatCOP(price * prod.requested_qty) : '—'}</div>
        </td>
      `;
    });

    html += `</tr>`;
  });

  // Summary rows: Subtotal, Shipping, Delivery Days, Grand Total
  html += `
      <tr style="font-weight:700; background:#f8fafc; border-top:2px solid #cbd5e1;">
        <td>Subtotal Mercancía</td>
        ${quotes.map(q => `<td style="text-align:right;">${formatCOP(q.subtotal)}</td>`).join('')}
      </tr>
      <tr>
        <td>Flete / Transporte</td>
        ${quotes.map(q => `<td style="text-align:right;">${formatCOP(q.shipping_cost)}</td>`).join('')}
      </tr>
      <tr>
        <td>Tiempo de Entrega</td>
        ${quotes.map(q => {
          const isFastest = q.id === fastest?.id;
          return `<td style="text-align:right; ${isFastest ? 'color:#854d0e; font-weight:700;' : ''}">${q.delivery_days} días hábiles${isFastest ? ' ⚡' : ''}</td>`;
        }).join('')}
      </tr>
      <tr>
        <td>Condición de Pago</td>
        ${quotes.map(q => `<td style="text-align:right; font-size:12px; color:#64748b;">${q.payment_terms || 'Contado'}</td>`).join('')}
      </tr>
      <tr style="font-size:15px; font-weight:800; background:#f1f5f9; border-top:2px solid #0f172a;">
        <td>TOTAL ORDEN (COP)</td>
        ${quotes.map(q => {
          const isWinner = q.id === winner?.id;
          return `
            <td style="text-align:right; ${isWinner ? 'color:#166534; background:#dcfce7; font-weight:900;' : ''}">
              ${formatCOP(q.grand_total)}
              ${isWinner ? '<br><span style="font-size:10px; color:#15803d;">RECOMENDADO</span>' : ''}
            </td>
          `;
        }).join('')}
      </tr>
      <tr>
        <td style="font-weight:600;">Acción</td>
        ${quotes.map(q => `
          <td style="text-align:right;">
            ${q.status === 'PENDING' ? `
              <button class="btn btn-primary btn-sm" onclick="awardQuotation('${q.id}')">
                Elegir Proveedor
              </button>
            ` : `
              <span class="urgency-badge normal">Adjudicada</span>
            `}
          </td>
        `).join('')}
      </tr>
    </tbody>
  </table>
  </div>
  </div>
  `;

  container.innerHTML = html;
}

async function awardQuotation(quoteId) {
  if (!confirm('¿Deseas adjudicar esta cotización y generar la Orden de Compra oficial para este proveedor?')) {
    return;
  }

  try {
    const po = await apiClient.awardQuotation(quoteId, 'Adjudicada desde el comparador de cotizaciones');
    showToast(`✅ Orden de Compra generada: ${po.po_number}`, 'success');
    await loadComparisonMatrix();
    setTimeout(() => switchPurchaseTab('purchase-orders'), 1200);
  } catch (err) {
    showToast(`Error al adjudicar: ${err.message}`, 'error');
  }
}

async function openAddQuotationModal() {
  const reqId = document.getElementById('rfqSelectForComparison')?.value;
  if (!reqId) {
    showToast('Selecciona primero una Solicitud de Compra (RFQ)', 'error');
    return;
  }

  try {
    const rfq = await apiClient.getPurchaseRequisitionDetail(reqId);
    const supplierSel = document.getElementById('quoteSupplierSelect');
    if (supplierSel) {
      supplierSel.innerHTML = state.suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
    }

    const itemsTbody = document.getElementById('quoteItemsTableBody');
    if (itemsTbody && rfq.items) {
      itemsTbody.innerHTML = rfq.items.map(item => `
        <tr>
          <td><strong>${item.product_name}</strong></td>
          <td>${item.unit}</td>
          <td style="text-align:right; font-weight:700;">${item.requested_qty}</td>
          <td>
            <input type="number" class="form-input quote-unit-price" 
              data-product-id="${item.product_id}" 
              style="width:140px; text-align:right; font-weight:700;" 
              min="0" step="100" placeholder="0" required>
          </td>
        </tr>
      `).join('');
    }

    const form = document.getElementById('formAddQuotation');
    if (form) form.dataset.rfqId = reqId;

    openModal('modalAddQuotation');
  } catch (err) {
    showToast(`Error cargando detalles de la solicitud: ${err.message}`, 'error');
  }
}

async function handleAddQuotationSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const reqId = form.dataset.rfqId;
  if (!reqId) {
    showToast('No hay una solicitud de compra seleccionada', 'error');
    return;
  }

  const supplierSel = document.getElementById('quoteSupplierSelect');
  const deliveryDays = parseInt(document.getElementById('quoteDeliveryDays')?.value || '2', 10);
  const paymentTerms = document.getElementById('quotePaymentTerms')?.value || 'Crédito 15 días';
  const shippingCost = parseFloat(document.getElementById('quoteShippingCost')?.value || '0');
  const notes = document.getElementById('quoteNotes')?.value || '';

  const itemInputs = Array.from(document.querySelectorAll('.quote-unit-price'));
  const items = itemInputs.map(inp => ({
    product_id: inp.dataset.productId,
    unit_price: parseFloat(inp.value || '0')
  })).filter(i => i.unit_price > 0);

  if (items.length === 0) {
    showToast('Ingresa el precio unitario ofertado para al menos un producto', 'error');
    return;
  }

  try {
    await apiClient.addSupplierQuotation(reqId, {
      supplier_id: supplierSel.value,
      delivery_days: deliveryDays,
      payment_terms: paymentTerms,
      shipping_cost: shippingCost,
      notes: notes,
      items: items
    });

    showToast('✅ Cotización registrada exitosamente en el comparador', 'success');
    closeModal('modalAddQuotation');
    await loadComparisonMatrix();
  } catch (err) {
    showToast(`Error guardando cotización: ${err.message}`, 'error');
  }
}

// -----------------------------------------------------------------------------
// TAB 3: PURCHASE ORDERS (OC) & OFFICIAL DOCUMENT
// -----------------------------------------------------------------------------
async function loadPurchaseOrders() {
  const tbody = document.getElementById('purchaseOrdersTableBody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:28px; color:#64748b;">Cargando órdenes de compra...</td></tr>';

  try {
    const list = await apiClient.getPurchaseOrders('');
    purchaseState.purchaseOrders = list || [];
    renderPurchaseOrders();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#dc2626; padding:20px;">${err.message}</td></tr>`;
  }
}

function renderPurchaseOrders() {
  const tbody = document.getElementById('purchaseOrdersTableBody');
  if (!tbody) return;

  const list = purchaseState.purchaseOrders;
  if (!list || list.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center; padding:40px; color:#64748b;">
          <div style="font-size:32px; margin-bottom:8px;">📄</div>
          <p>No hay órdenes de compra emitidas aún.</p>
          <p style="font-size:12px; color:#94a3b8; margin-top:4px;">Usa el comparador de cotizaciones para adjudicar la primera orden.</p>
        </td>
      </tr>
    `;
    return;
  }

  const statusLabels = {
    DRAFT: 'Borrador',
    PENDING: 'Pendiente',
    SENT: 'Enviada',
    RECEIVED: 'Recibida',
    CANCELLED: 'Cancelada'
  };

  tbody.innerHTML = list.map(po => {
    const statusClass = po.status.toLowerCase();
    const label = statusLabels[po.status] || po.status;

    return `
      <tr>
        <td><strong>${po.po_number}</strong></td>
        <td>${po.supplier_name}</td>
        <td>${formatDate(po.issued_at)}</td>
        <td style="text-align:right; font-weight:700;">${formatCOP(po.total_amount)}</td>
        <td><span class="po-status-badge ${statusClass}">${label}</span></td>
        <td style="display:flex; gap:6px; justify-content:flex-end;">
          <button class="btn btn-secondary btn-sm" onclick="openPrintPO('${po.id}')">🖨️ Ver OC</button>
          ${(po.status === 'PENDING' || po.status === 'SENT') ? `
            <button class="btn btn-primary btn-sm" onclick="receivePO('${po.id}')">📥 Recibir en Bodega</button>
          ` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

async function receivePO(poId) {
  if (!confirm('¿Confirmar recepción física de esta Orden de Compra en bodega? Se crearán los lotes correspondientes y se actualizará el stock y costo promedio.')) {
    return;
  }

  try {
    const result = await apiClient.receivePurchaseOrder(poId, {});
    showToast(`✅ Recepción completada: ${result.lots_created || 0} lotes ingresados al inventario`, 'success');
    await loadPurchaseOrders();
  } catch (err) {
    showToast(`Error al recibir orden: ${err.message}`, 'error');
  }
}

async function openPrintPO(poId) {
  const sheet = document.getElementById('printPoSheet');
  if (!sheet) return;

  sheet.innerHTML = '<div style="text-align:center; padding:30px;">Cargando formato de orden de compra...</div>';
  openModal('modalPrintPO');

  try {
    const po = await apiClient.getPurchaseOrderDetail(poId);

    sheet.innerHTML = `
      <div class="po-header-section" style="display:flex; justify-content:space-between; border-bottom:2px solid #0f172a; padding-bottom:16px; margin-bottom:20px;">
        <div>
          <div style="font-size:20px; font-weight:900; color:#0f172a;">REFRIBREAK SAS</div>
          <div style="font-size:12px; color:#64748b;">NIT 901.458.789-2 · Régimen Común</div>
          <div style="font-size:12px; color:#64748b;">Calle 127 # 45-20, Bogotá D.C. · Tel: (+57) 310 555-0199</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:18px; font-weight:800; color:#0074e8;">ORDEN DE COMPRA</div>
          <div style="font-size:16px; font-weight:900; color:#0f172a;">${po.po_number}</div>
          <div style="font-size:12px; color:#64748b;">Fecha: <strong>${formatDate(po.issued_at)}</strong></div>
          <div style="font-size:12px; color:#64748b;">Estado: <strong>${po.status}</strong></div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px; background:#ffffff; padding:16px; border-radius:8px; border:1px solid #e2e8f0;">
        <div>
          <div style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase;">PROVEEDOR ADJUDICADO</div>
          <div style="font-size:15px; font-weight:700; color:#0f172a; margin-top:2px;">${po.supplier_name}</div>
          <div style="font-size:12px; color:#475569;">NIT: ${po.supplier_nit || 'No registrado'}</div>
          <div style="font-size:12px; color:#475569;">Contacto: ${po.supplier_contact || 'Área de Ventas'}</div>
          <div style="font-size:12px; color:#475569;">Tel / Correo: ${po.supplier_phone || ''} ${po.supplier_email || ''}</div>
        </div>
        <div>
          <div style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase;">DESTINO & ENTREGA</div>
          <div style="font-size:14px; font-weight:700; color:#0f172a; margin-top:2px;">Sede: ${po.warehouse_name}</div>
          <div style="font-size:12px; color:#475569;">Condición de Pago: <strong>${po.payment_terms || 'Crédito'}</strong></div>
          <div style="font-size:12px; color:#475569;">Tiempo de Entrega: <strong>${po.delivery_days || 2} días hábiles</strong></div>
        </div>
      </div>

      <table class="custom-table" style="font-size:12px; margin-bottom:20px;">
        <thead>
          <tr style="background:#f1f5f9;">
            <th>SKU</th>
            <th>Descripción del Producto</th>
            <th>Unidad</th>
            <th style="text-align:right;">Cantidad</th>
            <th style="text-align:right;">Precio Unitario</th>
            <th style="text-align:right;">Total Item</th>
          </tr>
        </thead>
        <tbody>
          ${(po.items || []).map(it => `
            <tr>
              <td><code>${it.sku}</code></td>
              <td><strong>${it.product_name}</strong></td>
              <td>${it.unit}</td>
              <td style="text-align:right; font-weight:700;">${it.quantity}</td>
              <td style="text-align:right;">${formatCOP(it.unit_cost)}</td>
              <td style="text-align:right; font-weight:700;">${formatCOP(it.total_cost)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>

      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:40px;">
        <div style="max-width:440px; font-size:12px; color:#475569; background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #e2e8f0;">
          <strong>Instrucciones y Requisitos de Recepción:</strong>
          <div>${po.notes || 'Recepción en bodega sujeta a verificación de temperatura, empaque íntegro, lote visible y fecha de vencimiento adecuada.'}</div>
          <div style="margin-top:6px; font-size:11px; color:#94a3b8;">Documento oficial emitido bajo política de trazabilidad FEFO y costo bancario promedio ponderado.</div>
        </div>

        <div style="min-width:260px; font-size:13px;">
          <div style="display:flex; justify-content:space-between; padding:4px 0;">
            <span>Subtotal Mercancía:</span>
            <strong>${formatCOP(po.subtotal)}</strong>
          </div>
          <div style="display:flex; justify-content:space-between; padding:4px 0;">
            <span>Flete / Transporte:</span>
            <strong>${formatCOP(po.shipping_cost)}</strong>
          </div>
          <div style="display:flex; justify-content:space-between; padding:8px 0; border-top:2px solid #0f172a; margin-top:4px; font-size:15px; font-weight:800; color:#0074e8;">
            <span>TOTAL ORDEN:</span>
            <span>${formatCOP(po.total_amount)}</span>
          </div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:60px; padding-top:20px;">
        <div style="border-top:1px solid #334155; text-align:center; font-size:12px; padding-top:8px;">
          <strong>Firma Autorizada / Compras</strong><br>
          Refribreak SAS
        </div>
        <div style="border-top:1px solid #334155; text-align:center; font-size:12px; padding-top:8px;">
          <strong>Aceptado / Proveedor</strong><br>
          ${po.supplier_name}
        </div>
      </div>
    `;
  } catch (err) {
    sheet.innerHTML = `<div style="color:#dc2626; padding:30px;">Error al cargar la orden de compra: ${err.message}</div>`;
  }
}
