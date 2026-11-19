# SSV Hotel and Restaurant — Restaurant, Table Billing & Khata (Udhari) Management System

A free, self-hosted full-stack Restaurant Management System built with **Python (Flask + SQLite)** and a responsive **HTML/Tailwind/JS** frontend.

## Features
- **Table Management:** Add/remove dining tables, track Occupied vs. Available status, and handle Takeaway/Parcel orders.
- **Table-Wise Order Entry:** 1-click menu item selection (with Veg/Non-Veg & category filters), quantity controls, and custom item entry.
- **Kitchen Order Ticket (KOT):** Live kitchen queue to track Pending → Preparing → Served items.
- **Billing & Receipt:** Generate itemized bills with optional discounts and settle via **Cash, UPI, Card, or Khata (Udhari)**.
- **Khata / Udhari Ledger:** Manage regular weekly/monthly credit customers, add table bills directly to their Khata, view itemized udhari history, and record partial or full payments.
- **Full-Day Sales Report:** Daily revenue breakdown (Cash, UPI, Card, Khata Udhari, and Khata Recoveries), top-selling dishes, and CSV export.

## How to Run Locally (100% Free)
1. Install Python 3.9+ if not already installed.
2. Open a terminal inside this folder and install Flask:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python app.py
   ```
4. Open your browser and go to:
   `http://127.0.0.1:5000`

Your data is automatically saved in a local `restaurant.db` SQLite file—no paid database or cloud account required.
