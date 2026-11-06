/**
 * API client for Refribreak Inventory Core (RIC).
 * Consumes the Python FastAPI backend via native JSON fetch.
 */
const API_BASE = '/api/v1';

const apiClient = {
  async get(endpoint, params = {}) {
    const url = new URL(window.location.origin + API_BASE + endpoint);
    Object.keys(params).forEach(k => {
      if (params[k] !== undefined && params[k] !== null && params[k] !== '') {
        url.searchParams.append(k, params[k]);
      }
    });

    const res = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Error en petición GET');
    }
    return res.json();
  },

  async post(endpoint, data = {}) {
    const res = await fetch(API_BASE + endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Error en petición POST');
    }
    return res.json();
  },

  // High-level API domain calls
  getDashboardSummary(warehouseId) {
    return this.get('/dashboard/summary', { warehouse_id: warehouseId });
  },

  getWarehouses() {
    return this.get('/warehouses');
  },

  getCategories() {
    return this.get('/categories');
  },

  getProducts(categoryId) {
    return this.get('/products', { category_id: categoryId });
  },

  getInventory(warehouseId, categoryId, query) {
    return this.get('/inventory', { warehouse_id: warehouseId, category_id: categoryId, query });
  },

  getLots(warehouseId) {
    return this.get('/lots', { warehouse_id: warehouseId, only_active: true });
  },

  getMovements(warehouseId) {
    return this.get('/movements', { warehouse_id: warehouseId, limit: 50 });
  },

  getOrders(statusFilter) {
    return this.get('/orders', { status_filter: statusFilter });
  },

  getOrderDetail(orderId) {
    return this.get(`/orders/${orderId}`);
  },

  createOrder(orderData) {
    return this.post('/orders', orderData);
  },

  dispatchOrder(orderId) {
    return this.post(`/orders/${orderId}/dispatch`);
  },

  registerPurchaseEntry(entryData) {
    return this.post('/movements/entry', entryData);
  },

  registerWaste(wasteData) {
    return this.post('/movements/waste', wasteData);
  },

  registerAdjustment(adjData) {
    return this.post('/movements/adjustment', adjData);
  },

  getCustomers() {
    return this.get('/customers');
  },

  getSuppliers() {
    return this.get('/suppliers');
  },

  getAuditLogs() {
    return this.get('/audit', { limit: 50 });
  },

  simulateAiExtraction(rawText, supplierHint) {
    return this.post('/ai/simulate-extract', { raw_text: rawText, supplier_hint: supplierHint });
  },

  // --- Procurement & Comparison API Methods ---
  getReplenishmentSuggestions(warehouseId) {
    return this.get('/purchases/replenishment-suggestions', { warehouse_id: warehouseId });
  },

  createPurchaseRequisition(data) {
    return this.post('/purchases/requisitions', data);
  },

  getPurchaseRequisitions(warehouseId, status) {
    return this.get('/purchases/requisitions', { warehouse_id: warehouseId, status: status });
  },

  getPurchaseRequisitionDetail(reqId) {
    return this.get(`/purchases/requisitions/${reqId}`);
  },

  addSupplierQuotation(reqId, data) {
    return this.post(`/purchases/requisitions/${reqId}/quotations`, data);
  },

  getQuotationComparison(reqId) {
    return this.get(`/purchases/requisitions/${reqId}/compare`);
  },

  awardQuotation(quoteId, notes) {
    const endpoint = notes ? `/purchases/quotations/${quoteId}/award?notes=${encodeURIComponent(notes)}` : `/purchases/quotations/${quoteId}/award`;
    return this.post(endpoint, {});
  },

  getPurchaseOrders(status) {
    return this.get('/purchases/orders', { status: status });
  },

  getPurchaseOrderDetail(poId) {
    return this.get(`/purchases/orders/${poId}`);
  },

  receivePurchaseOrder(poId, data = {}) {
    return this.post(`/purchases/orders/${poId}/receive`, data);
  }
};
