/* ============================================================
   Bertrand's Crawfish — Shared JS Utilities
   ============================================================ */

/**
 * Fetch wrapper with JSON body and error handling.
 */
async function apiFetch(url, method = 'GET', body = null) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' }
    };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(url, opts);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.error || `HTTP ${resp.status}`, 'error');
      return null;
    }
    return await resp.json();
  } catch (e) {
    showToast('Network error: ' + e.message, 'error');
    return null;
  }
}

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'success'|'error'|''} type
 */
function showToast(message, type = '') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.className   = 'toast show ' + type;
  setTimeout(() => { toast.className = 'toast'; }, 3500);
}

/**
 * Close a modal by id.
 */
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

/**
 * Format order status for display.
 */
function fmtStatus(status) {
  const map = {
    pending:          'Pending',
    confirmed:        'Confirmed',
    preparing:        'Preparing',
    out_for_delivery: 'Out for Delivery',
    delivered:        'Delivered',
    cancelled:        'Cancelled',
  };
  return map[status] || status;
}

// Close modal when clicking overlay background
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.style.display = 'none';
  }
});

// Keyboard shortcut: Escape closes any open modal
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay').forEach(m => {
      m.style.display = 'none';
    });
  }
});
