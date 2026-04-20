import React, { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  ShoppingBag, 
  ChefHat, 
  Truck, 
  Package, 
  Users, 
  LogOut,
  Menu,
  X,
  Bell
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { dashboardApi } from '../api/api';

const NavBar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [counts, setCounts] = useState({ kitchen_count: 0, delivery_count: 0, overdue_count: 0 });
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const fetchCounts = async () => {
      try {
        const { data } = await dashboardApi.getNavCounts();
        setCounts(data);
      } catch (err) {
        console.error('Failed to fetch nav counts', err);
      }
    };

    if (user) {
      fetchCounts();
      const interval = setInterval(fetchCounts, 30000);
      return () => clearInterval(interval);
    }
  }, [user]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard, roles: ['admin'] },
    { to: '/orders', label: 'Orders', icon: ShoppingBag, roles: ['admin'] },
    { to: '/kitchen', label: 'Kitchen', icon: ChefHat, roles: ['admin', 'kitchen'], badge: counts.kitchen_count },
    { to: '/delivery', label: 'Delivery', icon: Truck, roles: ['admin', 'delivery'], badge: counts.delivery_count },
    { to: '/products', label: 'Products', icon: Package, roles: ['admin'] },
    { to: '/customers', label: 'Customers', icon: Users, roles: ['admin'] },
  ].filter(item => item.roles.includes(user?.role));

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0 flex items-center gap-2 font-bold text-xl text-primary-600">
              <ShoppingBag className="text-primary-600" />
              <span>FreshPlate</span>
            </div>
            <div className="hidden md:ml-8 md:flex md:space-x-4">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive
                        ? 'text-primary-600 bg-primary-50'
                        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                    }`
                  }
                >
                  <item.icon className="mr-2 h-4 w-4" />
                  {item.label}
                  {item.badge > 0 && (
                    <span className="ml-2 bg-red-100 text-red-600 text-xs font-semibold px-2 py-0.5 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-3">
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
              </div>
              <button
                onClick={handleLogout}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100"
              >
                <LogOut size={20} />
              </button>
            </div>
            <div className="md:hidden flex items-center">
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100"
              >
                {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden bg-white border-b border-gray-200 py-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setIsMobileMenuOpen(false)}
              className={({ isActive }) =>
                `flex items-center px-4 py-3 text-base font-medium transition-colors ${
                  isActive
                    ? 'text-primary-600 bg-primary-50 border-l-4 border-primary-600'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`
              }
            >
              <item.icon className="mr-3 h-5 w-5" />
              {item.label}
              {item.badge > 0 && (
                <span className="ml-auto bg-red-100 text-red-600 text-xs font-semibold px-2.5 py-0.5 rounded-full">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
          <button
            onClick={handleLogout}
            className="w-full flex items-center px-4 py-3 text-base font-medium text-red-600 hover:bg-red-50"
          >
            <LogOut className="mr-3 h-5 w-5" />
            Logout
          </button>
        </div>
      )}

      {/* Overdue Banner */}
      {counts.overdue_count > 0 && user?.role === 'admin' && (
        <div className="bg-red-600 text-white text-center py-1.5 text-sm font-medium">
          <NavLink to="/orders?status=overdue" className="hover:underline flex items-center justify-center gap-2">
            <Bell size={14} />
            There are {counts.overdue_count} overdue orders requiring attention!
          </NavLink>
        </div>
      )}
    </nav>
  );
};

export default NavBar;
