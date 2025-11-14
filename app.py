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
    """
    Add item to cart. If the same (user_id, menu_id) already exists,
    increment the quantity. Also set a session_state flag so rapid
    double-fires won't create duplicates from repeated reruns.
    """
    # session key to prevent duplicate processing during the same run
    key = f"added_{user_id}_{menu_id}"
    if st.session_state.get(key):
        # Already processed in this UI run
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Cart has UNIQUE KEY (user_id, menu_id) so ON DUPLICATE KEY works
        cursor.execute("""
            INSERT INTO Cart (user_id, menu_id, quantity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
        """, (user_id, menu_id, quantity))
        conn.commit()
        # Provide a simple message (no balloons)
        st.success("Added to cart!")
        # mark processed for this run (will reset on next rerun)
        st.session_state[key] = True
    except mysql.connector.Error as e:
        st.error(f"DB error adding to cart: {e}")
    finally:
        cursor.close()
        conn.close()

    # clear caches and trigger UI refresh
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
def get_delivery_partners():
    """
    Fetch all available delivery partners from the database.
    Returns a list of dictionaries with keys: delivery_partner_id, name.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT delivery_partner_id, name FROM Delivery_Partners ORDER BY name;")
        partners = cursor.fetchall()
        return partners
    except mysql.connector.Error as e:
        st.error(f"❌ Error fetching delivery partners: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def place_selected_items(user_id, selected_cart_ids, payment_method, coupon_code=None):
    """
    Place order for selected cart rows. Applies coupon, tax, delivery fee
    and stores final total in Orders and Payments.
    """
    if not selected_cart_ids:
        st.warning("No items selected.")
        return

    TAX_RATE = 0.05
    DELIVERY_FEE = 30.00

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1) Create order row (no delivery partner assigned)
        cursor.execute(
            "INSERT INTO Orders (user_id, total_amount, status, delivery_partner_id) VALUES (%s, %s, %s, %s)",
            (user_id, 0.00, 'Pending', None)
        )
        conn.commit()
        v_order_id = cursor.lastrowid

        # 1.a) Assign a delivery partner automatically (random)
        cursor.execute("SELECT delivery_partner_id FROM Delivery_Partners ORDER BY RAND() LIMIT 1")
        partner = cursor.fetchone()
        delivery_partner_id = partner['delivery_partner_id'] if partner else None
        cursor.execute("UPDATE Orders SET delivery_partner_id=%s WHERE order_id=%s", (delivery_partner_id, v_order_id))
        conn.commit()

        # 2) Copy selected cart rows into Order_Items
        placeholders = ",".join(["%s"] * len(selected_cart_ids))
        insert_sql = f"""
            INSERT INTO Order_Items (order_id, menu_id, quantity)
            SELECT %s, menu_id, quantity FROM Cart
            WHERE cart_id IN ({placeholders}) AND user_id = %s
        """
        params = [v_order_id] + selected_cart_ids + [user_id]
        cursor.execute(insert_sql, params)
        conn.commit()

        # 3) Compute subtotal for inserted items
        cursor.execute("""
            SELECT IFNULL(SUM(m.price * oi.quantity), 0.00) AS subtotal
            FROM Order_Items oi
            JOIN Menu m ON oi.menu_id = m.menu_id
            WHERE oi.order_id = %s
        """, (v_order_id,))
        row = cursor.fetchone()
        subtotal = float(row['subtotal'] or 0.0)

        # 4) Coupon lookup + discount calculation (cap by max_discount_amount)
        discount = 0.0
        if coupon_code:
            cursor.execute("""
                SELECT * FROM Coupons
                WHERE code=%s AND active=TRUE AND (expiry_date IS NULL OR expiry_date >= CURDATE())
                LIMIT 1
            """, (coupon_code,))
            coupon = cursor.fetchone()
            if coupon:
                pct = float(coupon.get('discount_percent') or 0) / 100.0
                max_disc = float(coupon.get('max_discount_amount') or 0.0)
                discount = min(subtotal * pct, max_disc)

        subtotal_after_coupon = max(subtotal - discount, 0.0)
        tax_amount = subtotal_after_coupon * TAX_RATE
        final_total = subtotal_after_coupon + tax_amount + (DELIVERY_FEE if subtotal > 0 else 0.0)

        # 5) Update Orders.total_amount with final_total
        cursor.execute("UPDATE Orders SET total_amount=%s WHERE order_id=%s", (final_total, v_order_id))
        conn.commit()

        # 6) Insert Payment record (include coupon_code if Payments table supports it)
        try:
            cursor.execute(
                "INSERT INTO Payments (order_id, amount, method, status, coupon_code) VALUES (%s,%s,%s,%s,%s)",
                (v_order_id, final_total, payment_method, 'Completed', coupon_code)
            )
        except mysql.connector.Error:
            # Fallback if coupon_code column does not exist
            cursor.execute(
                "INSERT INTO Payments (order_id, amount, method, status) VALUES (%s,%s,%s,%s)",
                (v_order_id, final_total, payment_method, 'Completed')
            )
        conn.commit()

        # 7) Remove those cart rows
        delete_sql = f"DELETE FROM Cart WHERE cart_id IN ({placeholders}) AND user_id = %s"
        delete_params = selected_cart_ids + [user_id]
        cursor.execute(delete_sql, delete_params)
        conn.commit()

        # success message (no balloons)
        st.success(f"Order #{v_order_id} placed successfully! Final total: ₹{final_total:.2f}")
        try:
            st.cache_data.clear()
        except Exception:
            pass
        rerun_app()

    except mysql.connector.Error as e:
        st.error(f"❌ Error placing order: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# --------------------------
# Fetch orders for display (this was missing earlier - ensure defined)
# --------------------------
def get_order_items(user_id=None):
    """
    Fetch all orders with restaurant, user, and delivery partner info.
    Returns a flat dataframe with one row per order-item.
    """
    conn = get_connection()
    query = """
        SELECT 
            o.order_id,
            o.user_id,
            o.status,
            o.total_amount,
            o.order_date,
            u.name AS user_name,
            d.name AS delivery_partner_name,
            m.name AS item_name,
            m.category,
            r.name AS restaurant_name,
            r.restaurant_id,
            oi.quantity,
            (m.price * oi.quantity) AS total
        FROM Orders o
        JOIN Users u ON o.user_id = u.user_id
        LEFT JOIN Delivery_Partners d ON o.delivery_partner_id = d.delivery_partner_id
        JOIN Order_Items oi ON o.order_id = oi.order_id
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
    """Update the order's status and trigger history logging."""
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
    """Submit a user review via stored procedure AddReview."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.callproc('AddReview', [user_id, restaurant_id, rating, comment])
        conn.commit()
        st.success("⭐ Review submitted successfully!")
    except mysql.connector.Error as e:
        st.error(f"❌ Error submitting review: {e}")
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
                        if st.button(f" Mark Delivered (#{order_id})", key=f"adm_del_{order_id}"):
                            update_order_status(order_id, "Delivered")
                            st.success(f"Order #{order_id} marked as Delivered!")

                with col2:
                    if status not in ["Delivered", "Cancelled"]:
                        if st.button(f" Cancel Order (#{order_id})", key=f"adm_can_{order_id}"):
                            update_order_status(order_id, "Cancelled")
                            st.warning(f"Order #{order_id} has been Cancelled!")

                st.markdown("---")

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
        'Sandwich Stop': r"C:\Users\Dr Bharathi\Desktop\FOOD ORDERING SYSTEM\images\sandwich-shop.png"
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
                                    # Use a friendly label "Quantity" (not qty_1 etc)
                                    qty = st.number_input(
                                        "Quantity", min_value=1, max_value=stock_val, value=1,
                                        step=1, key=f"qty_{m['menu_id']}_user"
                                    )
                                    # safer Add to Cart button (unique per user & item)
                                    if st.button("Add to Cart", key=f"add_{user['user_id']}_{m['menu_id']}"):
                                        add_to_cart(user['user_id'], m['menu_id'], qty)
                                else:
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

    # Build unique options: label -> cart_id
    # Keep labels clean: no #[id], no (x3). We'll show quantities in the preview table below.
    options = {
        f"{row.item_name} — {row.restaurant_name}": int(row.cart_id)
        for _, row in cart_df.iterrows()
    }
    option_labels = list(options.keys())

    # Selection by unique labels -> cart_ids
    selected_labels = st.multiselect("Select items to order", option_labels, key="cart_select")
    selected_cart_ids = [options[lbl] for lbl in selected_labels]

    # Filter dataframe to only selected rows
    if selected_cart_ids:
        selected_cart_df = cart_df[cart_df['cart_id'].isin(selected_cart_ids)].copy()
        st.subheader("Selected items")
        # Show quantities and totals in table; this avoids needing qty in the label.
        st.dataframe(selected_cart_df[['item_name','restaurant_name','category','quantity','price','total']])
        subtotal = float(selected_cart_df['total'].sum())
    else:
        st.info("No items selected — pick items above to see a preview and total.")
        selected_cart_df = pd.DataFrame()
        subtotal = 0.0

    # Remove buttons for each cart row (unique cart_id)
    for _, row in cart_df.iterrows():
        if st.button(f"Remove {row['item_name']}", key=f"remove_{row['cart_id']}"):
            remove_cart_item(row['cart_id'])
            return  # Streamlit will rerun and reflect changes

    # Payment and coupon input
    payment = st.selectbox("Payment Method",
                           ["Credit Card", "Debit Card", "UPI", "Wallet", "Cash"],
                           key="cart_payment")
    coupon_code = st.text_input("Coupon (optional)", key="cart_coupon").strip()
    coupon_code = coupon_code if coupon_code else None

    # Pricing rules
    TAX_RATE = 0.05          # 5% tax
    DELIVERY_FEE = 30.00     # flat delivery fee

    # Helper: get coupon from DB
    def lookup_coupon(code):
        if not code:
            return None
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("""
                SELECT * FROM Coupons
                WHERE code=%s AND active=TRUE AND (expiry_date IS NULL OR expiry_date >= CURDATE())
                LIMIT 1
            """, (code,))
            return cur.fetchone()
        except Exception:
            return None
        finally:
            cur.close()
            conn.close()

    coupon = lookup_coupon(coupon_code)

    # Compute discount (capped)
    discount = 0.0
    if coupon and subtotal > 0:
        pct = float(coupon.get('discount_percent') or 0) / 100.0
        max_disc = float(coupon.get('max_discount_amount') or 0.0)
        discount = min(subtotal * pct, max_disc)

    subtotal_after_coupon = max(subtotal - discount, 0.0)
    tax_amount = subtotal_after_coupon * TAX_RATE
    final_total = subtotal_after_coupon + tax_amount + (DELIVERY_FEE if subtotal > 0 else 0.0)

    # Show breakdown
    st.markdown("---")
    st.markdown("### Price summary")
    st.write(f"Subtotal: ₹{subtotal:.2f}")
    st.write(f"Coupon discount: -₹{discount:.2f}  {'(' + coupon_code + ')' if coupon else ''}")
    st.write(f"Subtotal after coupon: ₹{subtotal_after_coupon:.2f}")
    st.write(f"Tax ({TAX_RATE*100:.0f}%): ₹{tax_amount:.2f}")
    st.write(f"Delivery fee: ₹{(DELIVERY_FEE if subtotal > 0 else 0.0):.2f}")
    st.markdown(f"**Final total: ₹{final_total:.2f}**")
    st.markdown("---")

    # Place order (disabled if no selection)
    place_btn = st.button("Place Selected Order", key="cart_order_btn", disabled=(len(selected_cart_ids) == 0))
    if place_btn:
        place_selected_items(user['user_id'], selected_cart_ids, payment, coupon_code)

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
