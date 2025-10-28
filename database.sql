DROP DATABASE IF EXISTS FoodOrdering;
CREATE DATABASE FoodOrdering;
USE FoodOrdering;

-- TABLES 
-- Users
CREATE TABLE Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    address VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Restaurants
CREATE TABLE Restaurants (
    restaurant_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(255),
    phone VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Delivery partners (Riders)
CREATE TABLE Delivery_Partners (
    delivery_partner_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    phone VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Menu: added stock column to simulate inventory
CREATE TABLE Menu (
    menu_id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(8,2) NOT NULL COMMENT 'Price in INR',
    category VARCHAR(50),
    stock INT DEFAULT 100, -- inventory for demo
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id)
);

-- Orders
CREATE TABLE Orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10,2) DEFAULT 0.00,
    status ENUM('Pending', 'Confirmed', 'Out for Delivery', 'Delivered', 'Cancelled') DEFAULT 'Pending',
    delivery_partner_id INT DEFAULT NULL,
    coupon_code VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (delivery_partner_id) REFERENCES Delivery_Partners(delivery_partner_id)
);

-- Order items (junction)
CREATE TABLE Order_Items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    menu_id INT NOT NULL,
    quantity INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES Orders(order_id),
    FOREIGN KEY (menu_id) REFERENCES Menu(menu_id),
    CHECK (quantity > 0)
);

-- Cart (unique per user/menu: a user can't have duplicate rows for same menu)
CREATE TABLE Cart (
    cart_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    menu_id INT NOT NULL,
    quantity INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (menu_id) REFERENCES Menu(menu_id),
    UNIQUE KEY uniq_user_menu (user_id, menu_id),
    CHECK (quantity > 0)
);

-- Reviews
CREATE TABLE Reviews (
    review_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    restaurant_id INT NOT NULL,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment VARCHAR(500),
    review_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id)
);

-- Payments
CREATE TABLE Payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    amount DECIMAL(10,2),
    method VARCHAR(50),
    status ENUM('Pending', 'Completed', 'Failed') DEFAULT 'Pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES Orders(order_id)
);

-- Order status history (audit log)
CREATE TABLE Order_Status_History (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(100) DEFAULT 'system',
    FOREIGN KEY (order_id) REFERENCES Orders(order_id)
);

-- Coupons
CREATE TABLE Coupons (
    coupon_id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) UNIQUE,
    discount_percent INT CHECK (discount_percent BETWEEN 0 AND 100),
    max_discount_amount DECIMAL(10,2),
    expiry_date DATE,
    active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT
    CURRENT_TIMESTAMP
);

-- SAMPLE DATA 

-- Users
INSERT INTO Users (name, email, phone, address) VALUES
('Alice', 'alice@example.com', '9876543210', '123 Main St, Delhi'),
('Bob', 'bob@example.com', '9123456780', '456 Oak Rd, Mumbai'),
('Charlie', 'charlie@example.com', '9988776655', '78 Park Lane, Bangalore'),
('Diana', 'diana@example.com', '9871234567', '90 Elm St, Pune'),
('Eve', 'eve@example.com', '9765432109', '21 Maple Ave, Chennai'),
('Frank', 'frank@example.com', '9122334455', '33 Cedar Rd, Hyderabad'),
('Grace', 'grace@example.com', '9233445566', '55 Spruce St, Kolkata');

-- Restaurants
INSERT INTO Restaurants (name, address, phone) VALUES
('Pizza Palace', '12 Baker St, Delhi', '9112345678'),
('Sushi World', '34 Maple Ave, Mumbai', '9223456789'),
('Burger Hub', '56 Oak St, Bangalore', '9334455667'),
('Curry House', '78 Pine Rd, Pune', '9445566778'),
('Taco Town', '90 Cedar Ave, Chennai', '9556677889'),
('Pasta Corner', '101 Main Rd, Hyderabad', '9667788990'),
('Sandwich Stop', '202 Elm St, Kolkata', '9778899001');

-- Delivery partners
INSERT INTO Delivery_Partners (name, phone) VALUES
('John Doe', '9000000001'),
('Jane Smith', '9000000002'),
('Mike Johnson', '9000000003'),
('Sara Lee', '9000000004'),
('Tom Brown', '9000000005'),
('Linda White', '9000000006'),
('Kevin Black', '9000000007');

-- Menu (35+ items) — includes stock values
INSERT INTO Menu (restaurant_id, name, price, category, stock) VALUES
(1, 'Pepperoni Pizza', 325.00, 'Pizza', 30),
(1, 'Veggie Pizza', 280.00, 'Pizza', 40),
(1, 'Cheese Pizza', 300.00, 'Pizza', 35),
(1, 'Margherita Pizza', 290.00, 'Pizza', 25),
(1, 'Garlic Bread', 120.00, 'Sides', 50),
(1, 'Mozzarella Sticks', 150.00, 'Sides', 40),
(1, 'Coke', 50.00, 'Drink', 200),
(1, 'Pepsi', 50.00, 'Drink', 200),
(1, 'Chocolate Lava Cake', 180.00, 'Dessert', 30),
(2, 'Salmon Sushi', 340.00, 'Sushi', 20),
(2, 'Tuna Roll', 280.00, 'Sushi', 25),
(2, 'Veggie Roll', 250.00, 'Sushi', 30),
(2, 'Dragon Roll', 360.00, 'Sushi', 15),
(2, 'Miso Soup', 100.00, 'Sides', 50),
(2, 'Edamame', 120.00, 'Sides', 50),
(2, 'Green Tea', 60.00, 'Drink', 100),
(2, 'Mochi Ice Cream', 150.00, 'Dessert', 20),
(3, 'Cheeseburger', 150.00, 'Burger', 60),
(3, 'Veggie Burger', 120.00, 'Burger', 50),
(3, 'Chicken Burger', 170.00, 'Burger', 70),
(3, 'Fries', 80.00, 'Sides', 120),
(3, 'Chicken Nuggets', 100.00, 'Sides', 90),
(3, 'Pepsi', 50.00, 'Drink', 200),
(3, 'Milkshake', 120.00, 'Drink', 60),
(4, 'Butter Chicken', 400.00, 'Curry', 30),
(4, 'Paneer Tikka', 350.00, 'Curry', 35),
(4, 'Dal Makhani', 300.00, 'Curry', 40),
(4, 'Naan', 60.00, 'Bread', 200),
(4, 'Jeera Rice', 120.00, 'Rice', 150),
(4, 'Mango Lassi', 90.00, 'Drink', 100),
(4, 'Gulab Jamun', 80.00, 'Dessert', 50),
(5, 'Chicken Taco', 110.00, 'Taco', 50),
(5, 'Beef Taco', 120.00, 'Taco', 40),
(5, 'Veggie Taco', 100.00, 'Taco', 45),
(5, 'Nachos', 140.00, 'Sides', 60),
(5, 'Salsa Dip', 60.00, 'Sides', 200),
(5, 'Coke', 50.00, 'Drink', 200),
(5, 'Churros', 130.00, 'Dessert', 40),
(6, 'Spaghetti Bolognese', 320.00, 'Pasta', 30),
(6, 'Penne Alfredo', 300.00, 'Pasta', 30),
(6, 'Mac & Cheese', 280.00, 'Pasta', 30),
(6, 'Garlic Breadsticks', 100.00, 'Sides', 80),
(6, 'Caesar Salad', 150.00, 'Salad', 40),
(6, 'Orange Juice', 80.00, 'Drink', 100),
(6, 'Tiramisu', 180.00, 'Dessert', 20),
(7, 'Chicken Sandwich', 180.00, 'Sandwich', 40),
(7, 'Veggie Sandwich', 150.00, 'Sandwich', 50),
(7, 'Club Sandwich', 200.00, 'Sandwich', 30),
(7, 'French Fries', 80.00, 'Sides', 100),
(7, 'Cold Coffee', 90.00, 'Drink', 80),
(7, 'Brownie', 120.00, 'Dessert', 25),
(7, 'Grilled Cheese', 160.00, 'Sandwich', 35);

-- Orders (sample)
INSERT INTO Orders (user_id, total_amount, status, delivery_partner_id) VALUES
(1, 550.00, 'Pending', 1),
(2, 780.00, 'Delivered', 2),
(3, 430.00, 'Out for Delivery', 3),
(4, 600.00, 'Delivered', 4),
(5, 320.00, 'Pending', 5),
(6, 750.00, 'Cancelled', 1),
(7, 900.00, 'Delivered', 2);

-- Order_Items (sample)
INSERT INTO Order_Items (order_id, menu_id, quantity) VALUES
(1, 1, 1),(1, 5,2),(1, 9,1),
(2, 2, 1),(2,6,2),(2,17,1),
(3, 7, 2),(3,10,1),(3,12,1),
(4, 11, 1),(4,12,2),(4,18,1),
(5, 13, 2),(5,15,1),
(6, 3, 2),(6,11,1),(6,20,1),
(7, 2, 1),(7,14,2),(7,17,1);

-- Cart (sample)
INSERT INTO Cart (user_id, menu_id, quantity) VALUES
(1, 2, 1),(1, 5,2),
(2, 10,1),(2, 14,1),
(3, 3,1),(3, 6,2),
(4, 7,1),(4, 12,1),
(5, 18,1),(5, 20,2),
(6, 1,1),(6, 4,1),
(7, 2,1),(7, 5,1);

-- Reviews (sample)
INSERT INTO Reviews (user_id, restaurant_id, rating, comment) VALUES
(1, 1, 5, 'Absolutely loved the pepperoni pizza! Perfect crust.'),
(2, 1, 4, 'Pizza was good but a bit cold.'),
(3, 1, 5, 'Cheese Pizza was delicious.'),
(4, 2, 5, 'Fresh sushi and fast delivery!'),
(5, 2, 4, 'Tuna Roll was tasty but rice slightly overcooked.'),
(6, 2, 3, 'Good sushi but limited variety.'),
(7, 3, 4, 'Cheeseburger was juicy, fries were crispy.');

-- Payments (sample)
INSERT INTO Payments (order_id, amount, method, status) VALUES
(1, 550.00, 'Credit Card', 'Completed'),
(2, 780.00, 'UPI', 'Completed'),
(3, 430.00, 'Wallet', 'Pending'),
(4, 600.00, 'Debit Card', 'Completed'),
(5, 320.00, 'Cash', 'Pending'),
(6, 750.00, 'Credit Card', 'Failed'),
(7, 900.00, 'UPI', 'Completed');

-- Coupons sample
INSERT INTO Coupons (code, discount_percent, max_discount_amount, expiry_date) VALUES
('WELCOME10', 10, 100.00, CURDATE() + INTERVAL 90 DAY),
('BIGSALE25', 25, 300.00, CURDATE() + INTERVAL 30 DAY);



-- FINAL
SHOW TABLES;
SELECT * FROM Users LIMIT 5;
SELECT * FROM Restaurants LIMIT 5;
SELECT * FROM Menu LIMIT 10;
SELECT * FROM Orders LIMIT 10;
SELECT * FROM Order_Items LIMIT 10;
SELECT * FROM Cart LIMIT 10;
SELECT * FROM Payments LIMIT 10;
SELECT * FROM Reviews LIMIT 10;

ALTER TABLE Users ADD COLUMN password VARCHAR(255);
-- Update existing users with hashed passwords
UPDATE Users SET password = SHA2('alice123', 256) WHERE email='alice@example.com';
UPDATE Users SET password = SHA2('bob123', 256) WHERE email='bob@example.com';
UPDATE Users SET password = SHA2('charlie123', 256) WHERE email='charlie@example.com';
UPDATE Users SET password = SHA2('diana123', 256) WHERE email='diana@example.com';
UPDATE Users SET password = SHA2('eve123', 256) WHERE email='eve@example.com';
UPDATE Users SET password = SHA2('frank123', 256) WHERE email='frank@example.com';
UPDATE Users SET password = SHA2('grace123', 256) WHERE email='grace@example.com';

USE FoodOrdering;
-- Function: GetOrderTotal
DELIMITER //
CREATE FUNCTION GetOrderTotal(p_order_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE total DECIMAL(10,2) DEFAULT 0.00;
    SELECT IFNULL(SUM(m.price * oi.quantity), 0.00) INTO total
    FROM Order_Items oi
    JOIN Menu m ON oi.menu_id = m.menu_id
    WHERE oi.order_id = p_order_id;
    RETURN total;
END;
//
DELIMITER ;

-- Function: GetRestaurantAvgRating
DELIMITER //
CREATE FUNCTION GetRestaurantAvgRating(p_restaurant_id INT)
RETURNS DECIMAL(3,2)
DETERMINISTIC
BEGIN
    DECLARE avg_rating DECIMAL(3,2);
    SELECT IFNULL(AVG(rating), 0.00) INTO avg_rating
    FROM Reviews
    WHERE restaurant_id = p_restaurant_id;
    RETURN avg_rating;
END;
//
DELIMITER ;

-- Functions Created
SHOW FUNCTION STATUS WHERE Db = 'FoodOrdering';

SELECT order_id FROM Orders;
SELECT GetOrderTotal(10) AS OrderTotal;

SELECT restaurant_id, name FROM Restaurants;
SELECT GetRestaurantAvgRating(1) AS AverageRating;

SELECT restaurant_id, AVG(rating) AS manual_avg
FROM Reviews
GROUP BY restaurant_id;

-- procedure 
DELIMITER //
CREATE PROCEDURE PlaceOrderFromCart(IN p_user_id INT, IN p_delivery_partner_id INT)
BEGIN
    DECLARE v_order_id INT;

    -- 1. Create an order entry
    INSERT INTO Orders (user_id, total_amount, status, delivery_partner_id)
    VALUES (p_user_id, 0.00, 'Pending', p_delivery_partner_id);

    SET v_order_id = LAST_INSERT_ID();

    -- 2. Copy all cart items into Order_Items
    INSERT INTO Order_Items (order_id, menu_id, quantity)
    SELECT v_order_id, menu_id, quantity FROM Cart WHERE user_id = p_user_id;

    -- 3. Calculate total and update Orders table
    UPDATE Orders 
    SET total_amount = GetOrderTotal(v_order_id)
    WHERE order_id = v_order_id;

    -- 4. Clear the user's cart
    DELETE FROM Cart WHERE user_id = p_user_id;
END;
//
DELIMITER ;

DELIMITER //
CREATE PROCEDURE AddReview(
    IN p_user_id INT,
    IN p_restaurant_id INT,
    IN p_rating INT,
    IN p_comment VARCHAR(500)
)
BEGIN
    IF p_rating < 1 OR p_rating > 5 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Rating must be between 1 and 5';
    END IF;

    INSERT INTO Reviews (user_id, restaurant_id, rating, comment)
    VALUES (p_user_id, p_restaurant_id, p_rating, p_comment);
END;
//
DELIMITER ;

SHOW PROCEDURE STATUS WHERE Db='FoodOrdering';

SELECT * FROM Orders ORDER BY order_id DESC LIMIT 5;
SELECT * FROM Cart WHERE user_id = 1;

CALL PlaceOrderFromCart(1, 1);

SELECT * FROM Orders ORDER BY order_id DESC LIMIT 5;
SELECT * FROM Cart WHERE user_id = 1;
SELECT * FROM Order_Items WHERE order_id = (SELECT MAX(order_id) FROM Orders WHERE user_id=1); 

CALL AddReview(1, 1, 5, 'Excellent food and service!');

SELECT * FROM Reviews WHERE user_id=1 ORDER BY review_date DESC LIMIT 3;

-- triggers 

DELIMITER //
CREATE TRIGGER trg_after_insert_order_item
AFTER INSERT ON Order_Items
FOR EACH ROW
BEGIN
    -- Decrease stock for ordered item
    UPDATE Menu
    SET stock = stock - NEW.quantity
    WHERE menu_id = NEW.menu_id;

    -- If stock goes negative, signal error
    IF (SELECT stock FROM Menu WHERE menu_id = NEW.menu_id) < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Insufficient stock for the menu item';
    END IF;

    -- Recalculate order total
    UPDATE Orders
    SET total_amount = GetOrderTotal(NEW.order_id)
    WHERE order_id = NEW.order_id;
END;
//
DELIMITER ;
DELIMITER //
CREATE TRIGGER trg_after_delete_order_item
AFTER DELETE ON Order_Items
FOR EACH ROW
BEGIN
    UPDATE Menu
    SET stock = stock + OLD.quantity
    WHERE menu_id = OLD.menu_id;

    UPDATE Orders
    SET total_amount = GetOrderTotal(OLD.order_id)
    WHERE order_id = OLD.order_id;
END;
//
DELIMITER ;
DELIMITER //
CREATE TRIGGER trg_orders_update_status_after
AFTER UPDATE ON Orders
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status THEN
        INSERT INTO Order_Status_History (order_id, old_status, new_status, changed_by)
        VALUES (NEW.order_id, OLD.status, NEW.status, 'system');
    END IF;
END;
//
DELIMITER ;

SHOW TRIGGERS;

SELECT menu_id, stock FROM Menu WHERE menu_id = 1;
SELECT total_amount FROM Orders WHERE order_id = 1;

INSERT INTO Order_Items (order_id, menu_id, quantity) VALUES (1, 1, 2);

SELECT menu_id, stock FROM Menu WHERE menu_id = 1;
SELECT total_amount FROM Orders WHERE order_id = 1;

SELECT stock FROM Menu WHERE menu_id = 1;

DELETE FROM Order_Items
WHERE order_item_id = (
    SELECT t.order_item_id 
    FROM (
        SELECT MAX(order_item_id) AS order_item_id 
        FROM Order_Items 
        WHERE menu_id = 1
    ) AS t
);
SELECT stock FROM Menu WHERE menu_id = 1;

SELECT * FROM Order_Status_History WHERE order_id = 1;



UPDATE Orders SET status='Delivered' WHERE order_id=1;

SELECT * FROM Order_Status_History WHERE order_id = 1; 

SELECT * FROM Cart WHERE user_id=1 AND menu_id=1; 
INSERT INTO Cart (user_id, menu_id, quantity) VALUES (1,1,2);
SELECT * FROM Cart WHERE user_id=1 AND menu_id=1; 


SELECT * FROM Users;

UPDATE Orders SET status='Delivered' WHERE order_id=5;
SELECT * FROM Orders;

DELETE FROM Cart WHERE user_id=1 AND menu_id=2;
 


DELIMITER $$

ALTER TABLE Payments
ADD COLUMN coupon_code VARCHAR(50) NULL;

SHOW CREATE PROCEDURE PlaceOrderFromCart;
USE FoodOrdering;

DROP PROCEDURE IF EXISTS PlaceOrderFromCart;
DELIMITER //

CREATE PROCEDURE PlaceOrderFromCart(
    IN p_user_id INT,
    IN p_delivery_partner_id INT
)
BEGIN
    DECLARE v_order_id INT;

    -- 1. Create new order with assigned delivery partner
    INSERT INTO Orders (user_id, total_amount, status, delivery_partner_id)
    VALUES (p_user_id, 0.00, 'Pending', p_delivery_partner_id);

    SET v_order_id = LAST_INSERT_ID();

    -- 2. Copy cart items to Order_Items
    INSERT INTO Order_Items (order_id, menu_id, quantity)
    SELECT v_order_id, menu_id, quantity 
    FROM Cart 
    WHERE user_id = p_user_id;

    -- 3. Update total in Orders
    UPDATE Orders 
    SET total_amount = GetOrderTotal(v_order_id)
    WHERE order_id = v_order_id;

    -- 4. Clear the user's cart
    DELETE FROM Cart WHERE user_id = p_user_id;
END;
//
DELIMITER ;


CALL PlaceOrderFromCart(1, 3);
SELECT order_id, user_id, delivery_partner_id 
FROM Orders 
ORDER BY order_id DESC LIMIT 3;





