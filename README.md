# 🏭 LogisTech: Automated Warehouse System

LogisTech is a backend engine designed to simulate and orchestrate a high-volume fulfillment center. It solves real-world logistics problems—like space optimization and truck loading constraints—using advanced data structures and algorithms.

Built with Django and PostgreSQL, it features a persistent state managed by a "Control Tower" (Singleton) that synchronizes in-memory logic with database records.

---

---
## 🧠 Key Features & Algorithms

**1. The Control Tower (Singleton Pattern)**
A single source of truth (LogiMaster) manages the warehouse state. It initializes on server start, loads inventory from PostgreSQL into memory, and reconstructs the truck's LIFO stack from shipment logs.

**2. Smart Storage (Binary Search)**
-**Problem**: Finding the smallest suitable bin for an incoming package among thousands of options.
-**Solution**: Bins are kept sorted by capacity in memory. We use Python's bisect module to perform a **Binary Search (O(log N))** to find the "Best Fit" bin instantly, minimizing wasted space.

**3. The Conveyor Belt (FIFO Queue)**
-Packages are processed in the order they arrive.
-**Queue Rotation Logic**: If a package cannot fit into any available bin, it is automatically rotated from the front to the back of the queue to prevent blockages.

**4. Truck Loader (LIFO Stack & Backtracking)**
-**Loading Dock**: Modeled as a Stack. To remove an item deep inside the truck, all items in front must be temporarily unloaded (LIFO Rollback).
-**Optimization** Algorithm: Uses Backtracking to calculate the optimal cargo load based on a specific constraint:
-**Fragile Items**: Must be shipped "All-or-Nothing" (either all fragile items go, or none do).
-**Standard Items**: Fill the remaining space to maximize utilization.

---

## 🛠️ Tech Stack

```
Language: Python 3.13+
Framework: Django 5.x
Database: PostgreSQL 18
Environment Management: python-dotenv
```

---

## 🚀 Setup Guide

### 1. Prerequisites
Ensure you have Python and PostgreSQL installed.

### 2. Clone & Install

-It is recommended to run this project in an isolated environment.
```
git clone <your-repo-url>
cd LogisTech

# Create Virtual Environment
python -m venv env
# Activate: .\env\Scripts\activate (Windows) or source env/bin/activate (Mac/Linux)

# Install Dependencies
pip install -r requirements.txt
```

### 3. Database Configuration

-1. Create a PostgreSQL database named warehouse.
-2. Create a .env file in the root directory (same level as manage.py) and add your credentials:
```
DB_NAME="warehouse"
DB_USER="postgres"
DB_PASSWORD="YourPasswordHere"
# DB_HOST and DB_PORT are set to localhost:5432 by default in settings.py
```

### 4. Initialize System

```
# Create Database Tables
python manage.py makemigrations warehouse
python manage.py migrate

# Start the Server
python manage.py runserver
```

---

## 📡 API Reference

Base URL: ```http://127.0.0.1:8000/```

### 📦 Warehouse Operations

| Method | Endpoint            | Description |
|--------|----------------------|-------------|
| GET    | `/` or `/generate_bins/` | **Reset & Init:** Clears the database and creates dummy bins with realistic location codes (e.g., `Aisle-01-Sect-02`). |
| GET    | `/view_status/`     | Returns counts for Conveyor, Truck Stack, and Empty Bins. |


### 📥 Ingestion & Storage

| Method | Endpoint          | Description |
|--------|--------------------|-------------|
| POST   | `/ingest/`         | Adds a new package to the Conveyor Queue. |
| GET    | `/process_queue/`  | Moves the next item from Conveyor → Bin using Binary Search. |

-Ingest Body:
```
{
    "size": 15,
    "destination": "New York",
    "is_fragile": false
}

```

### 🚚 Truck Logistics

| Method | Endpoint          | Description |
|--------|--------------------|-------------|
| POST   | `/optimize_load/`  | Runs Backtracking logic to find the best items currently in bins to fill the truck capacity. |
| POST   | `/unload_truck/`   | **Rollback Logic:** Removes a specific item. If the item is buried, it temporarily unloads other items and reloads them back into the bins. |

-Optimize Load Body:
```
{ "capacity": 500 }
```

-Unload Truck Body:
```
{ "tracking_id": "PKG-12345678" }
```

---

## 📂 Project Structure
```
LogisTech/
├── logistech/
│   ├── settings.py       # Django Settings (DB & Apps)
│   └── urls.py           # Main URL Routing
├── warehouse/
│   ├── models.py         # DB Schemas (StorageBin, Package, ShipmentLog)
│   ├── Logistech_Engine.py # Core Algorithms (LogiMaster, Truck, Search)
│   ├── views.py          # API Controllers
│   └── urls.py           # App URLs
├── .env                  # Secrets (Excluded from Git)
├── .gitignore
├── requirements.txt
└── manage.py
```