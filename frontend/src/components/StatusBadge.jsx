import React from 'react';

const StatusBadge = ({ status }) => {
  const styles = {
    received: 'bg-gray-100 text-gray-800',
    logged: 'bg-blue-100 text-blue-800',
    in_preparation: 'bg-yellow-100 text-yellow-800',
    ready: 'bg-indigo-100 text-indigo-800',
    delivered: 'bg-green-100 text-green-800',
    cancelled: 'bg-red-100 text-red-800',
  };

  const label = status?.replace('_', ' ').toUpperCase() || 'UNKNOWN';

  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100 text-gray-800'}`}>
      {label}
    </span>
  );
};

export default StatusBadge;
