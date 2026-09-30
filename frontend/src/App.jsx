import { useEffect, useState } from 'react';
import Login from './components/Login.jsx';
import Dashboard from './components/Dashboard.jsx';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('access_token'));

  useEffect(() => {
    const handleSessionExpired = () => setIsAuthenticated(false);
    window.addEventListener('auth:expired', handleSessionExpired);
    return () => window.removeEventListener('auth:expired', handleSessionExpired);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setIsAuthenticated(false);
  };

  return (
    <div>
      {isAuthenticated ? (
        <Dashboard onLogout={handleLogout} />
      ) : (
        <Login onLoginSuccess={() => setIsAuthenticated(true)} />
      )}
    </div>
  );
}
