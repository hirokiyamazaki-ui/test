-- Drop the table if it exists to start fresh (useful for development)
DROP TABLE IF EXISTS receipts;

-- Create the receipts table
CREATE TABLE receipts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  store_name TEXT,
  transaction_date TEXT,
  total_amount INTEGER,
  saved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
