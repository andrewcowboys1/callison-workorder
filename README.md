# Callison Electric Heating & Cooling — Work Order App

A simple, mobile-friendly work order management system built for technicians and office staff at Callison Electric Heating & Cooling (Staunton, VA).

## Features

- **Role-based access**
  - **Admin / Office** (Andrew, Melissa): Create work orders, assign technicians, view everything, update any job.
  - **Technicians**: See only their assigned jobs, update status, add notes, parts, times, and photos from the field.

- **Work Order fields tailored to HVAC + Electrical**
  - Priority (Emergency / High / Normal / Low)
  - Job types: AC, Furnace, Heat Pump, Ductwork, Panel Upgrade, EV Charger, Generator, Wiring, Commercial, etc.
  - Customer info, address, equipment details
  - Arrival / departure times
  - Work performed notes
  - Parts used
  - Photo uploads (with captions) — works great from phone camera
  - Printable / PDF-friendly work order sheet with signature line

- **Mobile-first design** — Technicians can use it on their phones in the field.
- **Local SQLite database** — No external services required. Easy to back up.

## Quick Start

### 1. Requirements
- Python 3.10+

### 2. Install & Run

```bash
cd callison-workorders
pip install -r requirements.txt
python app.py
```

Then open in a browser: **http://localhost:5000**

(Or from other devices on the same network: `http://YOUR-COMPUTER-IP:5000`)

### 3. Demo Logins

| Username  | Password     | Role        |
|-----------|--------------|-------------|
| admin     | callison2026 | Admin (Andrew) |
| melissa   | office123    | Admin (Office) |
| jimmy     | tech123      | Technician  |
| tech1     | tech123      | Technician  |
| tech2     | tech123      | Technician  |

**Change these passwords** before real use (edit the seed data or update the database).

## Typical Workflow

1. **Office** creates a new work order → fills customer, job type, description → assigns a tech.
2. **Technician** logs in on phone → sees “My Jobs” sorted by priority.
3. Tech opens the job → updates status to “En Route” / “On Site”.
4. Adds arrival time, work performed notes, parts used, uploads photos of nameplate / before-after.
5. Marks status “Completed”.
6. Office can print the work order or mark it “Invoiced”.

## File Structure

```
callison-workorders/
├── app.py              # Main application
├── requirements.txt
├── workorders.db       # SQLite database (created automatically)
├── uploads/            # Photo storage
├── templates/          # HTML pages
└── README.md
```

## Production Tips

- Change `app.secret_key` in `app.py` to a long random string.
- Run behind a reverse proxy (nginx / Caddy) with HTTPS.
- For multi-user access from the field, host it on a small VPS, Railway, Render, or a always-on computer in the shop.
- Back up `workorders.db` regularly (it contains all your job history).
- To add more technicians: insert rows into the `users` table or extend the seed code.

## Future Enhancements (easy to add later)

- Customer signature capture (canvas)
- SMS notifications when a job is assigned
- QuickBooks / invoice integration
- Offline support (PWA)
- Route optimization / map view
- Recurring maintenance agreements

---

Built for Callison Electric Heating & Cooling  
Family-owned · Staunton, VA · Since 2003
