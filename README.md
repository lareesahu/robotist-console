# Robotist — Australia's Premium Robotics E-Commerce Platform

**Live site:** [www.robotist.com.au](https://www.robotist.com.au)

Robotist is a curated e-commerce and inquiry platform for commercial and industrial robots in the Australian market. It showcases robots across categories including humanoid, logistics, cleaning, security, hospitality, and companion — enabling businesses to browse, compare, and submit purchase or rental inquiries directly.

---

## What This Repo Is

This is the **frontend codebase** for the Robotist website. It is a static HTML/CSS/JS site with no build step — every file is served directly. Changes pushed to the `main` branch automatically deploy to Render within ~60 seconds.

---

## Site Structure

| File / Directory | Purpose |
|---|---|
| `index.html` | Homepage — robot catalogue, category filters, team section, inquiry CTA |
| `about.html` | About Robotist — company story, mission, team |
| `contact.html` | Contact page — inquiry form and office details |
| `products/` | Individual product pages (one `.html` per robot model) |
| `robots/` | Robot product images (`.webp` format) |
| `render.yaml` | Render Blueprint — defines the auto-deploy pipeline |
| `DEPLOY.md` | Full deployment documentation and troubleshooting guide |

### Product Pages (`products/`)

Each file in `products/` is a standalone product detail page for a specific robot model. Current catalogue includes:

- Fourier GR-3 (humanoid)
- Gausium Phantas (cleaning)
- Genisom L1 / M1 (education/companion)
- ISAGE Star Sageman (security)
- KEENON C40-P1 (hospitality)
- LimX OLI (logistics)
- MagicLab MagicDog Y1 (quadruped)
- PNDBotics ADAM (humanoid)
- QiSheng D2 (logistics)
- UNIX AI Panther (security)

---

## Deployment Pipeline

```
git commit → git push to main → Render detects push → site live in ~60s
```

This is a **GitHub → Render auto-deploy** pipeline. The `render.yaml` file at the repo root is the Render Blueprint that controls this. Auto-Deploy is set to **"On Commit"** in the Render dashboard.

**Render service:** `robotist` (Static Site, `srv-d7egikd7vvec73f79q80`)
**Render account login:** `lareesa@pulse-branding.com` / `Evolveyourbrand2021` (email login — do not use GitHub OAuth button)

For full deployment details, troubleshooting, and account setup, see **[DEPLOY.md](./DEPLOY.md)**.

---

## GitHub Actions

A workflow at `.github/workflows/compress-images.yml` automatically compresses any image files (`.jpg`, `.png`, `.webp`, `.gif`) pushed to `main`, committing the optimised versions back to the branch before Render picks them up.

> **Note:** This workflow file requires a GitHub token with `workflows` permission to push via CLI. If it ever goes missing, add it manually via the GitHub web editor at `github.com/lareesahu/robotist-ecommerce/new/main/.github/workflows` — name it `compress-images.yml`.

---

## Account Map

| Platform | Account | Notes |
|---|---|---|
| GitHub (primary) | `lareesahu` | Repo owner — `lareesahu/robotist-ecommerce` |
| GitHub (original) | `lareesawho` | Original repo owner; `lareesahu` added as admin |
| Render | `lareesa@pulse-branding.com` | Hosts the live Robotist service |

---

## Design Notes

- **No build step.** Pure HTML/CSS/JS. Edit files and push — that's it.
- **All images** should be in `.webp` format. The GitHub Action handles compression automatically.
- **Inquiry-based pricing.** Prices are not displayed on the site — all product pages direct users to submit an inquiry.
- **Mobile-first.** All pages are designed to be fully responsive at 320px, 768px, 1024px, and 1440px.

---

## Key Contacts

| Role | Name | Email |
|---|---|---|
| Founder & CEO | Robert Vicencio | — |
| Co-Founder & CMO | Lareesa Hu | lareesa@pulse-branding.com |
