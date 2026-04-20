import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Plus, 
  Trash2, 
  ShoppingBag, 
  User, 
  Calendar, 
  FileText,
  Loader2,
  Search
} from 'lucide-react';
import { ordersApi, productsApi, customersApi } from '../api/api';
import { useToast } from '../context/ToastContext';

const NewOrderPage = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [customerSearch, setCustomerSearch] = useState('');
  
  const [formData, setFormData] = useState({
    customer_id: '',
    delivery_date: new Date().toISOString().split('T')[0],
    notes: '',
    items: [{ product_id: '', quantity: 1 }]
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [prodRes, custRes] = await Promise.all([
          productsApi.getProducts(),
          customersApi.getCustomers()
        ]);
        setProducts(prodRes.data.filter(p => p.is_active));
        setCustomers(custRes.data);
      } catch (err) {
        showToast('Failed to load initial data', 'error');
      }
    };
    fetchData();
  }, []);

  const filteredCustomers = useMemo(() => {
    if (!customerSearch) return [];
    return customers.filter(c => 
      c.name.toLowerCase().includes(customerSearch.toLowerCase()) ||
      c.phone.includes(customerSearch)
    ).slice(0, 5);
  }, [customers, customerSearch]);

  const handleAddItem = () => {
    setFormData({
      ...formData,
      items: [...formData.items, { product_id: '', quantity: 1 }]
    });
  };

  const handleRemoveItem = (index) => {
    const newItems = formData.items.filter((_, i) => i !== index);
    setFormData({ ...formData, items: newItems });
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...formData.items];
    newItems[index][field] = value;
    setFormData({ ...formData, items: newItems });
  };

  const calculateTotal = () => {
    return formData.items.reduce((sum, item) => {
      const product = products.find(p => p.id === parseInt(item.product_id));
      return sum + (product ? product.price_per_unit * item.quantity : 0);
    }, 0);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.customer_id) return showToast('Please select a customer', 'warning');
    if (formData.items.some(item => !item.product_id)) return showToast('Please select products for all items', 'warning');

    setLoading(true);
    try {
      await ordersApi.createOrder(formData);
      showToast('Order created successfully!', 'success');
      navigate('/orders');
    } catch (err) {
      showToast(err.response?.data?.message || 'Failed to create order', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20">
      <div className="flex items-center gap-2 text-gray-500 text-sm">
        <span className="hover:text-primary-600 cursor-pointer" onClick={() => navigate('/orders')}>Orders</span>
        <span>/</span>
        <span className="text-gray-900 font-medium">New Order</span>
      </div>

      <h1 className="text-2xl font-bold text-gray-900">Create New Order</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Customer Selection */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <User size={20} className="text-primary-600" />
            Customer Information
          </h3>
          <div className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">Search Customer</label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
              <input
                type="text"
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-md w-full focus:ring-primary-500 focus:border-primary-500"
                placeholder="Type name or phone..."
                value={customerSearch}
                onChange={(e) => setCustomerSearch(e.target.value)}
              />
            </div>
            
            {filteredCustomers.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg">
                {filteredCustomers.map(c => (
                  <button
                    key={c.id}
                    type="button"
                    className="w-full text-left px-4 py-2 hover:bg-primary-50 flex justify-between"
                    onClick={() => {
                      setFormData({ ...formData, customer_id: c.id });
                      setCustomerSearch(c.name);
                    }}
                  >
                    <span className="font-medium">{c.name}</span>
                    <span className="text-gray-500 text-sm">{c.phone}</span>
                  </button>
                ))}
              </div>
            )}
            
            {formData.customer_id && (
              <div className="mt-2 p-3 bg-primary-50 border border-primary-100 rounded-md flex items-center justify-between">
                <span className="text-sm text-primary-700">Selected: <strong>{customers.find(c => c.id === formData.customer_id)?.name}</strong></span>
                <button 
                  type="button" 
                  className="text-xs text-primary-600 hover:underline"
                  onClick={() => {
                    setFormData({ ...formData, customer_id: '' });
                    setCustomerSearch('');
                  }}
                >
                  Change
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Order Items */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <ShoppingBag size={20} className="text-primary-600" />
              Order Items
            </h3>
            <button
              type="button"
              onClick={handleAddItem}
              className="text-sm font-medium text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              <Plus size={16} /> Add Item
            </button>
          </div>

          <div className="space-y-3">
            {formData.items.map((item, index) => (
              <div key={index} className="flex gap-3 items-end">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-500 mb-1">Product</label>
                  <select
                    className="w-full p-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500 text-sm"
                    value={item.product_id}
                    onChange={(e) => handleItemChange(index, 'product_id', e.target.value)}
                    required
                  >
                    <option value="">Select a product</option>
                    {products.map(p => (
                      <option key={p.id} value={p.id}>{p.name} - ${p.price_per_unit}/{p.unit}</option>
                    ))}
                  </select>
                </div>
                <div className="w-24">
                  <label className="block text-xs font-medium text-gray-500 mb-1">Qty</label>
                  <input
                    type="number"
                    min="1"
                    step="0.1"
                    className="w-full p-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500 text-sm"
                    value={item.quantity}
                    onChange={(e) => handleItemChange(index, 'quantity', parseFloat(e.target.value))}
                    required
                  />
                </div>
                {formData.items.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveItem(index)}
                    className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                  >
                    <Trash2 size={20} />
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="pt-4 border-t flex justify-between items-center">
            <span className="text-gray-500 font-medium">Estimated Total:</span>
            <span className="text-xl font-bold text-gray-900">${calculateTotal().toFixed(2)}</span>
          </div>
        </div>

        {/* Delivery & Notes */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Calendar size={20} className="text-primary-600" />
              Delivery Date
            </h3>
            <input
              type="date"
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              value={formData.delivery_date}
              onChange={(e) => setFormData({ ...formData, delivery_date: e.target.value })}
              required
            />
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <FileText size={20} className="text-primary-600" />
              Special Notes
            </h3>
            <textarea
              rows="1"
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              placeholder="e.g. Extra spicy, No onions..."
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-4">
          <button
            type="button"
            onClick={() => navigate('/orders')}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-8 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 shadow-sm disabled:opacity-50 flex items-center gap-2 transition-colors font-medium"
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : 'Create Order'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default NewOrderPage;
