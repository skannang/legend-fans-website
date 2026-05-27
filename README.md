# 🌟 Legend Fans Website

> Official fan engagement website for **Legend Saravanan** fans worldwide  
> Backed by **All World Legend Fans Association (AWLFA)**

---

## What this is

A web platform for fans of Tamil businessman and actor Legend Saravanan to:
- Discover community news, events, and charity initiatives
- Watch his videos (synced from YouTube & Facebook with live view counts)
- Connect with their district leader
- Get a verified digital Fan ID
- Receive AWLFA distributions and announcements

This is a **labor-of-love project for friends, by friends.** Not commercial. Built slowly and lovingly.

---

## 🧑‍💻 Team

- **GS Kannan (Senthil)** — Architect & Builder · Malaysia Legends Association
- **Senthil Kumaran V K** — Mentor · Technical Engineering Leader
- **R. Balaganesan** — IT Leader · Chennai

---

## 🏗️ Architecture

```
                          ┌─────────────────────┐
                          │  FANS (Browser)     │
                          │  legendfans.in      │
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  Cloudflare CDN     │
                          │  (Chennai edge)  ⚡  │
                          └──────────┬──────────┘
                                     ▼
              ┌──────────────────────┴──────────────────────┐
              ▼                                             ▼
    ┌──────────────────┐                           ┌──────────────────┐
    │   FRONTEND       │                           │   BACKEND        │
    │   GitHub Pages   │                           │   Render.com     │
    │   (static HTML)  │                           │   FastAPI/Python │
    └──────────────────┘                           └────────┬─────────┘
                                                            │
                                            ┌───────────────┴───────────────┐
                                            ▼                               ▼
                                   ┌──────────────────┐          ┌──────────────────┐
                                   │   DATABASE       │          │   FILE STORAGE   │
                                   │   Neon.tech      │          │   Cloudflare R2  │
                                   │   PostgreSQL     │          │   (10 GB free)   │
                                   └──────────────────┘          └──────────────────┘
```

### Tech Stack

| Layer | Tool | Cost | Why |
|---|---|---|---|
| Frontend | HTML/CSS/JS on **GitHub Pages** | Free | Already on GitHub, zero config |
| CDN | **Cloudflare** Free Plan | Free | Chennai POP = fast for TN fans |
| Backend | **FastAPI (Python)** on **Render.com** | Free | Modern, clean, easy to learn |
| Database | **PostgreSQL** on **Neon.tech** | Free | Already in PRD; serverless Postgres |
| File Storage | **Cloudflare R2** | Free 10 GB | No egress fees |
| Code Repo | **GitHub** (private) | Free | Source control + Pages hosting |

### Why this stack
- **Today: ₹0/month** — fully functional
- **Later: ~₹600/month** when fans grow (just upgrade Render's plan)
- **Migration-friendly** — every piece can move to AWS later if needed
- **Fast in Tamil Nadu** — Cloudflare Chennai POP gives ~50ms latency

---

## 📋 Build Plan

Each step ends with something visible/usable. Pausing is fine after any step.

### Phase A — Get Online Fast (Week 1)
- [x] **Step 1** — Polish homepage + add Videos section ← **WE ARE HERE**
- [ ] **Step 2** — Push to GitHub + enable GitHub Pages
- [ ] **Step 3** — Connect Cloudflare CDN for speed

### Phase B — Real Admin (Week 2–3)
- [ ] **Step 4** — Cloudflare R2 setup (file storage)
- [ ] **Step 5** — Neon.tech setup (database)
- [ ] **Step 6** — Build Python FastAPI backend
- [ ] **Step 7** — Build admin page with login + upload
- [ ] **Step 8** — Homepage reads real content from database

### Phase C — Fan Features (Week 4+)
- [ ] **Step 9** — Real registration
- [ ] **Step 10** — Real login + fan dashboard
- [ ] **Step 11** — YouTube/FB video stats live sync
- [ ] **Step 12** — Leader dashboard + distribution flow

---

## 📁 Repository Structure

```
legend-fans-website/
├── README.md              ← This file
├── frontend/              ← What fans see in browser
│   ├── index.html         ← Homepage
│   ├── (future: login.html, register.html, etc.)
│   └── (future: admin.html — hidden admin page)
├── backend/               ← (Phase B onwards) Python server
│   └── (future: FastAPI app, routes, models)
└── docs/                  ← Notes, decisions, reference
    └── (future: deployment guides, API docs)
```

---

## 🎨 Design System

These are **locked** — same as the existing mockups and PRD:

### Colors
- Primary: `#F26B2C` (warm orange)
- Background: `#FFF4EC` (peach)
- Accents: `#1B5E20` (forest green), `#C9A961` (gold)
- Ink: `#1A0F08` (deep warm black)

### Typography
- Display: **Fraunces** (italic for emphasis)
- Body: **Manrope**
- Tamil: **Noto Sans Tamil**

### Tone
- Warm, festive, Tamil Nadu cultural identity
- Bilingual Tamil + English
- Photo-heavy, community-feeling
- Never cold/tech-app aesthetic

---

## 🚦 Current Status

**Last updated:** May 27, 2026  
**Current step:** Step 1 — Adding Videos section to homepage

---

*Built with patience. நிதானமாக கட்டப்படுகிறது.* 🧡
