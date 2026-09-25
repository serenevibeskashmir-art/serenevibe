import React, { useState } from 'react';
import { adminLogin } from '../api';

export default function AdminLogin({ onSuccess, subtitle = 'Sign in to create and manage client itineraries.' }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await adminLogin(password);
      onSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <p style={styles.brand}>Serene Vibes Kashmir</p>
        <h1 style={styles.title}>Admin Access</h1>
        <p style={styles.subtitle}>{subtitle}</p>
        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label} htmlFor="admin-password">Password</label>
          <input
            id="admin-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
            required
            autoComplete="current-password"
          />
          {error && <p style={styles.error}>{error}</p>}
          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
        <a href="/" style={styles.backLink}>← Back to website</a>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#eef1f4',
    padding: '24px',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  card: {
    width: '100%',
    maxWidth: '420px',
    background: '#fff',
    border: '1px solid #d8dee6',
    borderRadius: '10px',
    padding: '32px',
    boxShadow: '0 12px 40px rgba(26, 35, 50, 0.08)',
  },
  brand: {
    margin: '0 0 4px',
    fontSize: '0.75rem',
    fontWeight: 700,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: '#b8956b',
  },
  title: {
    margin: '0 0 8px',
    fontSize: '1.75rem',
    color: '#1e3a4f',
    fontFamily: 'Georgia, serif',
  },
  subtitle: {
    margin: '0 0 24px',
    color: '#5a6578',
    fontSize: '0.925rem',
    lineHeight: 1.6,
  },
  form: { display: 'flex', flexDirection: 'column', gap: '12px' },
  label: {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#5a6578',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  input: {
    padding: '10px 12px',
    borderRadius: '6px',
    border: '1px solid #d8dee6',
    fontSize: '0.95rem',
  },
  button: {
    marginTop: '8px',
    padding: '11px 16px',
    background: '#1e3a4f',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  error: { margin: 0, color: '#b42318', fontSize: '0.875rem' },
  backLink: {
    display: 'inline-block',
    marginTop: '20px',
    fontSize: '0.875rem',
    color: '#1e3a4f',
    textDecoration: 'none',
  },
};
