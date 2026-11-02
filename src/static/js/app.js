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

  // Forms
  document.getElementById('formPurchaseEntry')?.addEventListener('submit', submitPurchaseEntry);
  document.getElementById('formCreateOE')?.addEventListener('submit', submitCreateOrder);
  document.getElementById('btnRunAi')?.addEventListener('click', handleSimulateAiInvoice);

  // Initialize
  await loadInitialMetadata();
  switchView('dashboard');
});
