select * from pg_database;
\c spider_data;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,  -- 或用 GENERATED AS IDENTITY
    name VARCHAR(50),
    is_active BOOLEAN DEFAULT FALSE,  -- 严格布尔值
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (name, is_active)
VALUES ('张三', TRUE);

SELECT * FROM users;

-- 插入数据并返回指定字段
INSERT INTO users (name, is_active)
VALUES ('周八', TRUE)
RETURNING id, name, create_time;  -- 返回插入后的id、姓名、创建时间

