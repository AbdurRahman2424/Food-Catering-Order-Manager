import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Clock, 
  CheckCircle, 
  FileText, 
  Printer, 
  MessageSquare, 
  Send,
  Loader2,
  ChevronRight,
  RefreshCw,
  Download
} from 'lucide-react';
import { ordersApi } from '../api/api';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';
import io from 'socket.io-client';

const OrderDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  
  const [orderData, setOrderData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);

  useEffect(() => {
    const fetchOrder = async () => {
      try {
        const { data } = await ordersApi.getOrder(id);
        setOrderData(data);
      } catch (err) {
        showToast('Failed to load order details', 'error');
        navigate('/orders');
      } finally {
        setLoading(false);
      }
    };

    fetchOrder();

    // SocketIO for live comments
    const socket = io(import.meta.env.VITE_SOCKET_URL);
    socket.on('new_comment', (data) => {
      if (data.order_id === parseInt(id)) {
        setOrderData(prev => ({
          ...prev,
          comments: [...prev.comments, {
            staff_name: data.staff_name,
            comment: data.comment,
            created_at: data.time
          }]
        }));
      }
    });

    socket.on('order_status_changed', (data) => {
      if (data.order_id === parseInt(id)) {
        setOrderData(prev => ({
          ...prev,
          order: { ...prev.order, status: data.new_status }
        }));
        showToast(`Order status updated to ${data.new_status}`, 'info');
      }
    });

    return () => socket.disconnect();
  }, [id]);

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!comment.trim()) return;
    setSubmittingComment(true);
    try {
      await ordersApi.addComment(id, comment);
      setComment('');
    } catch (err) {
      showToast('Failed to add comment', 'error');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleReorder = async () => {
    try {
      const { data } = await ordersApi.reorder(id);
      // Pre-fill Logic: We could navigate to new order with state
      navigate('/orders/new', { state: { prefill: data } });
    } catch (err) {
      showToast('Failed to pre-fill reorder', 'error');
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-primary-600" size={40} /></div>;

  const { order, items, comments, total_price } = orderData;
  const steps = ['received', 'logged', 'in_preparation', 'ready', 'delivered'];
  const currentStepIdx = steps.indexOf(order.status);

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <span className="hover:text-primary-600 cursor-pointer" onClick={() => navigate('/orders')}>Orders</span>
            <ChevronRight size={14} />
            <span className="text-gray-900 font-medium">Order #{order.id}</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            Order #{order.id}
            <StatusBadge status={order.status} />
          </h1>
        </div>
        <div className="flex gap-3 w-full md:w-auto">
          <button 
            onClick={handleReorder}
            className="flex-1 md:flex-none inline-flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <RefreshCw size={18} className="mr-2" />
            Reorder
          </button>
          <a 
            href={ordersApi.getInvoicePdfUrl(id)} 
            target="_blank"
            rel="noreferrer"
            className="flex-1 md:flex-none inline-flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
          >
            <Download size={18} className="mr-2" />
            Invoice PDF
          </a>
        </div>
      </div>

      {/* Status Stepper */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-6">Order Progress</h3>
        <div className="relative">
          <div className="absolute top-4 left-0 w-full h-0.5 bg-gray-200" />
          <div 
            className="absolute top-4 left-0 h-0.5 bg-primary-600 transition-all duration-500" 
            style={{ width: `${(currentStepIdx / (steps.length - 1)) * 100}%` }}
          />
          <div className="relative flex justify-between">
            {steps.map((step, idx) => (
              <div key={step} className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center z-10 transition-colors ${
                  idx <= currentStepIdx ? 'bg-primary-600 text-white' : 'bg-white border-2 border-gray-200 text-gray-400'
                }`}>
                  {idx < currentStepIdx ? <CheckCircle size={18} /> : <span className="text-xs font-bold">{idx + 1}</span>}
                </div>
                <span className={`mt-2 text-xs font-medium capitalize ${idx <= currentStepIdx ? 'text-primary-600' : 'text-gray-400'}`}>
                  {step.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Order Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-6 border-b border-gray-100 flex justify-between items-center">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <FileText size={18} className="text-primary-600" />
                Items Summary
              </h3>
              <span className="text-sm text-gray-500">Placed on {new Date(order.created_at).toLocaleDateString()}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Price</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Qty</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{item.product_name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 text-center">${parseFloat(item.unit_price).toFixed(2)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 text-center">{item.quantity} {item.unit}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900 text-right">
                        ${(item.quantity * item.unit_price).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-50">
                  <tr>
                    <td colSpan="3" className="px-6 py-4 text-right text-sm font-bold text-gray-900">Grand Total</td>
                    <td className="px-6 py-4 text-right text-lg font-bold text-primary-600">${total_price.toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            {order.notes && (
              <div className="p-4 bg-amber-50 border-t border-amber-100">
                <p className="text-xs font-bold text-amber-800 uppercase mb-1">Notes:</p>
                <p className="text-sm text-amber-900">{order.notes}</p>
              </div>
            )}
          </div>

          {/* Comments Section */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col h-[400px]">
            <div className="p-4 border-b border-gray-100 flex items-center gap-2">
              <MessageSquare size={18} className="text-primary-600" />
              <h3 className="font-semibold text-gray-900">Communication & Logs</h3>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
              {comments.length === 0 ? (
                <p className="text-center text-gray-400 text-sm py-10">No comments yet.</p>
              ) : (
                comments.map((c, idx) => (
                  <div key={idx} className={`flex flex-col ${c.staff_name === user?.name ? 'items-end' : 'items-start'}`}>
                    <div className={`max-w-[80%] rounded-lg p-3 text-sm ${
                      c.staff_name === user?.name 
                        ? 'bg-primary-600 text-white rounded-tr-none' 
                        : 'bg-white border border-gray-200 text-gray-800 rounded-tl-none'
                    }`}>
                      <p className="font-bold text-xs mb-1 opacity-80">{c.staff_name}</p>
                      <p>{c.comment}</p>
                    </div>
                    <span className="text-[10px] text-gray-400 mt-1">{c.created_at}</span>
                  </div>
                ))
              )}
            </div>
            <form onSubmit={handleAddComment} className="p-4 bg-white border-t border-gray-100 flex gap-2">
              <input
                type="text"
                className="flex-1 p-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500 text-sm"
                placeholder="Write a message..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <button 
                type="submit" 
                disabled={submittingComment || !comment.trim()}
                className="p-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
              >
                {submittingComment ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}
              </button>
            </form>
          </div>
        </div>

        {/* Customer Sidebar */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-4">
            <h3 className="font-semibold text-gray-900 border-b border-gray-100 pb-2">Customer Info</h3>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400 uppercase font-bold">Name</p>
                <p className="text-sm font-medium text-gray-900">{order.customer_name}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase font-bold">Phone</p>
                <p className="text-sm font-medium text-gray-900">{order.customer_phone}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase font-bold">Email</p>
                <p className="text-sm font-medium text-gray-900">{order.customer_email || 'N/A'}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase font-bold">Delivery Address</p>
                <p className="text-sm font-medium text-gray-900">{order.customer_address}</p>
              </div>
            </div>
            <button 
              onClick={() => navigate(`/customers/${order.customer_id}`)}
              className="w-full mt-2 text-sm text-primary-600 font-medium hover:underline flex items-center justify-center gap-1"
            >
              View History <ChevronRight size={14} />
            </button>
          </div>

          <div className="bg-primary-600 p-6 rounded-xl shadow-lg text-white space-y-4">
            <h3 className="font-semibold border-b border-primary-500 pb-2">Logistics</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Clock size={20} className="text-primary-200" />
                <div>
                  <p className="text-xs text-primary-200 uppercase font-bold">Target Date</p>
                  <p className="text-sm font-bold">{new Date(order.delivery_date).toLocaleDateString()}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Printer size={20} className="text-primary-200" />
                <div>
                  <p className="text-xs text-primary-200 uppercase font-bold">Invoiced By</p>
                  <p className="text-sm font-bold">{order.staff_name}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OrderDetailPage;
