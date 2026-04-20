import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Search, 
  Plus, 
  ExternalLink,
  Loader2,
  Phone,
  Mail,
  ShoppingBag
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { customersApi } from '../api/api';
import { useToast } from '../context/ToastContext';
import Modal from '../components/Modal';

const CustomersPage = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    address: ''
  });

  const fetchCustomers = async () => {
    try {
      const { data } = await customersApi.getCustomers();
      setCustomers(data);
    } catch (err) {
      showToast('Failed to load customers', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await customersApi.createCustomer(formData);
      showToast('Customer added successfully', 'success');
      fetchCustomers();
      setIsModalOpen(false);
      setFormData({ name: '', phone: '', email: '', address: '' });
    } catch (err) {
      showToast('Failed to add customer', 'error');
    }
  };

  const filteredCustomers = customers.filter(c => 
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.phone.includes(search) ||
    c.email?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Users className="text-primary-600" />
          Customers
        </h1>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 shadow-sm transition-colors text-sm font-medium"
        >
          <Plus size={18} className="mr-2" />
          New Customer
        </button>
      </div>

      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Search by name, phone or email..."
            className="pl-10 pr-4 py-2 border border-gray-300 rounded-md w-full focus:ring-primary-500 focus:border-primary-500"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          <div className="col-span-full py-10 flex justify-center">
            <Loader2 className="animate-spin text-primary-600" size={32} />
          </div>
        ) : filteredCustomers.map((customer) => (
          <div 
            key={customer.id} 
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover:border-primary-300 transition-all cursor-pointer group"
            onClick={() => navigate(`/customers/${customer.id}`)}
          >
            <div className="flex justify-between items-start mb-4">
              <div className="bg-primary-50 p-3 rounded-full text-primary-600 group-hover:bg-primary-600 group-hover:text-white transition-colors">
                <Users size={24} />
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-400 uppercase font-bold">Total Orders</p>
                <p className="text-lg font-bold text-gray-900">{customer.total_orders}</p>
              </div>
            </div>
            
            <h3 className="text-lg font-bold text-gray-900 mb-4">{customer.name}</h3>
            
            <div className="space-y-2 mb-6">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Phone size={14} className="text-gray-400" />
                {customer.phone}
              </div>
              {customer.email && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Mail size={14} className="text-gray-400" />
                  {customer.email}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-50">
              <span className="text-xs text-gray-400 italic">
                {customer.last_order_date ? `Last order: ${new Date(customer.last_order_date).toLocaleDateString()}` : 'No orders yet'}
              </span>
              <span className="text-primary-600 font-medium text-sm flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                Profile <ExternalLink size={14} />
              </span>
            </div>
          </div>
        ))}
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add New Customer"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Full Name</label>
            <input
              type="text"
              required
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-primary-500 focus:border-primary-500"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Phone Number</label>
            <input
              type="tel"
              required
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-primary-500 focus:border-primary-500"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Email Address (Optional)</label>
            <input
              type="email"
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-primary-500 focus:border-primary-500"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Delivery Address</label>
            <textarea
              required
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-primary-500 focus:border-primary-500"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors font-medium shadow-sm"
            >
              Create Customer
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default CustomersPage;
