
-- 表1：用户表（user）
CREATE TABLE `user` (
  `user_id` INT PRIMARY KEY AUTO_INCREMENT,
  `user_name` VARCHAR(50) NOT NULL,
  `age` INT,
  `register_time` DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 表2：订单表（order）
CREATE TABLE `order` (
  `order_id` INT PRIMARY KEY AUTO_INCREMENT,
  `order_no` VARCHAR(30) NOT NULL UNIQUE,
  `user_id` INT NOT NULL,
  `total_amount` DECIMAL(10,2) NOT NULL,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  -- 外键关联：订单表的user_id对应用户表的user_id（多对一关系）
  FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`)
);

-- 表3：商品表（product）
CREATE TABLE `product` (
  `product_id` INT PRIMARY KEY AUTO_INCREMENT,
  `product_name` VARCHAR(100) NOT NULL,
  `price` DECIMAL(10,2) NOT NULL,
  `stock` INT DEFAULT 0
);

-- 表4：订单详情表（order_item）
CREATE TABLE `order_item` (
  `item_id` INT PRIMARY KEY AUTO_INCREMENT,
  `order_id` INT NOT NULL,
  `product_id` INT NOT NULL,
  `quantity` INT NOT NULL DEFAULT 1,
  `item_amount` DECIMAL(10,2) NOT NULL,
  -- 外键关联：订单详情表 ↔ 订单表（多对一）
  FOREIGN KEY (`order_id`) REFERENCES `order` (`order_id`),
  -- 外键关联：订单详情表 ↔ 商品表（多对一）
  FOREIGN KEY (`product_id`) REFERENCES `product` (`product_id`)
);
