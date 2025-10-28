import streamlit as st
import mysql.connector
import pandas as pd
import hashlib
import random
import os
from PIL import Image

# -------------------------------------------------------------------
# Ensure fresh DB data each run (help avoid stale caches)
# -------------------------------------------------------------------
try:
    st.cache_data.clear()
except Exception:
    pass

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
# BANNER (visible on all pages)
# --------------------------
def show_banner(image_path):
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #ffe4b5, #fff5ee); color: #222; }
    .stButton>button { background-color: #ff6347; color: white; border-radius: 10px; padding: 8px 20px; border: none; }
    .stButton>button:hover { background-color: #ff4500; color: white; }
    .stDataFrame { border: 1px solid #ffb6c1; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

    if os.path.exists(image_path):
        try:
            st.image(image_path, width=700)
        except Exception as e:
            st.warning(f"Banner image could not be displayed: {e}")
    else:
        st.warning(f"⚠️ Banner image not found: {image_path}")

# --------------------------
# DATA FETCH HELPERS (always fresh)
# --------------------------
def get_restaurants():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Restaurants ORDER BY restaurant_id", conn)
    conn.close()
    return df

# include all menu items (so admin updates are visible even if stock=0)
def get_menu_by_restaurant(restaurant_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM Menu WHERE restaurant_id=%s ORDER BY menu_id", conn, params=(restaurant_id,))
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
        # If you have a DB trigger to increment quantity, or constraint, keep message
        st.warning("Item already in cart; quantity incremented automatically via trigger or DB rule.")
    finally:
        cursor.close()
        conn.close()
    # clear caches and rerun so cart & menu reflect correctly
    try:
        st.cache_data.clear()
    except Exception:
        pass
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
    try:
        st.cache_data.clear()
    except Exception:
        pass
    rerun_app()

# --------------------------
# ORDER FUNCTIONS
# --------------------------
def place_selected_items(user_id, selected_items, payment_method, coupon_code=None):
    if not selected_items:
        st.warning("Please select at least one item to order.")
        return

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Pick a random delivery partner
        dp_df = pd.read_sql("SELECT delivery_partner_id FROM Delivery_Partners", conn)
        if dp_df.empty:
            delivery_partner_id = None
        else:
            delivery_partner_id = int(random.choice(dp_df['delivery_partner_id']))

        # --- Fetch selected cart items (menu_id + quantity)
        cart_items_query = f"SELECT menu_id, quantity FROM Cart WHERE cart_id IN ({','.join(['%s'] * len(selected_items))})"
        cursor.execute(cart_items_query, selected_items)
        cart_items = cursor.fetchall()

        # --- Call your existing procedure for each item
        for _ in selected_items:
            cursor.callproc('PlaceOrderFromCart', [user_id, delivery_partner_id])

        conn.commit()

        # --- Update the latest payment method and coupon
        cursor.execute("SELECT MAX(order_id) AS oid FROM Orders WHERE user_id=%s", (user_id,))
        last_order_id = cursor.fetchone()['oid']

        if last_order_id:
            cursor.execute(
                "UPDATE Payments SET method=%s, coupon_code=%s WHERE order_id=%s",
                (payment_method, coupon_code, last_order_id)
            )
            conn.commit()

        # --- Update stock quantities in the Menu table
        for item in cart_items:
            menu_id = item['menu_id']
            qty_ordered = int(item['quantity'])
            cursor.execute("UPDATE Menu SET stock = GREATEST(stock - %s, 0) WHERE menu_id=%s", (qty_ordered, menu_id))
        conn.commit()

        # --- Clear ordered items from cart
        cursor.execute(f"DELETE FROM Cart WHERE cart_id IN ({','.join(['%s'] * len(selected_items))})", selected_items)
        conn.commit()

        st.success("Selected items ordered successfully! Stock updated in menu.")
    except mysql.connector.Error as e:
        st.error(f"Error placing order: {e}")
    finally:
        cursor.close()
        conn.close()

    try:
        st.cache_data.clear()
    except Exception:
        pass
    rerun_app()


def get_order_items(user_id=None):
    conn = get_connection()
    query = """
        SELECT oi.order_item_id, o.order_id, m.name AS item_name, m.category, r.name AS restaurant_name,
               oi.quantity, (oi.quantity*m.price) AS total, o.status, r.restaurant_id
        FROM Order_Items oi
        JOIN Orders o ON oi.order_id = o.order_id
        JOIN Menu m ON oi.menu_id = m.menu_id
        JOIN Restaurants r ON m.restaurant_id = r.restaurant_id
    """
    if user_id:
        query += " WHERE o.user_id=%s ORDER BY o.order_id DESC"
        df = pd.read_sql(query, conn, params=(user_id,))
    else:
        query += " ORDER BY o.order_id DESC"
        df = pd.read_sql(query, conn)
    conn.close()
    return df

def update_order_status(order_id, new_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Orders SET status=%s WHERE order_id=%s", (new_status, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass
    rerun_app()

def submit_review(user_id, restaurant_id, rating, comment):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.callproc('AddReview', [user_id, restaurant_id, rating, comment])
        conn.commit()
        st.success("Review submitted successfully!")
    except mysql.connector.Error as e:
        st.error(f"Error submitting review: {e}")
    finally:
        cursor.close()
        conn.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass
    rerun_app()

# --------------------------
# LOGIN / SIGNUP
# --------------------------
def show_login_signup():
    st.title("🍔 Food Ordering System")
    choice = st.sidebar.selectbox("Select", ["Login", "Signup", "Admin Login"], key="login_select")

    if choice == "Login":
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="login_btn"):
            user = login_user(email, password)
            if user:
                st.session_state['user'] = user
                st.success(f"Welcome {user['name']}!")
                rerun_app()
            else:
                st.error("Invalid credentials")

    elif choice == "Signup":
        name = st.text_input("Name", key="signup_name")
        email = st.text_input("Email", key="signup_email")
        phone = st.text_input("Phone", key="signup_phone")
        address = st.text_input("Address", key="signup_address")
        password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Signup", key="signup_btn"):
            if signup_user(name, email, phone, address, password):
                st.success("Signup successful! Login now.")

    elif choice == "Admin Login":
        uname = st.text_input("Admin Username", key="admin_user")
        pwd = st.text_input("Admin Password", type="password", key="admin_pass")
        if st.button("Login as Admin", key="admin_login_btn"):
            if uname == "admin" and pwd == "admin123":
                st.session_state['admin'] = True
                st.success("Admin logged in!")
                rerun_app()
            else:
                st.error("Invalid admin credentials")

# --------------------------
# ADMIN PORTAL
# --------------------------
def show_admin_portal():
    st.header("👨‍💼 Admin Dashboard")
    # Admin logout button in sidebar (always visible)
    if st.sidebar.button("Logout (Admin)", key="admin_logout"):
        st.session_state.clear()
        rerun_app()

    tabs = st.tabs(["Restaurants", "Menu", "Orders"])

    # --- RESTAURANTS TAB ---
    with tabs[0]:
        st.subheader("🏢 Manage Restaurants")
        rest_df = get_restaurants()
        st.dataframe(rest_df)

        name = st.text_input("Restaurant Name", key="add_rest_name")
        address = st.text_input("Address", key="add_rest_address")

        if st.button("Add Restaurant", key="add_rest_btn"):
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO Restaurants (name, address) VALUES (%s,%s)", (name, address))
            conn.commit()
            conn.close()
            st.success("✅ Restaurant added successfully!")
            try:
                st.cache_data.clear()
            except Exception:
                pass
            rerun_app()

        if not rest_df.empty:
            rest_name = st.selectbox("Select Restaurant to Delete", rest_df['name'], key="delete_rest_select")
            if st.button("🗑️ Delete Selected Restaurant", key="delete_rest_btn"):
                rest_id = int(rest_df[rest_df['name'] == rest_name]['restaurant_id'].values[0])
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM Menu WHERE restaurant_id=%s", (rest_id,))
                cur.execute("DELETE FROM Restaurants WHERE restaurant_id=%s", (rest_id,))
                conn.commit()
                conn.close()
                st.warning(f"'{rest_name}' deleted successfully!")
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                rerun_app()

    # --- MENU TAB ---
    with tabs[1]:
        rest_df = get_restaurants()
        if not rest_df.empty:
            rest_name = st.selectbox("Select Restaurant", rest_df['name'], key="menu_rest_select")
            rest_id = int(rest_df[rest_df['name'] == rest_name]['restaurant_id'].values[0])
            menu_df = get_menu_by_restaurant(rest_id)
            st.dataframe(menu_df)

            st.markdown("### ➕ Add New Menu Item")
            name = st.text_input("Item Name", key="add_menu_name")
            category = st.text_input("Category", key="add_menu_category")
            price = st.number_input("Price (₹)", min_value=0.0, step=1.0, key="add_menu_price")
            stock = st.number_input("Stock", min_value=0, step=1, key="add_menu_stock")

            if st.button("Add Item", key="add_menu_btn"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO Menu (restaurant_id, name, category, price, stock) VALUES (%s,%s,%s,%s,%s)",
                    (rest_id, name, category, price, stock)
                )
                conn.commit()
                conn.close()
                st.success("✅ Item added successfully!")
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                rerun_app()

            if not menu_df.empty:
                st.markdown("---")
                st.markdown("### ✏️ Update or 🗑️ Delete Menu Item")

                menu_name = st.selectbox("Select Item", menu_df['name'], key="update_menu_select")
                menu_id = int(menu_df[menu_df['name'] == menu_name]['menu_id'].values[0])

                current_price = float(menu_df.loc[menu_df['menu_id'] == menu_id, 'price'].values[0])
                current_stock = int(menu_df.loc[menu_df['menu_id'] == menu_id, 'stock'].values[0])

                new_price = st.number_input("New Price (₹)", min_value=0.0, value=current_price, step=1.0,
                                            key="update_menu_price")
                new_stock = st.number_input("New Stock", min_value=0, value=current_stock, step=1,
                                            key="update_menu_stock")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Update Item", key="update_menu_btn"):
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE Menu SET price=%s, stock=%s WHERE menu_id=%s",
                                    (new_price, new_stock, menu_id))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ '{menu_name}' updated successfully!")
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass
                        rerun_app()

                with col2:
                    if st.button("🗑️ Delete Item", key="delete_menu_btn"):
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("DELETE FROM Menu WHERE menu_id=%s", (menu_id,))
                        conn.commit()
                        conn.close()
                        st.warning(f"'{menu_name}' deleted successfully!")
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass
                        rerun_app()
        else:
            st.warning("⚠️ No restaurants found. Please add one first.")

    # --- ORDERS TAB ---
    with tabs[2]:
        st.subheader("📦 Manage Orders")

        df = get_order_items()
        if df.empty:
            st.info("No orders found.")
        else:
            grouped = df.groupby("order_id")

            for order_id, group in grouped:
                status = group["status"].iloc[0]
                delivery_partner = group["delivery_partner_name"].iloc[0] if "delivery_partner_name" in group else "N/A"

                st.markdown(f"### 🧾 Order #{order_id}")
                st.write(f"**Status:** {status}")
                st.write(f"🛵 **Delivery Partner:** {delivery_partner}")

                st.dataframe(
                    group[['item_name', 'restaurant_name', 'quantity', 'total']],
                    use_container_width=True
                )

                col1, col2 = st.columns(2)

                with col1:
                    if status not in ["Delivered", "Cancelled"]:
                        if st.button(f"✅ Mark Delivered (#{order_id})", key=f"adm_del_{order_id}"):
                            update_order_status(order_id, "Delivered")
                            st.success(f"Order #{order_id} marked as Delivered!")

                with col2:
                    if status not in ["Delivered", "Cancelled"]:
                        if st.button(f"❌ Cancel Order (#{order_id})", key=f"adm_can_{order_id}"):
                            update_order_status(order_id, "Cancelled")
                            st.warning(f"Order #{order_id} has been Cancelled!")

                st.markdown("---")


# --------------------------
# RESTAURANT BROWSING
# --------------------------
def show_restaurants_dropdown_menu():
    # banner is shown in main(); this function preserves original layout and behaviour
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
                st.image(img_path, width=500)
            else:
                st.warning("Image not found for this restaurant.")

            # Always fetch fresh menu to reflect admin changes
            menu_df = get_menu_by_restaurant(row['restaurant_id'])
            if menu_df.empty:
                st.info("No menu available.")
            else:
                for cat in menu_df['category'].unique():
                    with st.expander(cat):
                        cat_items = menu_df[menu_df['category'] == cat]
                        for _, m in cat_items.iterrows():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(f"**{m['name']}** - ₹{m['price']} | Stock: {m['stock']}")
                            with col2:
                                # If stock is zero, show disabled Out of Stock button and avoid invalid number_input
                                try:
                                    stock_val = int(m['stock'])
                                except Exception:
                                    stock_val = 0
                                if stock_val > 0:
                                    qty = st.number_input(
                                        f"qty_{m['menu_id']}", min_value=1, max_value=stock_val, value=1,
                                        step=1, key=f"qty_{m['menu_id']}_user"
                                    )
                                    if st.button("Add to Cart", key=f"add_{m['menu_id']}_user"):
                                        add_to_cart(user['user_id'], m['menu_id'], qty)
                                else:
                                    # disabled Out of Stock button for clarity
                                    st.button("Out of Stock", disabled=True, key=f"out_{m['menu_id']}")

            reviews_df = get_reviews_by_restaurant(row['restaurant_id'])
            if not reviews_df.empty:
                st.markdown("**Reviews:**")
                for _, rev in reviews_df.iterrows():
                    # safe formatting of date if datetime type
                    try:
                        date_str = rev['review_date'].strftime('%Y-%m-%d')
                    except Exception:
                        date_str = str(rev['review_date'])
                    st.write(f"⭐ {rev['rating']} — {rev['comment']}  (_by {rev['user_name']} on {date_str}_)")

# --------------------------
# CART
# --------------------------
def show_cart():
    user = st.session_state['user']
    st.header("🛒 Your Cart")
    cart_df = get_cart(user['user_id'])
    if cart_df.empty:
        st.info("Cart is empty.")
        return
    selected_items = st.multiselect("Select items to order", cart_df['item_name'], key="cart_select")
    selected_cart_ids = cart_df[cart_df['item_name'].isin(selected_items)]['cart_id'].tolist()
    st.dataframe(cart_df[['item_name', 'restaurant_name', 'category', 'quantity', 'price', 'total']])
    for _, row in cart_df.iterrows():
        if st.button(f"Remove {row['item_name']}", key=f"remove_{row['cart_id']}"):
            remove_cart_item(row['cart_id'])
    payment = st.selectbox("Payment Method", ["Credit Card", "Debit Card", "UPI", "Wallet", "Cash"], key="cart_payment")
    coupon = st.text_input("Coupon (optional)", key="cart_coupon")
    if st.button("Place Selected Order", key="cart_order_btn"):
        if selected_cart_ids:
            place_selected_items(user['user_id'], selected_cart_ids, payment, coupon)
        else:
            st.warning("Select at least one item to order.")

# --------------------------
# ORDER HISTORY
# --------------------------
def show_order_history():
    user = st.session_state['user']
    st.header("📦 Order History")

    df = get_order_items(user['user_id'])
    if df.empty:
        st.info("No orders found.")
        return

    grouped = df.groupby('order_id')
    for order_id, order_items in grouped:
        order_status = order_items['status'].iloc[0]
        st.subheader(f"Order #{order_id} - Status: {order_status}")

        # Show assigned delivery partner
        delivery_partner = order_items['delivery_partner_name'].iloc[0] if 'delivery_partner_name' in order_items else None
        if delivery_partner:
            st.write(f"🛵 **Delivery Partner:** {delivery_partner}")

        st.dataframe(order_items[['item_name', 'restaurant_name', 'category', 'quantity', 'total']])

        # --- Review Section ---
        restaurants_in_order = order_items[['restaurant_name', 'restaurant_id']].drop_duplicates()
        rest_options = {row['restaurant_name']: row['restaurant_id'] for _, row in restaurants_in_order.iterrows()}
        if rest_options:
            selected_restaurant = st.selectbox(
                f"Leave a review for Order #{order_id}",
                list(rest_options.keys()),
                key=f"review_rest_{order_id}"
            )
            rating = st.slider("Rating", 1, 5, 5, key=f"review_rate_{order_id}")
            comment = st.text_area("Comment", key=f"review_comment_{order_id}")
            if st.button(f"Submit Review for #{order_id}", key=f"review_btn_{order_id}"):
                submit_review(user['user_id'], rest_options[selected_restaurant], rating, comment)

        # --- Action Buttons ---
        col1, col2 = st.columns(2)
        with col1:
            if order_status not in ["Delivered", "Cancelled"] and st.button(
                f"Mark Delivered #{order_id}", key=f"user_delivered_{order_id}"
            ):
                update_order_status(order_id, "Delivered")
                st.success(f"✅ Order #{order_id} marked as Delivered!")
        with col2:
            if order_status not in ["Delivered", "Cancelled"] and st.button(
                f"Cancel #{order_id}", key=f"user_cancel_{order_id}"
            ):
                update_order_status(order_id, "Cancelled")
                st.warning(f"⚠️ Order #{order_id} Cancelled!")


# --------------------------
# MAIN
# --------------------------
def main():
    # Banner displayed on all pages
    banner_path = r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\banner.jpg"
    show_banner(banner_path)

    st.sidebar.title("🍽️ Food Ordering System")

    # If no user/admin signed in -> show login/signup (login function sets session vars)
    if 'user' not in st.session_state and 'admin' not in st.session_state:
        show_login_signup()
        return

    # If admin signed in -> admin portal
    if 'admin' in st.session_state and st.session_state['admin']:
        show_admin_portal()
        return

    # Normal user navigation (logout as sidebar button)
    if 'user' in st.session_state and st.session_state['user']:
        if st.sidebar.button("Logout", key="user_logout"):
            st.session_state.clear()
            rerun_app()
            return

        menu = st.sidebar.radio("Navigate", ["Browse Restaurants", "Cart", "Orders"], key="main_menu")
        if menu == "Browse Restaurants":
            show_restaurants_dropdown_menu()
        elif menu == "Cart":
            show_cart()
        elif menu == "Orders":
            show_order_history()
        return

    # Fallback
    show_login_signup()

if __name__ == "__main__":
    main()
