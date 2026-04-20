import React, { useState, useEffect } from 'react';
import { 
  Truck, 
  MapPin, 
  Phone, 
  CheckCircle,
  Loader2,
  ExternalLink,
  ShoppingBag
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { deliveryApi, ordersApi } from '../api/api';
import { useToast } from '../context/ToastContext';

const DeliveryPage = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const fetchDeliveryOrders = async () => {
    try {
      const { data } = await deliveryApi.getOrders();
      setOrders(data);
    } catch (err) {
      showToast('Failed to load delivery orders', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeliveryOrders();
    const interval = setInterval(fetchDeliveryOrders, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleMarkDelivered = async (id) => {
    try {
      await ordersApi.updateStatus(id, 'delivered');
      showToast(`Order #${id} marked as DELIVERED`, 'success');
      fetchDeliveryOrders();
    } catch (err) {
      showToast('Failed to update status', 'error');
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-primary-600" size={40} /></div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Truck className="text-primary-600" />
          Delivery Management
        </h1>
        <div className="text-sm font-medium text-primary-600 bg-primary-50 px-4 py-1.5 rounded-full border border-primary-100">
          {orders.length} Orders Ready for Delivery
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="bg-white p-12 rounded-xl border border-dashed border-gray-300 text-center">
          <Truck size={48} className="mx-auto text-gray-300 mb-4" />
          <h2 className="text-xl font-medium text-gray-900">No deliveries ready</h2>
          <p className="text-gray-500">Wait for the kitchen to mark orders as "Ready".</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {orders.map((order) => (
            <div key={order.id} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col">
              <div className="p-4 bg-gray-50 border-b border-gray-100 flex justify-between items-center">
                <span className="text-lg font-bold text-gray-900">Order #{order.id}</span>
                <span className="text-sm text-gray-500 font-medium">{order.item_count} Items</span>
              </div>
              
              <div className="p-6 flex-1 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-primary-50 rounded-lg">
                    <MapPin className="text-primary-600" size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900">{order.customer_name}</h3>
                    <p className="text-sm text-gray-600 mt-1 leading-relaxed">
                      {order.customer_address}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-50 rounded-lg">
                    <Phone className="text-green-600" size={20} />
                  </div>
                  <p className="text-sm font-bold text-gray-900">{order.customer_phone}</p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-50 rounded-lg">
                    <ShoppingBag className="text-amber-600" size={20} />
                  </div>
                  <p className="text-sm text-gray-600">
                    Deliver by: <span className="font-bold text-gray-900">{new Date(order.delivery_date).toLocaleDateString()}</span>
                  </p>
                </div>
              </div>

              <div className="p-4 bg-white border-t border-gray-100 flex gap-3">
                <Link 
                  to={`/orders/${order.id}`}
                  className="px-4 py-2 border border-gray-200 rounded-lg text-gray-500 hover:text-primary-600 hover:bg-gray-50 transition-all flex items-center justify-center"
                >
                  <ExternalLink size={20} />
                </Link>
                <button
                  onClick={() => handleMarkDelivered(order.id)}
                  className="flex-1 bg-green-600 hover:bg-green-700 text-white font-bold py-2.5 rounded-lg shadow-sm transition-all flex items-center justify-center gap-2"
                >
                  <CheckCircle size={20} /> Confirm Delivered
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DeliveryPage;
