# 🌱 MITTI — The Living Soil Cafe
## Website Documentation & Deployment Guide

---

## 📁 Folder Structure

```
mitti/
├── index.html          ← Home page
├── menu.html           ← Menu page (with filter)
├── contact.html        ← Contact, reservation form & map
├── css/
│   └── style.css       ← All styles (design system + pages)
├── js/
│   └── components.js   ← Shared navbar, footer, animations
└── README.md           ← This file
```

---

## 🎨 Design System

| Token         | Value           | Usage               |
|---------------|-----------------|---------------------|
| --soil        | #2C1A0E         | Primary dark        |
| --terracotta  | #C2622D         | Brand accent/CTA    |
| --clay        | #D4875A         | Secondary accent    |
| --sand        | #F0E6D3         | Card backgrounds    |
| --moss        | #4A6741         | Farm/green sections |
| --sage        | #8AAE7E         | Light green         |
| --leaf        | #B5CC9A         | Highlight green     |
| --cream       | #FAF6EF         | Page background     |
| --gold        | #C9A84C         | Special elements    |

**Fonts:** Cormorant Garamond (display) + DM Sans (body)

---

## 🚀 Local Development

1. Download/unzip the `mitti/` folder
2. Open `index.html` in any browser
3. No build tools, no dependencies — pure HTML/CSS/JS

**For live preview during editing:**
```bash
# If you have Python installed:
cd mitti
python -m http.server 8080
# Open: http://localhost:8080
```

---

## 🌐 Free Deployment Options

### Option 1: Netlify (Easiest — Recommended)
1. Go to [netlify.com](https://netlify.com) → Sign up free
2. Drag & drop the `mitti/` folder onto the Netlify dashboard
3. Done! You get a live URL like `mitti-cafe.netlify.app` instantly
4. To use a custom domain: Site Settings → Domain Management → Add domain

### Option 2: GitHub Pages
1. Create a free [github.com](https://github.com) account
2. Create a new repository named `mitti-cafe`
3. Upload all files in the `mitti/` folder
4. Go to: Settings → Pages → Source: Deploy from branch → main → /root
5. Live at: `yourusername.github.io/mitti-cafe`

### Option 3: Vercel
1. Go to [vercel.com](https://vercel.com) → Sign up with GitHub
2. New Project → Import your GitHub repo
3. Deploy — auto-deploys on every push

---

## 🔧 Customization Guide

### Change contact details
In `contact.html`, update these values:
- Address: Search for "C-12, C-Scheme"
- Phone: Search for "+91 141 234 5678"
- Email: Search for "hello@mitti.cafe"

### Add real Google Maps
Replace the `.map-placeholder` div in `contact.html` with:
```html
<iframe
  src="https://www.google.com/maps/embed?pb=YOUR_EMBED_CODE"
  width="100%" height="380" style="border:0;border-radius:24px"
  allowfullscreen loading="lazy">
</iframe>
```
Get embed code: Google Maps → Share → Embed a map → Copy HTML

### Add WhatsApp Chat Button
Add before closing `</body>` in all pages:
```html
<a href="https://wa.me/919876543210?text=Hi!%20I'd%20like%20to%20reserve%20a%20table%20at%20MITTI"
   style="position:fixed;bottom:2rem;right:2rem;background:#25D366;color:white;
          width:56px;height:56px;border-radius:50%;display:flex;align-items:center;
          justify-content:center;font-size:1.6rem;z-index:999;
          box-shadow:0 4px 16px rgba(0,0,0,0.2);text-decoration:none">
  💬
</a>
```

### Update weekly menu
Open `menu.html` → Find the week tag:
```html
<div class="menu-week-tag">🌿 Week of May 5–11, 2025</div>
```
Update the date each Monday.

### Change menu prices
Search for `₹` in `menu.html` and update individual prices.

---

## ✨ Features Included

| Feature | Location |
|---------|----------|
| Animated hydroponic tower hero | index.html |
| Scrolling ticker band | index.html |
| Seasonal harvest calendar | index.html |
| Plant growth tracker widget | index.html |
| Plant adoption subscription section | index.html |
| Customer testimonials | index.html |
| Full menu with category filters | menu.html |
| Harvest add-on banner | menu.html |
| Table reservation form | contact.html |
| Opening hours (today highlighted) | contact.html |
| Newsletter signup | contact.html |
| Map placeholder (ready for Google Maps) | contact.html |
| Mobile-responsive navigation | All pages |
| Smooth scroll animations (Intersection Observer) | All pages |
| Navbar scroll effect | All pages |

---

## 📱 Mobile Responsive
- Full hamburger menu for mobile
- Grid layouts collapse gracefully to single column
- Hero stacks vertically on mobile
- All touch targets meet accessibility guidelines

---

## 🎯 Next Steps / Suggested Improvements
1. **Online ordering** — Integrate with Zomato/Swiggy API or build with Razorpay
2. **Real plant cam** — Embed a Raspberry Pi camera stream via WebRTC
3. **CMS for weekly menu** — Use Contentful or Sanity.io so non-devs can update
4. **WhatsApp integration** — Direct booking via WhatsApp Business API
5. **Analytics** — Add Google Analytics or Plausible for privacy-first tracking
6. **SEO** — Add structured data (JSON-LD) for restaurant schema
7. **PWA** — Add service worker for offline menu access
