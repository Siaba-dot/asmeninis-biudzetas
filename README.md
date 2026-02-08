# Personal Budget Tracker

A personal finance tracking app built with **Streamlit + Supabase**, focused on **data accuracy and transparency**.

The application enforces a strict rule:
**balance is never entered manually – it is always calculated from transactions**.

---

## Tech Stack

- Python
- Streamlit
- Supabase (PostgreSQL + Auth)
- Pandas
- Plotly

---

## Core Concepts

- One transaction = one real money movement
- Amounts are always positive
- Transaction type defines direction (income / expense)
- No balance column in the database
- All analytics are derived from raw data

---

## Features

- Email/password authentication (Supabase Auth)
- User-isolated data (`user_email`)
- CRUD for transactions
- Income, expenses, balance KPIs
- Cumulative balance over time
- Income vs expenses charts
- Category-based expense analysis
- Rule-based financial insights (no AI)
- Filtered Excel export

---

## Data Model

**Table: `biudzetas`**

| Column | Description |
|------|------------|
| id | UUID |
| user_email | User identifier |
| data | Transaction date |
| tipas | Income / Expense |
| kategorija | Category |
| suma_eur | Positive amount |

---

## Design Goals

- 100% accurate calculations
- Full user control
- No hidden logic
- No AI, no guessing

---

## Status

Actively used as a personal finance control system.
