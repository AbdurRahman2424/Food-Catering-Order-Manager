import api from './index';

export const authApi = {
  login: (credentials) => api.post('/login', credentials),
  logout: () => api.post('/logout'),
};

export const dashboardApi = {
  getStats: () => api.get('/api/dashboard'),
  getNavCounts: () => api.get('/api/nav-counts'),
};

export const ordersApi = {
  getOrders: (params) => api.get('/api/orders', { params }),
  getOrder: (id) => api.get(`/api/orders/${id}`),
  createOrder: (data) => api.post('/api/orders', data),
  updateStatus: (id, status) => api.post(`/api/orders/${id}/status`, { status }),
  addComment: (id, comment) => api.post(`/api/orders/${id}/comments`, { comment }),
  getInvoice: (id) => api.get(`/api/orders/${id}/invoice`),
  reorder: (id) => api.post(`/api/reorder/${id}`),
  getInvoicePdfUrl: (id) => `${import.meta.env.VITE_API_URL}/api/orders/${id}/invoice/pdf`,
};

export const productsApi = {
  getProducts: () => api.get('/api/products'),
  createProduct: (data) => api.post('/api/products', data),
  updateProduct: (id, data) => api.put(`/api/products/${id}`, data),
};

export const customersApi = {
  getCustomers: () => api.get('/api/customers'),
  getCustomer: (id) => api.get(`/api/customers/${id}`),
  createCustomer: (data) => api.post('/api/customers', data),
};

export const kitchenApi = {
  getOrders: () => api.get('/api/kitchen'),
};

export const deliveryApi = {
  getOrders: () => api.get('/api/delivery'),
};
