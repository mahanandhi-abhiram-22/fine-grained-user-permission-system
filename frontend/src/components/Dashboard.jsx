import { useEffect, useState } from 'react';
import api from '../services/api';

export default function Dashboard({ onLogout }) {
  const [permissions, setPermissions] = useState([]);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [employees, setEmployees] = useState([]);
  const [employeeCount, setEmployeeCount] = useState(0);
  const [nextPageUrl, setNextPageUrl] = useState(null);
  const [previousPageUrl, setPreviousPageUrl] = useState(null);
  const [currentPageUrl, setCurrentPageUrl] = useState('/employees/');
  const [loading, setLoading] = useState(true);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [employeeError, setEmployeeError] = useState('');
  const [dashboardError, setDashboardError] = useState('');
  const [showPermissionManager, setShowPermissionManager] = useState(false);
  const [permissionAdminLoading, setPermissionAdminLoading] = useState(false);
  const [permissionAdminError, setPermissionAdminError] = useState('');
  const [permissionAdminNotice, setPermissionAdminNotice] = useState('');
  const [permissionUsers, setPermissionUsers] = useState([]);
  const [availableFunctions, setAvailableFunctions] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedPermissionCodes, setSelectedPermissionCodes] = useState([]);
  
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [formData, setFormData] = useState({ employee_code: '', first_name: '', last_name: '', department: '' });

  const fetchEmployees = async (pageUrl = '/employees/') => {
    setEmployeesLoading(true);
    setEmployeeError('');
    try {
      const empRes = await api.get(pageUrl);
      setEmployees(empRes.data.results || []);
      setEmployeeCount(empRes.data.count ?? 0);
      setNextPageUrl(empRes.data.next);
      setPreviousPageUrl(empRes.data.previous);
      setCurrentPageUrl(pageUrl);
    } catch (err) {
      console.error('Failed to fetch employees', err);
      const detail = err.response?.data?.detail;
      setEmployeeError(typeof detail === 'string' ? detail : 'Unable to load employees. Please try again.');
    } finally {
      setEmployeesLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    api.get('/permissions/me/')
      .then((permRes) => {
        if (!active) return;
        const permissionCodes = permRes.data.permissions || [];
        setIsSuperuser(permRes.data.is_superuser);
        setPermissions(permissionCodes);

        if (!permissionCodes.includes('VIEW_EMPLOYEE')) return;
        setEmployeesLoading(true);
        setEmployeeError('');
        return api.get('/employees/')
          .then((empRes) => {
            if (!active) return;
            setEmployees(empRes.data.results || []);
            setEmployeeCount(empRes.data.count ?? 0);
            setNextPageUrl(empRes.data.next);
            setPreviousPageUrl(empRes.data.previous);
            setCurrentPageUrl('/employees/');
          })
          .catch((err) => {
            if (!active) return;
            console.error('Failed to fetch employees', err);
            const detail = err.response?.data?.detail;
            setEmployeeError(typeof detail === 'string' ? detail : 'Unable to load employees. Please try again.');
          })
          .finally(() => {
            if (active) setEmployeesLoading(false);
          });
      })
      .catch((err) => {
        if (!active) return;
        console.error('Failed to load dashboard data', err);
        setDashboardError('Unable to load your dashboard permissions.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const hasPermission = (code) => permissions.includes(code);

  const openPermissionManager = async () => {
    setShowPermissionManager(true);
    setPermissionAdminLoading(true);
    setPermissionAdminError('');
    setPermissionAdminNotice('');
    try {
      const response = await api.get('/permissions/manage/');
      setPermissionUsers(response.data.users || []);
      setAvailableFunctions(response.data.functions || []);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setPermissionAdminError(typeof detail === 'string' ? detail : 'Unable to load permission management data.');
    } finally {
      setPermissionAdminLoading(false);
    }
  };

  const handlePermissionUserChange = (event) => {
    const userId = event.target.value;
    setSelectedUserId(userId);
    const user = permissionUsers.find((candidate) => String(candidate.id) === userId);
    setSelectedPermissionCodes(user?.permissions || []);
    setPermissionAdminNotice('');
  };

  const handlePermissionToggle = (code) => {
    setSelectedPermissionCodes((currentCodes) => (
      currentCodes.includes(code)
        ? currentCodes.filter((currentCode) => currentCode !== code)
        : [...currentCodes, code]
    ));
  };

  const handlePermissionSave = async (event) => {
    event.preventDefault();
    if (!selectedUserId) return;

    setPermissionAdminLoading(true);
    setPermissionAdminError('');
    setPermissionAdminNotice('');
    try {
      await api.post('/permissions/assign/', {
        user_id: Number(selectedUserId),
        function_codes: selectedPermissionCodes,
      });
      setPermissionUsers((users) => users.map((user) => (
        String(user.id) === selectedUserId
          ? { ...user, permissions: [...selectedPermissionCodes].sort() }
          : user
      )));
      setPermissionAdminNotice('Permissions updated successfully.');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setPermissionAdminError(typeof detail === 'string' ? detail : 'Unable to update permissions.');
    } finally {
      setPermissionAdminLoading(false);
    }
  };

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
      fetchEmployees(editId ? currentPageUrl : '/employees/');
    } catch (err) {
      const responseData = err.response?.data;
      const errorMsg = typeof responseData === 'string' && responseData.includes('<!DOCTYPE html>')
        ? `Server returned HTML error (${err.response.status}). Check your Django terminal or API URL configuration.`
        : responseData
          ? typeof responseData === 'object' ? JSON.stringify(responseData, null, 2) : responseData
          : err.message;
      
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
        const pageUrl = employees.length === 1 && previousPageUrl ? previousPageUrl : currentPageUrl;
        fetchEmployees(pageUrl);
      } catch {
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
      {dashboardError && <p role="alert" style={{ color: '#b00020', marginTop: '15px' }}>{dashboardError}</p>}

      {hasPermission('ASSIGN_PERMISSION') && (
        <section style={{ margin: '20px 0', textAlign: 'left' }}>
          <button type="button" onClick={openPermissionManager} disabled={permissionAdminLoading}>
            Manage user permissions
          </button>
          {showPermissionManager && (
            <div style={{ marginTop: '12px', padding: '16px', border: '1px solid #ddd' }}>
              <h3>Manage user permissions</h3>
              {permissionAdminError && <p role="alert" style={{ color: '#b00020' }}>{permissionAdminError}</p>}
              {permissionAdminNotice && <p role="status">{permissionAdminNotice}</p>}
              {permissionAdminLoading ? (
                <p role="status">Loading permission data...</p>
              ) : (
                <form onSubmit={handlePermissionSave}>
                  <label htmlFor="permission-target-user">Target user</label>
                  <select id="permission-target-user" value={selectedUserId} onChange={handlePermissionUserChange}>
                    <option value="">Select a user</option>
                    {permissionUsers.map((user) => (
                      <option key={user.id} value={user.id}>{user.email}</option>
                    ))}
                  </select>
                  <fieldset disabled={!selectedUserId || permissionAdminLoading}>
                    <legend>Function permissions</legend>
                    {availableFunctions.map((permission) => (
                      <label key={permission.code} style={{ display: 'block' }}>
                        <input
                          type="checkbox"
                          checked={selectedPermissionCodes.includes(permission.code)}
                          onChange={() => handlePermissionToggle(permission.code)}
                        />
                        {permission.name} ({permission.code})
                      </label>
                    ))}
                  </fieldset>
                  <button type="submit" disabled={!selectedUserId || permissionAdminLoading}>
                    Save permissions
                  </button>
                </form>
              )}
            </div>
          )}
        </section>
      )}

      <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '5px', margin: '20px 0' }}>
        <h4>Your Active Permissions:</h4>
        {isSuperuser && <p style={{ color: 'green', fontWeight: 'bold' }}>Superuser account; employee function permissions still apply.</p>}
        <ul>
          {permissions.length > 0 ? permissions.map((p) => <li key={p}>{p}</li>) : <p>No specific function permissions assigned.</p>}
        </ul>
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

          <p>Total employees: {employeeCount}</p>
          {employeeError && <p role="alert" style={{ color: '#b00020' }}>{employeeError}</p>}
          {employeesLoading ? (
            <p role="status">Loading employees...</p>
          ) : (
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
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px' }}>
            <button type="button" onClick={() => fetchEmployees(previousPageUrl)} disabled={!previousPageUrl || employeesLoading}>
              Previous
            </button>
            <button type="button" onClick={() => fetchEmployees(nextPageUrl)} disabled={!nextPageUrl || employeesLoading}>
              Next
            </button>
          </div>
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
