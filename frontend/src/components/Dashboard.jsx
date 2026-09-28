import React, { useEffect, useState } from 'react';
import api from '../services/api';

export default function Dashboard({ onLogout }) {
  const [permissions, setPermissions] = useState([]);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [formData, setFormData] = useState({ employee_code: '', first_name: '', last_name: '', department: '' });

  useEffect(() => {
    fetchUserData();
  }, []);

  const fetchUserData = async () => {
    try {
      const permRes = await api.get('/permissions/me/');
      setIsSuperuser(permRes.data.is_superuser);
      setPermissions(permRes.data.permissions || []);

      if (permRes.data.is_superuser || (permRes.data.permissions || []).includes('VIEW_EMPLOYEE')) {
        fetchEmployees();
      }
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchEmployees = async () => {
    try {
      const empRes = await api.get('/employees/');
      setEmployees(empRes.data);
    } catch (err) {
      console.error('Failed to fetch employees', err);
    }
  };

  const hasPermission = (code) => isSuperuser || permissions.includes(code);

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      if (editId) {
        await api.put(`/employees/${editId}/`, formData);
      } else {
        await api.post('/employees/', formData);
      }
      setShowForm(false);
      setEditId(null);
      setFormData({ employee_code: '', first_name: '', last_name: '', department: '' });
      fetchEmployees();
    } catch (err) {
      const responseData = err.response?.data;
      let errorMsg = 'Unknown error occurred';
      
      if (typeof responseData === 'string' && responseData.includes('<!DOCTYPE html>')) {
        errorMsg = `Server returned HTML error (${err.response.status}). Check your Django terminal or API URL configuration.`;
      } else if (responseData) {
        errorMsg = typeof responseData === 'object' ? JSON.stringify(responseData, null, 2) : responseData;
      } else {
        errorMsg = err.message;
      }
      
      alert(`Operation failed:\n${errorMsg}`);
    }
  };

  const handleEditClick = (emp) => {
    setEditId(emp.id);
    setFormData({ employee_code: emp.employee_code, first_name: emp.first_name, last_name: emp.last_name, department: emp.department });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this employee?')) {
      try {
        await api.delete(`/employees/${id}/`);
        fetchEmployees();
      } catch (err) {
        alert('Failed to delete employee.');
      }
    }
  };

  if (loading) return <div style={{ textAlign: 'center', marginTop: '50px' }}>Loading dashboard...</div>;

  return (
    <div style={{ padding: '20px', maxWidth: '900px', margin: '0 auto', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #ddd', paddingBottom: '15px' }}>
        <h2>Fine-Grained Permission Dashboard</h2>
        <button onClick={onLogout} style={{ padding: '8px 15px', background: '#dc3545', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          Logout
        </button>
      </div>

      <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '5px', margin: '20px 0' }}>
        <h4>Your Active Permissions:</h4>
        {isSuperuser ? (
          <p style={{ color: 'green', fontWeight: 'bold' }}>Superuser (All Permissions Granted)</p>
        ) : (
          <ul>
            {permissions.length > 0 ? permissions.map((p) => <li key={p}>{p}</li>) : <p>No specific function permissions assigned.</p>}
          </ul>
        )}
      </div>

      {hasPermission('VIEW_EMPLOYEE') && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3>Employee Directory</h3>
            {hasPermission('CREATE_EMPLOYEE') && (
              <button onClick={() => { setShowForm(true); setEditId(null); setFormData({ employee_code: '', first_name: '', last_name: '', department: '' }); }} style={{ padding: '8px 12px', background: '#28a745', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                + Add Employee
              </button>
            )}
          </div>

          <table border="1" cellPadding="10" style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#eee' }}>
                <th>ID</th>
                <th>Code</th>
                <th>First Name</th>
                <th>Last Name</th>
                <th>Department</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {employees.length > 0 ? employees.map((emp) => (
                <tr key={emp.id}>
                  <td>{emp.id}</td>
                  <td>{emp.employee_code}</td>
                  <td>{emp.first_name}</td>
                  <td>{emp.last_name}</td>
                  <td>{emp.department}</td>
                  <td>
                    {hasPermission('EDIT_EMPLOYEE') && (
                      <button onClick={() => handleEditClick(emp)} style={{ marginRight: '5px', padding: '5px 10px', background: '#ffc107', border: 'none', borderRadius: '3px', cursor: 'pointer' }}>Edit</button>
                    )}
                    {hasPermission('DELETE_EMPLOYEE') && (
                      <button onClick={() => handleDelete(emp.id)} style={{ padding: '5px 10px', background: '#dc3545', color: 'white', border: 'none', borderRadius: '3px', cursor: 'pointer' }}>Delete</button>
                    )}
                  </td>
                </tr>
              )) : (
                <tr><td colSpan="6" style={{ textAlign: 'center' }}>No employees found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div style={{ marginTop: '30px', padding: '20px', border: '1px solid #ccc', borderRadius: '5px', background: '#fff' }}>
          <h3>{editId ? 'Edit Employee' : 'Create New Employee'}</h3>
          <form onSubmit={handleSave}>
            <div style={{ marginBottom: '10px' }}>
              <label>Employee Code:</label><br />
              <input type="text" value={formData.employee_code} onChange={(e) => setFormData({...formData, employee_code: e.target.value})} required style={{ width: '100%', padding: '6px' }} />
            </div>
            <div style={{ marginBottom: '10px' }}>
              <label>First Name:</label><br />
              <input type="text" value={formData.first_name} onChange={(e) => setFormData({...formData, first_name: e.target.value})} required style={{ width: '100%', padding: '6px' }} />
            </div>
            <div style={{ marginBottom: '10px' }}>
              <label>Last Name:</label><br />
              <input type="text" value={formData.last_name} onChange={(e) => setFormData({...formData, last_name: e.target.value})} required style={{ width: '100%', padding: '6px' }} />
            </div>
            <div style={{ marginBottom: '10px' }}>
              <label>Department:</label><br />
              <input type="text" value={formData.department} onChange={(e) => setFormData({...formData, department: e.target.value})} required style={{ width: '100%', padding: '6px' }} />
            </div>
            <button type="submit" style={{ padding: '8px 15px', background: '#007BFF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', marginRight: '10px' }}>Save</button>
            <button type="button" onClick={() => setShowForm(false)} style={{ padding: '8px 15px', background: '#6c757d', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
          </form>
        </div>
      )}
    </div>
  );
}
