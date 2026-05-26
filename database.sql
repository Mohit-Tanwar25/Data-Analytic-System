
CREATE DATABASE analysis;

USE analysis;


CREATE TABLE sales_data (

    order_id VARCHAR(100),

    order_date DATE,

    ship_date DATE,

    category VARCHAR(100),

    product_name VARCHAR(255),

    region VARCHAR(100),

    sales FLOAT,

    profit FLOAT,

    quantity INT,

    discount FLOAT,

    shipping_cost FLOAT

);


SELECT * FROM sales_data;

DELETE FROM sales_data;

DROP TABLE sales_data;

TRUNCATE TABLE sales_data;
