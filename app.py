import streamlit as st
import mysql.connector
import pandas as pd
import hashlib
import random
import os
from PIL import Image

# --------------------------
# RERUN FUNCTION
# --------------------------
def rerun_app():
    st.session_state['rerun'] = not st.session_state.get('rerun', False)

# --------------------------
# DATABASE CONNECTION
# --------------------------
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Sirishreyu@2431",
        database="FoodOrdering"
    )

# --------------------------
# PASSWORD UTILITIES
# --------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(email, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE email=%s AND password=%s", (email, hash_password(password)))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def signup_user(name, email, phone, address, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Users (name, email, phone, address, password) VALUES (%s,%s,%s,%s,%s)",
            (name, email, phone, address, hash_password(password))
        )
        conn.commit()
        return True
    except mysql.connector.Error as e:
        st.error(f"Error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# --------------------------
# BANNER
# --------------------------
def show_banner(image_path):
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #ffe4b5, #fff5ee); color: #222; }
    .stButton>button { background-color: #ff6347; color: white; border-radius: 10px; padding: 8px 20px; border: none; }
    .stButton>button:hover { background-color: #ff4500; color: white; }
    </style>
    """, unsafe_allow_html=True)

    if os.path.exists(image_path):
        st.image(image_path, width=700)
    else:
        st.warning(f"⚠️ Banner image not found: {image_path}")

# --------------------------
# DATA FETCH HELPERS
# --------------------------
def get_restaurants():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Restaurants", conn)
    conn.close()
    return df

def get_menu_by_restaurant(restaurant_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Menu WHERE restaurant_id=%s AND stock>0", conn, params=(restaurant_id,))
    conn.close()
    return df

def get_reviews_by_restaurant(restaurant_id):
    conn = get_connection()
    df = pd.read_sql("""
        SELECT u.name AS user_name, r.rating, r.comment, r.review_date
        FROM Reviews r
        JOIN Users u ON r.user_id = u.user_id
        WHERE r.restaurant_id=%s
        ORDER BY r.review_date DESC
    """, conn, params=(restaurant_id,))
    conn.close()
    return df

# --------------------------
# CART FUNCTIONS
# --------------------------
def add_to_cart(user_id, menu_id, quantity):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Cart (user_id, menu_id, quantity) VALUES (%s,%s,%s)", (user_id, menu_id, quantity))
        conn.commit()
        st.success("Added to cart!")
    except mysql.connector.Error:
        st.warning("Item already in cart.")
    finally:
        cursor.close()
        conn.close()
    rerun_app()

def get_cart(user_id):
    conn = get_connection()
    df = pd.read_sql("""
        SELECT c.cart_id, m.menu_id, m.name AS item_name, m.category, m.price, c.quantity,
               (m.price * c.quantity) AS total, r.name AS restaurant_name
        FROM Cart c
        JOIN Menu m ON c.menu_id = m.menu_id
        JOIN Restaurants r ON m.restaurant_id = r.restaurant_id
        WHERE c.user_id=%s
    """, conn, params=(user_id,))
    conn.close()
    return df

def remove_cart_item(cart_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Cart WHERE cart_id=%s", (cart_id,))
    conn.commit()
    conn.close()
    st.info("Item removed from cart!")
    rerun_app()

# --------------------------
# RESTAURANT BROWSING
# --------------------------
def show_restaurants_dropdown_menu():
    user = st.session_state['user']
    st.header("🍴 Browse Restaurants")

    restaurant_images = {
        'Pizza Palace': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\pizza-palace.jpg",
        'Sushi World': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\sushi-world.jpg",
        'Burger Hub': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\burger-hub.jpeg",
        'Curry House': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\curry-house.jpeg",
        'Taco Town': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\taco.jpeg",
        'Pasta Corner': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\pasta-corner.jpeg",
        'Sandwich Stop': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\sandwich-shop.jpg"
    }

    restaurants = get_restaurants()
    for _, row in restaurants.iterrows():
        with st.expander(f"{row['name']} - {row['address']}"):
            img_path = restaurant_images.get(row['name'])
            if img_path and os.path.exists(img_path):
                img = Image.open(img_path)
                img = img.resize((500, 300))
                st.image(img)
            else:
                st.warning("⚠️ Image not found for this restaurant.")

            menu_df = get_menu_by_restaurant(row['restaurant_id'])
            if menu_df.empty:
                st.info("No menu available.")
            else:
                categories = menu_df['category'].unique()
                for cat in categories:
                    with st.expander(cat):
                        cat_items = menu_df[menu_df['category'] == cat]
                        for _, m in cat_items.iterrows():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(f"**{m['name']}** - ₹{m['price']} | Stock: {m['stock']}")
                            with col2:
                                qty = st.number_input(f"Qty_{m['menu_id']}", 1, m['stock'], key=f"qty_{m['menu_id']}")
                                if st.button(f"Add to Cart {m['menu_id']}", key=f"add_{m['menu_id']}"):
                                    add_to_cart(user['user_id'], m['menu_id'], qty)

# --------------------------
# MAIN APP
# --------------------------
def main():
    banner_path = r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\banner.jpg"
    show_banner(banner_path)

    if 'user' in st.session_state and st.session_state['user']:
        st.sidebar.write(f"👋 Hello, {st.session_state['user']['name']}")
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            rerun_app()
        choice = st.sidebar.radio("Navigation", ["Browse Restaurants", "Cart"], key="user_nav")
        if choice == "Browse Restaurants":
            show_restaurants_dropdown_menu()
        elif choice == "Cart":
            st.write("Cart section coming next...")
    else:
        show_login_signup()

# --------------------------
# LOGIN / SIGNUP
# --------------------------
def show_login_signup():
    st.title("🍔 Food Ordering System")
    choice = st.sidebar.selectbox("Select", ["Login", "Signup"], key="auth_select")

    if choice == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = login_user(email, password)
            if user:
                st.session_state['user'] = user
                st.success(f"Welcome {user['name']}!")
                rerun_app()
            else:
                st.error("Invalid credentials")

    elif choice == "Signup":
        name = st.text_input("Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        address = st.text_input("Address")
        password = st.text_input("Password", type="password")
        if st.button("Signup"):
            if signup_user(name, email, phone, address, password):
                st.success("Signup successful! Please login.")

# --------------------------
# RUN
# --------------------------
if __name__ == "__main__":
    main()
