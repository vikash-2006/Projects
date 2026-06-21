/**
 * MITTI — components.js  (UPDATED)
 * Save this file at: js/components.js
 * Replaces your existing js/components.js completely.
 *
 * Changes from original:
 *  - Added experience.html and subscribe.html to nav
 *  - Footer updated with correct links
 *  - MITTIReveal uses .fade-in class (instead of .reveal)
 *  - Toast uses window.MITTI.Toast
 */

// ═══════════════════════════════════════
//  1. NAVBAR
// ═══════════════════════════════════════
const MITTINav = {
  links: [
    { href: 'index.html',      label: 'Home'          },
    { href: 'menu.html',       label: 'Menu'          },
    { href: 'experience.html', label: 'Harvest'       },
    { href: 'subscribe.html',  label: 'Adopt a Plant' },
    { href: 'contact.html',    label: 'Contact'       },
    { href: 'login.html',      label: 'Account', auth: true },
  ],

  render() {
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const user = MITTISession.get();

    const navLinks = this.links.map(link => {
      const isActive = currentPage === link.href;
      const label = link.auth && user ? (user.firstName || 'Account') : link.label;
      const icon  = link.auth && user ? this._avatarInitial(user) : '';
      return `
        <a href="${link.href}"
           class="nav__link ${isActive ? 'nav__link--active' : ''}"
           ${isActive ? 'aria-current="page"' : ''}>
          ${icon}${label}
        </a>`;
    }).join('');

    const cartCount = MITTICart.getCount();

    const html = `
      <nav class="nav" role="navigation" aria-label="Main navigation">
        <div class="nav__inner">
          <a href="index.html" class="nav__logo" aria-label="MITTI home">
            <span class="nav__logo-icon" aria-hidden="true">🌱</span>
            <span class="nav__logo-text">MITTI</span>
          </a>
          <div class="nav__links" id="navLinks" role="menubar">
            ${navLinks}
          </div>
          <div class="nav__actions">
            <a href="menu.html" class="nav__cart" aria-label="${cartCount} items in cart">
              🛒
              ${cartCount > 0 ? `<span class="nav__cart-badge" aria-live="polite">${cartCount}</span>` : ''}
            </a>
            <button class="nav__hamburger" id="navHamburger"
                    aria-label="Toggle menu" aria-expanded="false" aria-controls="navLinks">
              <span class="nav__hamburger-line"></span>
              <span class="nav__hamburger-line"></span>
              <span class="nav__hamburger-line"></span>
            </button>
          </div>
        </div>
      </nav>
      <div class="nav__backdrop" id="navBackdrop" aria-hidden="true"></div>
    `;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = html.trim();
    // Insert nav then backdrop at top of body
    while (wrapper.firstElementChild) {
      document.body.insertBefore(wrapper.firstElementChild, document.body.firstChild);
    }
    // Move skip-link to very top
    const skip = document.querySelector('.skip-link');
    if (skip) document.body.insertBefore(skip, document.body.firstChild);

    this._bindEvents();
  },

  _avatarInitial(user) {
    const initial = (user.firstName || '?')[0].toUpperCase();
    return `<span class="nav__avatar" aria-hidden="true">${initial}</span>`;
  },

  _bindEvents() {
    const hamburger = document.getElementById('navHamburger');
    const navLinks  = document.getElementById('navLinks');
    const backdrop  = document.getElementById('navBackdrop');
    if (!hamburger) return;

    const toggle = (open) => {
      navLinks.classList.toggle('nav__links--open', open);
      backdrop.classList.toggle('nav__backdrop--visible', open);
      hamburger.setAttribute('aria-expanded', open);
    };

    hamburger.addEventListener('click', () => {
      toggle(!navLinks.classList.contains('nav__links--open'));
    });
    backdrop.addEventListener('click', () => toggle(false));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') toggle(false); });

    const nav = document.querySelector('.nav');
    window.addEventListener('scroll', () => {
      nav.classList.toggle('nav--scrolled', window.scrollY > 20);
    }, { passive: true });
  }
};


// ═══════════════════════════════════════
//  2. FOOTER
// ═══════════════════════════════════════
const MITTIFooter = {
  render() {
    const year = new Date().getFullYear();
    const html = `
      <footer class="footer" role="contentinfo">
        <div class="footer__inner">
          <div class="footer__brand">
            <a href="index.html" class="footer__logo" aria-label="MITTI home">
              <span aria-hidden="true">🌱</span> MITTI
            </a>
            <p class="footer__tagline">
              Jaipur's living farm cafe.<br>
              Eat what Rajasthan grew. Watch it grow back.
            </p>
            <div class="footer__socials">
              <a href="#" class="footer__social" aria-label="Instagram">📸</a>
              <a href="#" class="footer__social" aria-label="Facebook">📘</a>
              <a href="#" class="footer__social" aria-label="YouTube">▶️</a>
              <a href="#" class="footer__social" aria-label="LinkedIn">💼</a>
            </div>
          </div>
          <nav class="footer__nav" aria-label="Footer navigation">
            <div class="footer__nav-col">
              <h4 class="footer__nav-heading">Visit</h4>
              <a href="menu.html"       class="footer__nav-link">This Week's Menu</a>
              <a href="experience.html" class="footer__nav-link">Harvest Experience</a>
              <a href="contact.html"    class="footer__nav-link">Reserve a Table</a>
              <a href="contact.html"    class="footer__nav-link">Corporate Offsites</a>
            </div>
            <div class="footer__nav-col">
              <h4 class="footer__nav-heading">Grow With Us</h4>
              <a href="subscribe.html"  class="footer__nav-link">Adopt a Plant</a>
              <a href="subscribe.html"  class="footer__nav-link">Harvest Boxes</a>
              <a href="menu.html"       class="footer__nav-link">MITTI Soil Kits</a>
              <a href="experience.html" class="footer__nav-link">School Trips</a>
            </div>
            <div class="footer__nav-col">
              <h4 class="footer__nav-heading">Contact</h4>
              <a href="mailto:hello@mitti.cafe"     class="footer__nav-link">hello@mitti.cafe</a>
              <a href="tel:+919876543210"           class="footer__nav-link">+91 98765 43210</a>
              <span class="footer__nav-link footer__nav-link--text">C-12, C-Scheme, Jaipur</span>
              <span class="footer__nav-link footer__nav-link--text">Tue–Sun: 8am – 10pm</span>
            </div>
          </nav>
        </div>
        <div class="footer__bottom">
          <p>© ${year} MITTI The Living Soil Cafe, Jaipur. All rights reserved. | FSSAI Lic: 12345678901234</p>
          <div class="footer__bottom-links">
            <a href="#">Privacy Policy</a>
            <a href="#">Terms of Use</a>
            <a href="#">Accessibility</a>
          </div>
        </div>
      </footer>
    `;
    document.body.insertAdjacentHTML('beforeend', html);
  }
};


// ═══════════════════════════════════════
//  3. TOAST
// ═══════════════════════════════════════
const MITTIToast = {
  _container: null,
  _timers: {},
  _counter: 0,

  init() {
    if (this._container) return;
    this._container = document.createElement('div');
    this._container.className = 'toast-container';
    this._container.setAttribute('role', 'region');
    this._container.setAttribute('aria-label', 'Notifications');
    this._container.setAttribute('aria-live', 'polite');
    document.body.appendChild(this._container);
  },

  show(message, type = 'success', duration = 4000) {
    this.init();
    const id = ++this._counter;
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('data-id', id);
    toast.innerHTML = `
      <span class="toast__icon" aria-hidden="true">${icons[type] || icons.info}</span>
      <span class="toast__msg">${message}</span>
      <button class="toast__close" aria-label="Dismiss">✕</button>
    `;
    this._container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast--visible'));
    toast.querySelector('.toast__close').addEventListener('click', () => this._dismiss(toast));
    if (duration > 0) {
      this._timers[id] = setTimeout(() => this._dismiss(toast), duration);
    }
    return id;
  },

  _dismiss(toast) {
    toast.classList.remove('toast--visible');
    toast.classList.add('toast--exit');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    const id = toast.getAttribute('data-id');
    clearTimeout(this._timers[id]);
    delete this._timers[id];
  },

  success: (msg, dur) => MITTIToast.show(msg, 'success', dur),
  error:   (msg, dur) => MITTIToast.show(msg, 'error',   dur),
  info:    (msg, dur) => MITTIToast.show(msg, 'info',    dur),
  warning: (msg, dur) => MITTIToast.show(msg, 'warning', dur),
};


// ═══════════════════════════════════════
//  4. SESSION MANAGER
// ═══════════════════════════════════════
const MITTISession = {
  KEYS: {
    USER:  'mitti_user',
    TOKEN: 'mitti_token',
    CART:  'mitti_cart_token',
  },

  save(user, token, cartToken) {
    try {
      localStorage.setItem(this.KEYS.USER,  JSON.stringify(this._normalize(user)));
      localStorage.setItem(this.KEYS.TOKEN, token || '');
      if (cartToken) localStorage.setItem(this.KEYS.CART, cartToken);
    } catch(e) { console.error('[MITTISession] save failed:', e); }
  },

  get() {
    try {
      const raw = localStorage.getItem(this.KEYS.USER);
      if (!raw) return null;
      const user = JSON.parse(raw);
      if (!user || typeof user.id === 'undefined' || !user.email) { this.clear(); return null; }
      return user;
    } catch { this.clear(); return null; }
  },

  getToken()     { return localStorage.getItem(this.KEYS.TOKEN) || ''; },
  getCartToken() { return localStorage.getItem(this.KEYS.CART) || ''; },
  isLoggedIn()   { return this.get() !== null; },

  clear() { Object.values(this.KEYS).forEach(k => localStorage.removeItem(k)); },

  authHeaders() {
    const token = this.getToken();
    return { 'Content-Type': 'application/json', ...(token ? { 'Authorization': `Bearer ${token}` } : {}) };
  },

  _normalize(user) {
    return {
      id:        user.id,
      firstName: user.firstName || user.first_name  || '',
      lastName:  user.lastName  || user.last_name   || '',
      email:     user.email     || '',
      phone:     user.phone     || '',
      role:      user.role      || 'customer',
      createdAt: user.createdAt || user.created_at  || '',
    };
  },

  requireAuth(redirectTo = window.location.href) {
    if (!this.isLoggedIn()) {
      sessionStorage.setItem('mitti_redirect', redirectTo);
      window.location.href = 'login.html';
      return false;
    }
    return true;
  },

  redirectAfterLogin(fallback = 'index.html') {
    const dest = sessionStorage.getItem('mitti_redirect') || fallback;
    sessionStorage.removeItem('mitti_redirect');
    window.location.href = dest;
  },
};


// ═══════════════════════════════════════
//  5. API CLIENT
// ═══════════════════════════════════════
const MITTIApi = {
  BASE: 'http://127.0.0.1:5000',

  async _request(method, path, body = null, auth = false) {
    const headers = auth ? MITTISession.authHeaders() : { 'Content-Type': 'application/json' };
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);
    try {
      const res  = await fetch(`${this.BASE}${path}`, options);
      const data = await res.json();
      if (!res.ok) throw new MITTIApiError(data.error || 'Request failed', res.status, data);
      return data;
    } catch(e) {
      if (e instanceof MITTIApiError) throw e;
      throw new MITTIApiError('Cannot reach server. Is Flask running?', 0, null);
    }
  },

  get:    (path, auth)       => MITTIApi._request('GET',    path, null, auth),
  post:   (path, body, auth) => MITTIApi._request('POST',   path, body, auth),
  patch:  (path, body, auth) => MITTIApi._request('PATCH',  path, body, auth),
  delete: (path, body, auth) => MITTIApi._request('DELETE', path, body, auth),

  auth: {
    login:    (email, password) => MITTIApi.post('/api/auth/login', { email, password }),
    register: (data)            => MITTIApi.post('/api/auth/register', data),
    logout:   ()                => MITTIApi.post('/api/auth/logout', {}, true),
    me:       ()                => MITTIApi.get('/api/auth/me', true),
  },

  reservations: {
    create: (data) => MITTIApi.post('/api/reservations', data, true),
    list:   ()     => MITTIApi.get('/api/reservations', true),
  },

  cart: {
    createSession: ()      => MITTIApi.post('/api/cart/session', {}, true),
    get:    (token)        => MITTIApi.get(`/api/cart/${token}`),
    add:    (data)         => MITTIApi.post('/api/cart/add', data),
    update: (data)         => MITTIApi.patch('/api/cart/update', data),
    remove: (data)         => MITTIApi.delete('/api/cart/remove', data),
    clear:  (token)        => MITTIApi.delete(`/api/cart/clear/${token}`),
  },
};

class MITTIApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'MITTIApiError';
    this.status = status;
    this.data = data;
  }
}


// ═══════════════════════════════════════
//  6. CART STATE
// ═══════════════════════════════════════
const MITTICart = {
  getCount() { return parseInt(sessionStorage.getItem('mitti_cart_count') || '0', 10); },

  setCount(n) {
    sessionStorage.setItem('mitti_cart_count', n);
    const badge = document.querySelector('.nav__cart-badge');
    const cart  = document.querySelector('.nav__cart');
    if (cart) {
      if (n > 0) {
        if (!badge) cart.insertAdjacentHTML('beforeend', `<span class="nav__cart-badge" aria-live="polite">${n}</span>`);
        else badge.textContent = n;
      } else { badge?.remove(); }
    }
  },

  increment() { this.setCount(this.getCount() + 1); },
  decrement() { this.setCount(Math.max(0, this.getCount() - 1)); },
};


// ═══════════════════════════════════════
//  7. SCROLL REVEAL
// ═══════════════════════════════════════
const MITTIReveal = {
  init() {
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            e.target.classList.add('is-visible');
            observer.unobserve(e.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    // Support both .fade-in (new) and .reveal (old) class names
    document.querySelectorAll('.fade-in, .reveal').forEach(el => observer.observe(el));
  }
};


// ═══════════════════════════════════════
//  8. BOOT
// ═══════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  MITTINav.render();
  MITTIFooter.render();
  MITTIToast.init();
  MITTIReveal.init();
});

// Global namespace
window.MITTI = {
  Session: MITTISession,
  Toast:   MITTIToast,
  Api:     MITTIApi,
  Cart:    MITTICart,
};