#!/usr/bin/env python3
"""
Create and populate BigQuery customer_bookings table
with Indian mobile numbers as primary lookup keys for Smart IVR.
"""

from google.cloud import bigquery
from config_loader import (
    BQ_BOOKINGS_TABLE as FULL_TABLE_ID,
    BQ_DATASET as DATASET_ID,
    BQ_TABLE as TABLE_ID,
    GOOGLE_CLOUD_PROJECT as PROJECT_ID,
)

FAKE_INDIAN_BOOKINGS = [
    {
        "mobile_number": "9876543210",
        "booking_id": "TKT-882190",
        "customer_name": "Rahul Sharma",
        "movie_name": "Stree 2: Sarkate Ka Aatang",
        "language": "Hindi",
        "format": "Dolby Atmos 2D",
        "cinema_name": "PVR Director's Cut, Ambience Mall, Gurugram",
        "screen_audi": "Audi 2 (Luxe Recliner)",
        "show_time": "Today at 07:45 PM",
        "seat_numbers": "D12, D13 (Platinum Recliner)",
        "total_tickets": 2,
        "amount_paid": 1450.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "UPI (Google Pay)",
    },
    {
        "mobile_number": "9811122233",
        "booking_id": "TKT-774412",
        "customer_name": "Priya Nair",
        "movie_name": "Kalki 2898 AD",
        "language": "Telugu",
        "format": "IMAX 3D",
        "cinema_name": "INOX Maison, Jio World Drive, BKC Mumbai",
        "screen_audi": "Audi 1 (IMAX Laser)",
        "show_time": "Today at 09:15 PM",
        "seat_numbers": "G8, G9, G10 (Royal Club)",
        "total_tickets": 3,
        "amount_paid": 2400.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "HDFC Regalia Credit Card",
    },
    {
        "mobile_number": "9900112233",
        "booking_id": "TKT-663105",
        "customer_name": "Vikramaditya Rao",
        "movie_name": "Kantara: A Legend Chapter 1",
        "language": "Kannada",
        "format": "Dolby 7.1",
        "cinema_name": "PVR Orion Mall, Rajajinagar, Bengaluru",
        "screen_audi": "Audi 4 (Gold Class)",
        "show_time": "Today at 08:30 PM",
        "seat_numbers": "E5, E6 (Gold Executive)",
        "total_tickets": 2,
        "amount_paid": 1120.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "PhonePe UPI",
    },
    {
        "mobile_number": "9820098200",
        "booking_id": "TKT-551908",
        "customer_name": "Ananya Iyer",
        "movie_name": "Jawan",
        "language": "Hindi",
        "format": "4DX",
        "cinema_name": "Cinepolis DLF Avenue, Saket, New Delhi",
        "screen_audi": "Audi 3 (4DX Motion)",
        "show_time": "Tomorrow at 06:00 PM",
        "seat_numbers": "F11, F12 (Prime Motion)",
        "total_tickets": 2,
        "amount_paid": 1380.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "ICICI Amazon Pay Card",
    },
    {
        "mobile_number": "9711122233",
        "booking_id": "TKT-449012",
        "customer_name": "Siddharth Malhotra",
        "movie_name": "Dune: Part Two",
        "language": "English",
        "format": "IMAX 2D",
        "cinema_name": "PVR Select Citywalk, Saket, New Delhi",
        "screen_audi": "Audi 1 (IMAX)",
        "show_time": "Today at 10:15 PM",
        "seat_numbers": "H14, H15 (Executive)",
        "total_tickets": 2,
        "amount_paid": 1560.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "Paytm UPI",
    },
    {
        "mobile_number": "9123456789",
        "booking_id": "TKT-338719",
        "customer_name": "Meera Deshmukh",
        "movie_name": "3 Idiots (Special Re-Release)",
        "language": "Hindi",
        "format": "Standard 2D",
        "cinema_name": "PVR Phoenix Marketcity, Viman Nagar, Pune",
        "screen_audi": "Audi 6",
        "show_time": "Tomorrow at 04:30 PM",
        "seat_numbers": "C7, C8, C9, C10 (Classic)",
        "total_tickets": 4,
        "amount_paid": 960.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "Digital Wallet",
    },
    {
        "mobile_number": "9988776655",
        "booking_id": "TKT-227610",
        "customer_name": "Arjun Reddy",
        "movie_name": "Salaar: Part 1 – Ceasefire",
        "language": "Telugu",
        "format": "Dolby Atmos",
        "cinema_name": "AMB Cinemas, Gachibowli, Hyderabad",
        "screen_audi": "Screen 1 (Barco Flagship Laser)",
        "show_time": "Today at 09:00 PM",
        "seat_numbers": "K1, K2 (VIP Lounge)",
        "total_tickets": 2,
        "amount_paid": 1200.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "Axis Bank Magnus Card",
    },
    {
        "mobile_number": "9654321098",
        "booking_id": "TKT-119044",
        "customer_name": "Rohan Verma",
        "movie_name": "Leo",
        "language": "Tamil",
        "format": "IMAX 2D",
        "cinema_name": "SPI Palazzo, Nexus Vijaya Mall, Chennai",
        "screen_audi": "IMAX Screen",
        "show_time": "Today at 07:00 PM",
        "seat_numbers": "J6, J7 (Royal)",
        "total_tickets": 2,
        "amount_paid": 990.00,
        "booking_status": "CONFIRMED",
        "cancellation_eligible": True,
        "payment_method": "UPI (PhonePe)",
    },
]


def setup_bq_table() -> None:
    client = bigquery.Client(project=PROJECT_ID)

    schema = [
        bigquery.SchemaField("mobile_number", "STRING", mode="REQUIRED", description="Primary key: 10-digit Indian mobile number"),
        bigquery.SchemaField("booking_id", "STRING", mode="REQUIRED", description="Ticket Booking ID"),
        bigquery.SchemaField("customer_name", "STRING", mode="REQUIRED", description="Full name of customer"),
        bigquery.SchemaField("movie_name", "STRING", mode="REQUIRED", description="Movie title"),
        bigquery.SchemaField("language", "STRING", mode="REQUIRED", description="Movie language (Hindi, Telugu, Kannada, Tamil, English)"),
        bigquery.SchemaField("format", "STRING", mode="REQUIRED", description="Projection format (IMAX 3D, Dolby Atmos, 4DX)"),
        bigquery.SchemaField("cinema_name", "STRING", mode="REQUIRED", description="Cinema hall name and city"),
        bigquery.SchemaField("screen_audi", "STRING", mode="REQUIRED", description="Auditorium / Screen number"),
        bigquery.SchemaField("show_time", "STRING", mode="REQUIRED", description="Scheduled show timing"),
        bigquery.SchemaField("seat_numbers", "STRING", mode="REQUIRED", description="Booked seat numbers and tier"),
        bigquery.SchemaField("total_tickets", "INTEGER", mode="REQUIRED", description="Number of seats booked"),
        bigquery.SchemaField("amount_paid", "FLOAT64", mode="REQUIRED", description="Total amount paid in INR"),
        bigquery.SchemaField("booking_status", "STRING", mode="REQUIRED", description="CONFIRMED or CANCELLED"),
        bigquery.SchemaField("cancellation_eligible", "BOOL", mode="REQUIRED", description="Whether ticket is eligible for cancellation"),
        bigquery.SchemaField("payment_method", "STRING", mode="REQUIRED", description="Original payment mode used"),
    ]

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    print(f"🚀 Creating & populating BigQuery table `{FULL_TABLE_ID}` with {len(FAKE_INDIAN_BOOKINGS)} Indian mobile bookings...")
    job = client.load_table_from_json(FAKE_INDIAN_BOOKINGS, FULL_TABLE_ID, job_config=job_config)
    job.result()

    table = client.get_table(FULL_TABLE_ID)
    print(f"🎉 Successfully loaded {table.num_rows} rows into `{FULL_TABLE_ID}`!")


if __name__ == "__main__":
    setup_bq_table()
