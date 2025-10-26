# Food Ordering System 🍔

A web-based application to browse restaurants, order food, track deliveries, and submit reviews. Admins can manage restaurants, menus, and orders. Built with **Python (Streamlit)** and **MySQL**, featuring secure authentication, CRUD operations, triggers, and stored procedures.

---

## Features

- User signup/login with password hashing
- Browse restaurants with images and menus
- Add items to cart and place orders
- Apply coupons during payment
- Track order history and status
- Submit and view restaurant reviews
- Admin dashboard for managing restaurants, menus, and orders
- Automatic stock management via triggers
- Stored procedures for order placement and review submission

---

## Technologies Used

- **Frontend:** Python, Streamlit  
- **Backend:** MySQL  
- **Libraries:** pandas, Pillow, mysql-connector-python

---

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/yourusername/food-ordering-system.git
cd food-ordering-system
2. (Optional) Create and activate a virtual environment:
    python -m venv venv
.\venv\Scripts\Activate.ps1
3. Install dependencies:
    pip install -r requirements.txt
4. Set up the database:
    Open MySQL and run database.sql.
    Update MySQL credentials in app.py if needed.
5. Run the application:
    streamlit run app.py
---
Project Structure
FoodOrderingSystem/
├─ app.py
├─ FoodOrdering.sql
├─ requirements.txt
├─ README.md
└─ images/
     ├─ pizza.jpg
     ├─ sushi.jpeg
     └─ ... (all other images used)
