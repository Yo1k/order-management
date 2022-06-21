CREATE TABLE IF NOT EXISTS orders (
    sec_no integer NOT NULL,
    order_no integer PRIMARY KEY,
    cost_usd numeric NOT NULL,
    cost_rub numeric,
    deliv_date date NOT NULL
);

CREATE TABLE IF NOT EXISTS missed_deadlines (
    order_no integer PRIMARY KEY,
    notif_date timestamp with time zone NOT NULL, -- date when the notification message was sent
    FOREIGN KEY (order_no) REFERENCES orders ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tg_information (
    user_chat_id integer PRIMARY KEY
);
