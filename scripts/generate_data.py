import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_dataset(output_path="data/raw/ecommerce_sales_data.csv"):
    np.random.seed(42)
    random.seed(42)

    num_customers = 120
    customers = []
    regions = ['North', 'South', 'East', 'West']
    genders = ['Male', 'Female', 'Other']
    segments_true = ['VIP / Loyal', 'Regular', 'New', 'At Risk']

    for i in range(1, num_customers + 1):
        cust_id = f"CUST_{1000 + i}"
        age = int(np.clip(np.random.normal(33, 10), 18, 68))
        gender = np.random.choice(genders, p=[0.48, 0.49, 0.03])
        region = np.random.choice(regions, p=[0.30, 0.28, 0.20, 0.22])
        profile = np.random.choice(segments_true, p=[0.22, 0.43, 0.20, 0.15])
        customers.append({
            'Customer_ID': cust_id,
            'Age': age,
            'Gender': gender,
            'Region': region,
            'Profile': profile
        })

    cust_df = pd.DataFrame(customers)

    products = [
        ('Electronics', 'Wireless Earbuds', 2499),
        ('Electronics', 'Smartwatch', 4999),
        ('Electronics', 'Bluetooth Speaker', 1899),
        ('Electronics', 'USB-C Hub', 1299),
        ('Fashion', 'Running Shoes', 3299),
        ('Fashion', 'Denim Jacket', 2199),
        ('Fashion', 'Cotton T-Shirt', 699),
        ('Fashion', 'Backpack', 1499),
        ('Home & Kitchen', 'Coffee Maker', 3499),
        ('Home & Kitchen', 'Air Fryer', 5499),
        ('Home & Kitchen', 'Insulated Bottle', 599),
        ('Beauty & Care', 'Skincare Combo', 1199),
        ('Beauty & Care', 'Hair Dryer', 1599),
        ('Books & Stationery', 'Data Analytics Handbook', 899),
        ('Books & Stationery', 'Desk Organizer', 499),
    ]

    payment_methods = ['UPI', 'Credit Card', 'Debit Card', 'Cash on Delivery', 'Net Banking']
    order_statuses = ['Delivered', 'Delivered', 'Delivered', 'Delivered', 'Returned', 'Cancelled']
    end_date = datetime(2026, 10, 31)

    rows = []
    order_counter = 5001

    for _, cust in cust_df.iterrows():
        prof = cust['Profile']
        if prof == 'VIP / Loyal':
            n_orders = np.random.randint(4, 8)
            recency_days_max = 45
        elif prof == 'Regular':
            n_orders = np.random.randint(2, 5)
            recency_days_max = 120
        elif prof == 'New':
            n_orders = np.random.randint(1, 3)
            recency_days_max = 35
        else:
            n_orders = np.random.randint(1, 4)
            recency_days_max = 330

        for _ in range(n_orders):
            days_ago = np.random.randint(180, 360) if prof == 'At Risk' else np.random.randint(1, recency_days_max + 1)
            order_date = end_date - timedelta(days=int(days_ago))
            cat, prod_name, base_price = random.choice(products)
            qty = int(np.random.choice([1, 2, 3, 4], p=[0.60, 0.25, 0.10, 0.05]))
            if prof == 'VIP / Loyal' and random.random() < 0.35:
                qty += 1
            discount_pct = int(np.random.choice([0, 5, 10, 15, 20, 25], p=[0.25, 0.20, 0.25, 0.15, 0.10, 0.05]))
            total_amount = round(base_price * qty * (1 - discount_pct / 100.0), 2)
            pay = np.random.choice(payment_methods, p=[0.42, 0.24, 0.16, 0.12, 0.06])
            status = random.choice(order_statuses)
            rating = round(float(np.clip(np.random.normal(4.2 if status == 'Delivered' else 2.5, 0.7), 1.0, 5.0)), 1)

            rows.append({
                'Order_ID': f"ORD_{order_counter}",
                'Order_Date': order_date.strftime('%Y-%m-%d'),
                'Customer_ID': cust['Customer_ID'],
                'Age': cust['Age'],
                'Gender': cust['Gender'],
                'Region': cust['Region'],
                'Category': cat,
                'Product_Name': prod_name,
                'Quantity': qty,
                'Unit_Price': base_price,
                'Discount_Pct': discount_pct,
                'Total_Sales': total_amount,
                'Payment_Method': pay,
                'Order_Status': status,
                'Customer_Rating': rating
            })
            order_counter += 1

    df = pd.DataFrame(rows).sample(frac=1, random_state=42).reset_index(drop=True)
    df.to_csv(output_path, index=False)
    print(f"Dataset saved to {output_path} with shape {df.shape}")

if __name__ == "__main__":
    generate_dataset()
