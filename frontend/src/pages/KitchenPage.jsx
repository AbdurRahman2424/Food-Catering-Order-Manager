import React, { useState, useEffect } from 'react';
import { 
  ChefHat, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  Loader2,
  ExternalLink
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { kitchenApi, ordersApi } from '../api/api';
import { useToast } from '../context/ToastContext';
import StatusBadge from '../components/StatusBadge';

const KitchenPage = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const fetchKitchenOrders = async () => {
    try {
      const { data } = await kitchenApi.getOrders();
      setOrders(data);
    } catch (err) {
      showToast('Failed to load kitchen orders', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKitchenOrders();
    const interval = setInterval(fetchKitchenOrders, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleUpdateStatus = async (id, status) => {
    try {
      await ordersApi.updateStatus(id, status);
      showToast(`Order #${id} marked as ${status.replace('_', ' ')}`, 'success');
      fetchKitchenOrders();
    } catch (err) {
      showToast('Failed to update status', 'error');
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-primary-600" size={40} /></div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <ChefHat className="text-primary-600" />
          Kitchen Display
        </h1>
        <div className="text-sm text-gray-500 bg-white px-3 py-1 rounded-full border flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          Auto-refreshing (60s)
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="bg-white p-12 rounded-xl border border-dashed border-gray-300 text-center">
          <ChefHat size={48} className="mx-auto text-gray-300 mb-4" />
          <h2 className="text-xl font-medium text-gray-900">All caught up!</h2>
          <p className="text-gray-500">There are no orders currently in preparation.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {orders.map((order) => {
            const isOverdue = new Date(order.delivery_date) < new Date().setHours(0,0,0,0);
            return (
              <div 
                key={order.id} 
                className={`bg-white rounded-xl shadow-sm border-2 overflow-hidden flex flex-col ${
                  isOverdue ? 'border-red-200' : 'border-gray-100'
                }`}
              >
                <div className={`p-4 flex justify-between items-start ${isOverdue ? 'bg-red-50' : 'bg-gray-50'}`}>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg font-bold text-gray-900">#{order.id}</span>
                      <StatusBadge status={order.status} />
                    </div>
                    <p className="text-sm font-medium text-gray-600">{order.customer_name}</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-xs font-bold uppercase ${isOverdue ? 'text-red-600' : 'text-gray-400'}`}>
                      {isOverdue && 'OVERDUE'}
                    </p>
                    <p className="text-sm font-medium text-gray-900">{new Date(order.delivery_date).toLocaleDateString()}</p>
                  </div>
                </div>

                <div className="p-4 flex-1 space-y-3">
                  <div className="space-y-2">
                    {order.order_items.map((item, idx) => (
                      <div key={idx} className="flex justify-between items-center text-sm">
                        <span className="font-medium text-gray-800">{item.product_name}</span>
                        <span className="bg-gray-100 px-2 py-0.5 rounded font-bold text-primary-700">
                          {item.quantity} {item.unit}
                        </span>
                      </div>
                    ))}
                  </div>
                  
                  {order.notes && (
                    <div className="mt-4 p-3 bg-amber-50 rounded text-xs text-amber-800 border border-amber-100">
                      <strong>Notes:</strong> {order.notes}
                    </div>
                  )}
                </div>

                <div className="p-4 bg-white border-t border-gray-100 flex gap-2">
                  <Link 
                    to={`/orders/${order.id}`}
                    className="p-2 border border-gray-200 rounded text-gray-400 hover:text-primary-600 transition-colors"
                  >
                    <ExternalLink size={20} />
                  </Link>
                  {order.status === 'logged' ? (
                    <button
                      onClick={() => handleUpdateStatus(order.id, 'in_preparation')}
                      className="flex-1 bg-amber-500 hover:bg-amber-600 text-white font-bold py-2 rounded shadow-sm transition-colors text-sm"
                    >
                      Start Preparation
                    </button>
                  ) : (
                    <button
                      onClick={() => handleUpdateStatus(order.id, 'ready')}
                      className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 rounded shadow-sm transition-colors text-sm flex items-center justify-center gap-2"
                    >
                      <CheckCircle size={18} /> Mark Ready
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default KitchenPage;
