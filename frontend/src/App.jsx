import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import io from 'socket.io-client';

// Context
import { useAuth } from './context/AuthContext';
import { useToast } from './context/ToastContext';

// Components
import NavBar from './components/NavBar';

// Pages
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import OrdersPage from './pages/OrdersPage';
import NewOrderPage from './pages/NewOrderPage';
import OrderDetailPage from './pages/OrderDetailPage';
import KitchenPage from './pages/KitchenPage';
import DeliveryPage from './pages/DeliveryPage';
import ProductsPage from './pages/ProductsPage';
import CustomersPage from './pages/CustomersPage';
import CustomerDetailPage from './pages/CustomerDetailPage';

const PrivateRoute = ({ children, roles = [] }) => {
  const { user, isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (roles.length > 0 && !roles.includes(user.role)) {
    // Redirect to their default page if they don't have access
    if (user.role === 'kitchen') return <Navigate to="/kitchen" replace />;
    if (user.role === 'delivery') return <Navigate to="/delivery" replace />;
    return <Navigate to="/" replace />;
  }

  return children;
};

function App() {
  const { isAuthenticated, user } = useAuth();
  const { showToast } = useToast();

  useEffect(() => {
    if (isAuthenticated) {
      const socket = io(import.meta.env.VITE_SOCKET_URL);

      socket.on('new_order_created', (data) => {
        showToast(data.message, 'success');
      });

      socket.on('order_status_changed', (data) => {
        if (user.role === 'admin' || (user.role === 'kitchen' && data.new_status === 'logged')) {
          showToast(data.message, 'info');
        }
      });

      socket.on('new_comment', (data) => {
        // Notification for comments could be added here
      });

      return () => socket.disconnect();
    }
  }, [isAuthenticated, user, showToast]);

  return (
    <div className="min-h-screen bg-gray-50">
      {isAuthenticated && <NavBar />}
      <main className={`${isAuthenticated ? 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8' : ''}`}>
        <Routes>
          <Route path="/login" element={!isAuthenticated ? <LoginPage /> : <Navigate to="/" />} />
          
          <Route path="/" element={
            <PrivateRoute roles={['admin']}>
              <DashboardPage />
            </PrivateRoute>
          } />
          
          <Route path="/orders" element={
            <PrivateRoute roles={['admin']}>
              <OrdersPage />
            </PrivateRoute>
          } />
          
          <Route path="/orders/new" element={
            <PrivateRoute roles={['admin']}>
              <NewOrderPage />
            </PrivateRoute>
          } />
          
          <Route path="/orders/:id" element={
            <PrivateRoute roles={['admin', 'kitchen', 'delivery']}>
              <OrderDetailPage />
            </PrivateRoute>
          } />
          
          <Route path="/kitchen" element={
            <PrivateRoute roles={['admin', 'kitchen']}>
              <KitchenPage />
            </PrivateRoute>
          } />
          
          <Route path="/delivery" element={
            <PrivateRoute roles={['admin', 'delivery']}>
              <DeliveryPage />
            </PrivateRoute>
          } />
          
          <Route path="/products" element={
            <PrivateRoute roles={['admin']}>
              <ProductsPage />
            </PrivateRoute>
          } />
          
          <Route path="/customers" element={
            <PrivateRoute roles={['admin']}>
              <CustomersPage />
            </PrivateRoute>
          } />
          
          <Route path="/customers/:id" element={
            <PrivateRoute roles={['admin']}>
              <CustomerDetailPage />
            </PrivateRoute>
          } />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
