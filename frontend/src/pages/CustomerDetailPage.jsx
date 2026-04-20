import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  User, 
  Phone, 
  Mail, 
  MapPin, 
  ShoppingBag,
  Loader2,
  ChevronLeft,
  ArrowRight
} from 'lucide-react';
import { customersApi } from '../api/api';
import { useToast } from '../context/ToastContext';
import StatusBadge from '../components/StatusBadge';

const CustomerDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  useEffect(() => {
    const fetchCustomer = async () => {
      try {
        const { data } = await customersApi.getCustomer(id);
        setData(data);
      } catch (err) {
        showToast('Failed to load customer details', 'error');
        navigate('/customers');
      } finally {
        setLoading(false);
      }
    };
    fetchCustomer();
  }, [id]);

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-primary-600" size={40} /></div>;

  const { customer, history } = data;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <button 
        onClick={() => navigate('/customers')}
        className="flex items-center gap-2 text-gray-500 hover:text-primary-600 transition-colors text-sm font-medium"
      >
        <ChevronLeft size={16} /> Back to Customers
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Customer Sidebar */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col items-center text-center">
            <div className="bg-primary-100 p-4 rounded-full text-primary-600 mb-4">
              <User size={48} />
            </div>
            <h1 className="text-xl font-bold text-gray-900">{customer.name}</h1>
            <p className="text-sm text-gray-500 italic mt-1">Customer since {new Date(customer.created_at).toLocaleDateString()}</p>
            
            <div className="w-full mt-6 space-y-4 border-t border-gray-50 pt-6 text-left">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-50 rounded-lg text-gray-400">
                  <Phone size={18} />
                </div>
                <div>
                  <p className="text-[10px] text-gray-400 uppercase font-bold">Phone</p>
                  <p className="text-sm font-medium text-gray-900">{customer.phone}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-50 rounded-lg text-gray-400">
                  <Mail size={18} />
                </div>
                <div>
                  <p className="text-[10px] text-gray-400 uppercase font-bold">Email</p>
                  <p className="text-sm font-medium text-gray-900">{customer.email || 'N/A'}</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="p-2 bg-gray-50 rounded-lg text-gray-400">
                  <MapPin size={18} />
                </div>
                <div>
                  <p className="text-[10px] text-gray-400 uppercase font-bold">Address</p>
                  <p className="text-sm font-medium text-gray-900 leading-relaxed">{customer.address}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-primary-600 p-6 rounded-xl shadow-lg text-white">
            <h3 className="text-sm font-bold uppercase tracking-wider opacity-80 mb-4">Order Statistics</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-primary-500 bg-opacity-30 p-3 rounded-lg">
                <p className="text-2xl font-bold">{history.length}</p>
                <p className="text-[10px] uppercase font-medium">Total Orders</p>
              </div>
              <div className="bg-primary-500 bg-opacity-30 p-3 rounded-lg">
                <p className="text-2xl font-bold">${history.reduce((sum, o) => sum + (parseFloat(o.total_price) || 0), 0).toFixed(0)}</p>
                <p className="text-[10px] uppercase font-medium">Total Spent</p>
              </div>
            </div>
          </div>
        </div>

        {/* Order History */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-6 border-b border-gray-100 flex justify-between items-center">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <ShoppingBag size={18} className="text-primary-600" />
                Order History
              </h3>
            </div>
            
            <div className="divide-y divide-gray-100">
              {history.length === 0 ? (
                <div className="p-12 text-center text-gray-400">No order history found for this customer.</div>
              ) : history.map((order) => (
                <div key={order.id} className="p-6 hover:bg-gray-50 transition-colors group">
                  <div className="flex flex-col sm:flex-row justify-between gap-4">
                    <div className="space-y-2">
                      <div className="flex items-center gap-3">
                        <span className="font-bold text-gray-900 text-lg">Order #{order.id}</span>
                        <StatusBadge status={order.status} />
                      </div>
                      <p className="text-sm text-gray-500 line-clamp-1">{order.items_summary}</p>
                      <p className="text-xs text-gray-400">Placed on {new Date(order.created_at).toLocaleDateString()}</p>
                    </div>
                    <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2">
                      <p className="text-lg font-bold text-primary-600">${parseFloat(order.total_price || 0).toFixed(2)}</p>
                      <Link 
                        to={`/orders/${order.id}`}
                        className="inline-flex items-center gap-1 text-sm font-medium text-gray-400 group-hover:text-primary-600 transition-colors"
                      >
                        View Details <ArrowRight size={14} />
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CustomerDetailPage;
