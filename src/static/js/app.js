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

    // Fill sheet fields
    document.getElementById('printOeConsecutive').textContent = order.consecutive_oe || 'OE 7217';
    document.getElementById('printOeDate').textContent = `${order.delivery_day_name || 'Viernes'} ${order.delivery_date || ''}`;
    document.getElementById('printOeCustomer').textContent = order.customer_name || 'Liid Comunicacion y Creatividad SAS';
    document.getElementById('printOeAddress').textContent = order.delivery_address || 'Trv 23 97 -73 Ofc 212 Bogota';
    document.getElementById('printOeArrivalTime').textContent = order.arrival_time || '7:30 AM';
    document.getElementById('printOeStartTime').textContent = order.start_time || '8:30 AM';
    document.getElementById('printOeEndTime').textContent = order.end_time || '11:30 AM';
    document.getElementById('printOeDepartureTime').textContent = order.departure_time || '6:40 AM';
    document.getElementById('printOeTransporter').textContent = order.transporter_name || 'Carlos Rodríguez';
    document.getElementById('printOeTransportMode').textContent = order.transport_mode || 'Carro';
    document.getElementById('printOePlate').textContent = order.vehicle_plate || 'WMA-452';
    document.getElementById('printOeAdvisor').textContent = order.advisor_name || 'Nays Navarro';
    document.getElementById('printOeRequestedBy').textContent = order.requested_by || 'Leonardo Ramírez';
    document.getElementById('printOeReceivedBy').textContent = order.received_by || 'Leonardo Ramírez';
    document.getElementById('printOePhone').textContent = order.receiver_phone || '3504163975';

    // Products table
    document.getElementById('printOeQty').textContent = order.quantity;
    document.getElementById('printOeType').textContent = order.service_type || 'Desayuno';
    document.getElementById('printOeDesc').textContent = order.service_description || 'Servido';
    document.getElementById('printOeProductDetail').textContent = order.product_detail;

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
  document.getElementById('formAddQuotation')?.addEventListener('submit', handleSaveQuotation);

  // Initialize
  await loadInitialMetadata();
  switchView('dashboard');
});

function closeCreateMenu() {
  document.getElementById('createMenuDropdown')?.classList.remove('active');
}

/* =========================================================================
   PROCUREMENT, COMPARISON & SMART REPLENISHMENT MODULE
   ========================================================================= */

let activePurchaseTab = 'suggestions';
let currentReplenishmentData = [];
let currentComparisonData = null;

function loadPurchasesView() {
  switchPurchaseTab(activePurchaseTab);
}

function switchPurchaseTab(tabName) {
  activePurchaseTab = tabName;

  // Toggle tab buttons
  document.getElementById('btnTabSuggestions')?.classList.toggle('active', tabName === 'suggestions');
  document.getElementById('btnTabComparator')?.classList.toggle('active', tabName === 'comparator');
  document.getElementById('btnTabOrders')?.classList.toggle('active', tabName === 'orders');

  // Toggle tab contents
  document.getElementById('subtabSuggestions')?.classList.toggle('active', tabName === 'suggestions');
  document.getElementById('subtabComparator')?.classList.toggle('active', tabName === 'comparator');
  document.getElementById('subtabOrders')?.classList.toggle('active', tabName === 'orders');

  if (tabName === 'suggestions') {
    loadReplenishmentSuggestions();
  } else if (tabName === 'comparator') {
    loadRequisitionsForDropdown();
  } else if (tabName === 'orders') {
    loadPurchaseOrders();
  }
}

// 1. REPLENISHMENT SUGGESTIONS BASED ON INVENTORY
async function loadReplenishmentSuggestions() {
  const tbody = document.getElementById('suggestionsTableBody');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="12" style="text-align:center; padding:28px;">Analizando niveles de stock y reservas en bodega...</td></tr>`;

  try {
    const data = await apiClient.getReplenishmentSuggestions(state.activeWarehouseId);
    currentReplenishmentData = data;

    // Update summary metrics
    const critCount = data.filter(i => i.urgency === 'CRITICAL').length;
    const lowCount = data.filter(i => i.urgency === 'LOW_STOCK').length;
    const totalEstCost = data.reduce((acc, curr) => acc + (curr.estimated_total_cost || 0), 0);

    const elCrit = document.getElementById('suggCritCount');
    const elLow = document.getElementById('suggLowCount');
    const elCost = document.getElementById('suggTotalCost');
    const badgeCount = document.getElementById('badgeSuggestionsCount');

    if (elCrit) elCrit.textContent = critCount;
    if (elLow) elLow.textContent = lowCount;
    if (elCost) elCost.textContent = formatCOP(totalEstCost);

    if (badgeCount) {
      const totalAlerts = critCount + lowCount;
      if (totalAlerts > 0) {
        badgeCount.style.display = 'inline-block';
        badgeCount.textContent = totalAlerts;
      } else {
        badgeCount.style.display = 'none';
      }
    }

    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="12" style="text-align:center; padding:28px; color:#16a34a; font-weight:600;">
        ✓ Todos los productos cumplen el nivel de stock mínimo en esta sede. No se requieren compras urgentes.
      </td></tr>`;
      return;
    }

    tbody.innerHTML = data.map((item, idx) => {
      const urgencyClass = item.urgency.toLowerCase();
      const urgencyLabel = item.urgency === 'CRITICAL' ? 'Crítico (Agotado)' : item.urgency === 'LOW_STOCK' ? 'Bajo Stock Mín.' : 'Normal';

      return `
        <tr>
          <td><input type="checkbox" class="sugg-check" data-index="${idx}" checked></td>
          <td><strong>${item.product_name}</strong></td>
          <td><code>${item.sku}</code></td>
          <td><span class="badge-pill badge-gray">${item.category_name}</span></td>
          <td>${item.warehouse_name}</td>
          <td style="font-weight:700; color:${item.available_qty <= 0 ? '#dc2626' : '#0f172a'};">
            ${item.available_qty} ${item.unit}
          </td>
          <td>${item.min_stock} ${item.unit}</td>
          <td style="color:#dc2626; font-weight:700;">-${item.deficit_qty}</td>
          <td>
            <input type="number" id="suggQtyInput_${idx}" class="form-input" style="width:80px; padding:4px 8px; font-weight:700;" value="${item.suggested_qty}" min="1" step="1">
          </td>
          <td>${formatCOP(item.last_unit_cost)}</td>
          <td style="font-weight:700; color:var(--siigo-navy);">${formatCOP(item.estimated_total_cost)}</td>
          <td>
            <span class="pill-urgency ${urgencyClass}">${urgencyLabel}</span>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="12" style="text-align:center; color:#dc2626; padding:20px;">Error al cargar sugerencias: ${err.message}</td></tr>`;
  }
}

function toggleSelectAllSuggestions(checked) {
  document.querySelectorAll('.sugg-check').forEach(chk => { chk.checked = checked; });
}

async function createRequisitionFromSelectedSuggestions() {
  const checkboxes = document.querySelectorAll('.sugg-check:checked');
  if (!checkboxes.length) {
    showToast('Selecciona al menos un producto de la lista para cotizar', 'error');
    return;
  }

  const items = [];
  checkboxes.forEach(chk => {
    const idx = parseInt(chk.dataset.index, 10);
    const item = currentReplenishmentData[idx];
    const qtyInput = document.getElementById(`suggQtyInput_${idx}`);
    const qty = qtyInput ? parseFloat(qtyInput.value) : item.suggested_qty;

    if (item && qty > 0) {
      items.push({
        product_id: item.product_id,
        requested_qty: qty,
        estimated_unit_cost: item.last_unit_cost || 0.0
      });
    }
  });

  const warehouseId = state.activeWarehouseId || state.warehouses[0]?.id || 'wh-bog-central';

  try {
    const res = await apiClient.createPurchaseRequisition({
      warehouse_id: warehouseId,
      origin: 'INVENTORY_SUGGESTION',
      notes: `Solicitud de reabastecimiento automático para ${items.length} productos bajo stock mínimo.`,
      items: items
    });

    showToast(`Solicitud ${res.consecutive} creada exitosamente con ${items.length} productos`, 'success');
    
    // Switch to comparator tab and select this requisition
    switchPurchaseTab('comparator');
    await loadRequisitionsForDropdown(res.id);

  } catch (err) {
    showToast(`Error al crear solicitud: ${err.message}`, 'error');
  }
}

// 2. COMPARISON MATRIX & RFQ SELECTION
async function loadRequisitionsForDropdown(selectedId = null) {
  const select = document.getElementById('selectRequisitionForCompare');
  if (!select) return;

  select.innerHTML = `<option value="">Cargando solicitudes...</option>`;

  try {
    const reqs = await apiClient.getPurchaseRequisitions(state.activeWarehouseId);
    if (!reqs.length) {
      select.innerHTML = `<option value="">No hay solicitudes de cotización activas</option>`;
      document.getElementById('comparisonSupplierCards').innerHTML = '';
      document.getElementById('comparisonMatrixBody').innerHTML = `<tr><td colspan="4" style="text-align:center; padding:28px;">No hay solicitudes registradas. Crea una desde la pestaña de sugerencias.</td></tr>`;
      return;
    }

    select.innerHTML = reqs.map(r => `
      <option value="${r.id}" ${selectedId === r.id ? 'selected' : ''}>
        ${r.consecutive} (${r.warehouse_name} — ${r.items.length} productos | ${r.quotations_count} cotizaciones) [${r.status}]
      </option>
    `).join('');

    loadComparisonForSelectedRequisition();

  } catch (err) {
    select.innerHTML = `<option value="">Error cargando solicitudes: ${err.message}</option>`;
  }
}

async function loadComparisonForSelectedRequisition() {
  const select = document.getElementById('selectRequisitionForCompare');
  const reqId = select?.value;
  if (!reqId) return;

  const cardsContainer = document.getElementById('comparisonSupplierCards');
  const matrixHeader = document.getElementById('comparisonMatrixHeader');
  const matrixBody = document.getElementById('comparisonMatrixBody');
  const itemsCountBadge = document.getElementById('comparisonItemsCountBadge');
  const detailHeader = document.getElementById('comparisonDetailHeader');

  cardsContainer.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:20px;">Cargando matriz comparativa...</div>`;

  try {
    const comp = await apiClient.getQuotationComparison(reqId);
    currentComparisonData = comp;

    if (detailHeader) {
      detailHeader.innerHTML = `
        <div style="font-size:14px; color:#475569;">
          <strong>Solicitud:</strong> <span style="color:#0f172a; font-weight:700;">${comp.requisition_consecutive}</span> | 
          <strong>Sede:</strong> ${comp.warehouse_name} | 
          <strong>Observaciones:</strong> <em>${comp.notes || 'Reabastecimiento regular'}</em>
        </div>
      `;
    }

    if (itemsCountBadge) itemsCountBadge.textContent = `${comp.items.length} productos`;

    if (!comp.suppliers.length) {
      cardsContainer.innerHTML = `
        <div style="grid-column:1/-1; background:#fff; padding:30px; border-radius:8px; border:2px dashed #cbd5e1; text-align:center;">
          <h4 style="font-size:16px; font-weight:700; color:#334155; margin-bottom:8px;">Aún no hay cotizaciones registradas para esta solicitud</h4>
          <p style="font-size:13px; color:#64748b; margin-bottom:16px;">Haz clic en el botón "+ Ingresar Oferta de Proveedor" para cargar propuestas y activar la matriz comparativa.</p>
          <button class="btn btn-primary" onclick="openAddQuotationModal()">+ Ingresar Oferta de Proveedor</button>
        </div>
      `;
      matrixBody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:20px;">Sin ofertas recibidas.</td></tr>`;
      return;
    }

    // Render Supplier Cards
    cardsContainer.innerHTML = comp.suppliers.map(card => {
      let cardClass = 'quote-card';
      let badgeHtml = '';

      if (card.is_awarded) {
        cardClass += ' awarded';
        badgeHtml = `<span class="badge-decision recommended">✓ ADJUDICADA</span>`;
      } else if (card.is_cheapest && card.is_fastest) {
        cardClass += ' cheapest';
        badgeHtml = `<span class="badge-decision best-price">🟢 MEJOR PRECIO & MÁS RÁPIDO</span>`;
      } else if (card.is_cheapest) {
        cardClass += ' cheapest';
        badgeHtml = `<span class="badge-decision best-price">🟢 MEJOR PRECIO</span>`;
      } else if (card.is_fastest) {
        cardClass += ' fastest';
        badgeHtml = `<span class="badge-decision fastest">🟡 ENTREGA MÁS RÁPIDA</span>`;
      } else if (card.recommendation_badge === 'RECOMENDADO') {
        badgeHtml = `<span class="badge-decision recommended">🔵 RECOMENDADO</span>`;
      }

      const savingsHtml = card.savings_cop > 0 
        ? `<div class="quote-savings-chip">💰 Ahorro de ${formatCOP(card.savings_cop)} (${card.savings_pct}%)</div>`
        : `<div style="font-size:11px; color:#94a3b8; margin-top:6px;">Opción de mayor valor base</div>`;

      const awardBtnHtml = card.is_awarded
        ? `<button class="btn-award-quote" disabled>✓ Orden de Compra Emitida</button>`
        : `<button class="btn-award-quote" onclick="handleAwardQuotation('${card.quotation_id}', '${card.supplier_name}')">
            📋 Adjudicar y Generar OC Oficial
          </button>`;

      return `
        <div class="${cardClass}">
          <div class="quote-card-header">
            <div>
              <div class="quote-supplier-title">${card.supplier_name}</div>
              <div class="quote-supplier-nit">NIT: ${card.supplier_nit}</div>
            </div>
            <div>${badgeHtml}</div>
          </div>

          <div class="quote-meta-row">
            <span>Tiempo de Entrega:</span>
            <strong>⏱️ ${card.delivery_days} ${card.delivery_days === 1 ? 'día hábil' : 'días hábiles'}</strong>
          </div>

          <div class="quote-meta-row">
            <span>Condición de Pago:</span>
            <strong>${card.payment_terms}</strong>
          </div>

          <div class="quote-meta-row">
            <span>Flete / Transporte:</span>
            <strong>${card.shipping_cost > 0 ? formatCOP(card.shipping_cost) : 'Gratis en sede'}</strong>
          </div>

          <div class="quote-total-box">
            <div class="quote-total-label">Total Cotizado Ofertado</div>
            <div class="quote-total-amount">${formatCOP(card.total_amount)}</div>
            ${savingsHtml}
          </div>

          ${awardBtnHtml}
        </div>
      `;
    }).join('');

    // Render Matrix Table Columns
    let headerHtml = `
      <th>Producto</th>
      <th>SKU</th>
      <th>Cant. Requerida</th>
    `;
    comp.suppliers.forEach(s => {
      headerHtml += `<th style="text-align:right;">${s.supplier_name}</th>`;
    });
    matrixHeader.innerHTML = headerHtml;

    // Render Matrix Table Rows
    matrixBody.innerHTML = comp.items.map(row => {
      let rowHtml = `
        <td><strong>${row.product_name}</strong></td>
        <td><code>${row.sku}</code></td>
        <td>${row.requested_qty} ${row.unit}</td>
      `;

      comp.suppliers.forEach(s => {
        const price = row.prices_by_supplier[s.supplier_id] || 0.0;
        const isBestPrice = (price > 0 && price === row.lowest_unit_price);
        const cellClass = isBestPrice ? 'cell-best-price' : '';
        const bestBadge = isBestPrice ? `<span class="badge-lowest-pill">Mejor</span>` : '';

        rowHtml += `
          <td class="${cellClass}" style="text-align:right;">
            ${formatCOP(price)} ${bestBadge}
          </td>
        `;
      });

      return `<tr>${rowHtml}</tr>`;
    }).join('');

  } catch (err) {
    cardsContainer.innerHTML = `<div style="grid-column:1/-1; color:#dc2626; padding:20px;">Error al generar matriz comparativa: ${err.message}</div>`;
  }
}

// 3. ADD SUPPLIER QUOTATION MODAL
function openAddQuotationModal() {
  const select = document.getElementById('selectRequisitionForCompare');
  const reqId = select?.value;
  if (!reqId || !currentComparisonData) {
    showToast('Selecciona primero una solicitud de compra válida', 'error');
    return;
  }

  // Populate supplier select
  const supSelect = document.getElementById('quoteSupplierSelect');
  if (supSelect) {
    supSelect.innerHTML = state.suppliers.map(s => `
      <option value="${s.id}">${s.name} (${s.nit})</option>
    `).join('');
  }

  // Populate line items
  const itemsTbody = document.getElementById('quoteItemsTableBody');
  if (itemsTbody) {
    itemsTbody.innerHTML = currentComparisonData.items.map(item => `
      <tr>
        <td><strong>${item.product_name}</strong></td>
        <td>${item.unit}</td>
        <td>${item.requested_qty}</td>
        <td>
          <input type="number" class="form-input quote-unit-cost" data-product-id="${item.product_id}" data-qty="${item.requested_qty}" 
            placeholder="Ej: 8500" min="0" step="100" style="width:160px;" required>
        </td>
      </tr>
    `).join('');
  }

  openModal('modalAddQuotation');
}

async function handleSaveQuotation(e) {
  e.preventDefault();
  const select = document.getElementById('selectRequisitionForCompare');
  const reqId = select?.value;
  if (!reqId) return;

  const supplierId = document.getElementById('quoteSupplierSelect')?.value;
  const docNumber = document.getElementById('quoteDocNumber')?.value;
  const deliveryDays = parseInt(document.getElementById('quoteDeliveryDays')?.value || '1', 10);
  const paymentTerms = document.getElementById('quotePaymentTerms')?.value;
  const shippingCost = parseFloat(document.getElementById('quoteShippingCost')?.value || '0');
  const notes = document.getElementById('quoteNotes')?.value;

  const items = [];
  document.querySelectorAll('.quote-unit-cost').forEach(input => {
    const pId = input.dataset.productId;
    const qty = parseFloat(input.dataset.qty);
    const unitCost = parseFloat(input.value || '0');
    if (pId && unitCost >= 0) {
      items.push({
        product_id: pId,
        quantity: qty,
        unit_cost: unitCost
      });
    }
  });

  try {
    await apiClient.addSupplierQuotation(reqId, {
      supplier_id: supplierId,
      quotation_number: docNumber,
      delivery_days: deliveryDays,
      payment_terms: paymentTerms,
      shipping_cost: shippingCost,
      notes: notes,
      items: items
    });

    closeModal('modalAddQuotation');
    showToast('Cotización registrada en la matriz comparativa exitosamente', 'success');
    loadComparisonForSelectedRequisition();

  } catch (err) {
    showToast(`Error al guardar cotización: ${err.message}`, 'error');
  }
}

// 4. AWARD QUOTATION AND GENERATE OFFICIAL PURCHASE ORDER
async function handleAwardQuotation(quoteId, supplierName) {
  if (!confirm(`¿Confirmas adjudicar esta compra a ${supplierName} y generar automáticamente la Orden de Compra Oficial (OC)?`)) {
    return;
  }

  try {
    const po = await apiClient.awardQuotation(quoteId);
    showToast(`¡Orden de Compra ${po.consecutive_oc} generada exitosamente a nombre de ${po.supplier_name}!`, 'success');

    // Switch to orders tab and open printable format
    switchPurchaseTab('orders');
    openPrintPOModal(po.id);

  } catch (err) {
    showToast(`Error al adjudicar orden de compra: ${err.message}`, 'error');
  }
}

// 5. LIST AND RECEIVE PURCHASE ORDERS
async function loadPurchaseOrders() {
  const tbody = document.getElementById('purchaseOrdersTableBody');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:28px;">Cargando órdenes de compra...</td></tr>`;

  try {
    const orders = await apiClient.getPurchaseOrders();
    if (!orders.length) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:28px; color:#64748b;">No hay órdenes de compra emitidas todavía.</td></tr>`;
      return;
    }

    tbody.innerHTML = orders.map(po => {
      const isReceived = po.status === 'RECEIVED';
      const statusPill = isReceived 
        ? `<span class="badge-pill badge-green">✓ RECIBIDA EN BODEGA</span>`
        : `<span class="badge-pill badge-blue">⏳ EMITIDA / EN TRÁNSITO</span>`;

      const receiveBtn = isReceived
        ? `<button class="btn btn-secondary btn-sm" disabled title="Ya fue ingresada al stock">Ingresada</button>`
        : `<button class="btn btn-primary btn-sm" onclick="handleReceivePO('${po.id}', '${po.consecutive_oc}')">📥 Recibir en Bodega</button>`;

      return `
        <tr>
          <td><strong style="color:var(--siigo-navy);">${po.consecutive_oc}</strong></td>
          <td>
            <strong>${po.supplier_name}</strong>
            <div style="font-size:11px; color:#64748b;">NIT: ${po.supplier_nit}</div>
          </td>
          <td>${po.warehouse_name}</td>
          <td>${formatDate(po.order_date)}</td>
          <td><strong>${formatDate(po.expected_delivery_date)}</strong></td>
          <td>${po.payment_terms}</td>
          <td style="font-weight:800; color:var(--siigo-navy);">${formatCOP(po.total_amount)}</td>
          <td>${statusPill}</td>
          <td>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-secondary btn-sm" onclick="openPrintPOModal('${po.id}')" title="Ver formato imprimible">👁️ Ver OC</button>
              ${receiveBtn}
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#dc2626; padding:20px;">Error al cargar órdenes de compra: ${err.message}</td></tr>`;
  }
}

async function handleReceivePO(poId, consecutive) {
  if (!confirm(`¿Confirmas la recepción física de la mercancía de la Orden de Compra ${consecutive}?\nSe crearán los lotes trazables por política FEFO y se actualizará el costo promedio ponderado.`)) {
    return;
  }

  try {
    const res = await apiClient.receivePurchaseOrder(poId, {});
    showToast(`✓ Mercancía de ${consecutive} recepcionada con éxito. Movimiento ${res.movement_consecutive} registrado.`, 'success');
    loadPurchaseOrders();
    // Refresh inventory and lot counts
    loadInventory();
  } catch (err) {
    showToast(`Error al recepcionar orden de compra: ${err.message}`, 'error');
  }
}

async function openPrintPOModal(poId) {
  const sheet = document.getElementById('printPoSheet');
  if (!sheet) return;

  sheet.innerHTML = `<div style="text-align:center; padding:30px;">Cargando documento oficial de Orden de Compra...</div>`;
  openModal('modalPrintPO');

  try {
    const po = await apiClient.getPurchaseOrderDetail(poId);

    sheet.innerHTML = `
      <div class="po-header">
        <div>
          <div style="font-size:20px; font-weight:900; color:var(--siigo-navy);">REFRIBREAK SAS</div>
          <div style="font-size:12px; color:#475569;">NIT: 901.123.456-7 — Régimen Común</div>
          <div style="font-size:12px; color:#475569;">Soluciones Empresariales de Refrigerios & Catering Corporativo</div>
          <div style="font-size:12px; color:#475569;">Bogotá D.C., Colombia — PBX: (601) 744-1234</div>
        </div>
        <div class="po-title-box" style="text-align:right;">
          <h2>ORDEN DE COMPRA</h2>
          <span>${po.consecutive_oc}</span>
          <div style="font-size:12px; color:#64748b; margin-top:4px;">Fecha: ${formatDate(po.order_date)}</div>
          <div style="font-size:12px; font-weight:700; color:#15803d;">Estado: ${po.status}</div>
        </div>
      </div>

      <div class="po-info-grid">
        <div>
          <strong style="color:var(--siigo-navy);">DATOS DEL PROVEEDOR</strong>
          <div><strong>Razón Social:</strong> ${po.supplier_name}</div>
          <div><strong>NIT:</strong> ${po.supplier_nit}</div>
          <div><strong>Condición de Pago:</strong> ${po.payment_terms}</div>
        </div>
        <div>
          <strong style="color:var(--siigo-navy);">DATOS DE ENTREGA & RECEPCIÓN</strong>
          <div><strong>Sede / Bodega Destino:</strong> ${po.warehouse_name}</div>
          <div><strong>Fecha Promesa Entrega:</strong> ${formatDate(po.expected_delivery_date)}</div>
          <div><strong>Elaborada por:</strong> ${po.created_by.toUpperCase()} (Lead Engineer)</div>
        </div>
      </div>

      <table class="po-table">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Descripción del Producto</th>
            <th>Unidad</th>
            <th style="text-align:right;">Cantidad</th>
            <th style="text-align:right;">Valor Unitario</th>
            <th style="text-align:right;">Total Item</th>
          </tr>
        </thead>
        <tbody>
          ${po.items.map(it => `
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

      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div style="max-width:440px; font-size:12px; color:#475569; background:#f8fafc; padding:12px; border-radius:6px; border:1px solid #e2e8f0;">
          <strong>Notas y Requisitos de Recepción:</strong>
          <div>${po.notes || 'Recepción sujeta a verificación de temperatura, lote visible y fecha de vencimiento.'}</div>
          <div style="margin-top:6px; font-size:11px; color:#94a3b8;">Documento oficial generado con política de trazabilidad FEFO y costo promedio ponderado.</div>
        </div>

        <div class="po-totals-box">
          <div class="po-total-row">
            <span>Subtotal Mercancía:</span>
            <strong>${formatCOP(po.subtotal)}</strong>
          </div>
          <div class="po-total-row">
            <span>Flete / Transporte:</span>
            <strong>${formatCOP(po.shipping_cost)}</strong>
          </div>
          <div class="po-total-row grand">
            <span>TOTAL ORDEN (COP):</span>
            <span style="color:var(--siigo-navy);">${formatCOP(po.total_amount)}</span>
          </div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:40px; margin-top:50px; padding-top:10px;">
        <div style="border-top:1px solid #334155; text-align:center; font-size:12px; padding-top:6px;">
          <strong>Firma Autorizada / Compras</strong><br>
          Refribreak SAS
        </div>
        <div style="border-top:1px solid #334155; text-align:center; font-size:12px; padding-top:6px;">
          <strong>Aceptado / Proveedor</strong><br>
          ${po.supplier_name}
        </div>
      </div>
    `;

  } catch (err) {
    sheet.innerHTML = `<div style="color:#dc2626; padding:30px;">Error al cargar la orden de compra: ${err.message}</div>`;
  }
}

