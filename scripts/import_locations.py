#!/usr/bin/env python3
"""
Import DataForSEO locations from CSV into SQLite database.

This script:
1. Downloads the latest locations CSV from DataForSEO CDN
2. Filters to English-speaking and business English countries
3. Imports only cities/regions (excludes postal codes)
4. Creates indexed SQLite database for fast lookups

Run this script locally to build/update the locations database:
    python scripts/import_locations.py

Then commit the resulting app/data/locations.db file to Git.
"""

import csv
import os
import sqlite3
import sys
from io import StringIO

import requests

# Target countries: English-speaking + countries with popular business English
TARGET_COUNTRIES = [
    'US',  # United States
    'GB',  # United Kingdom
    'CA',  # Canada
    'AU',  # Australia
    'NZ',  # New Zealand
    'IE',  # Ireland
    'IN',  # India
    'PH',  # Philippines
    'SG',  # Singapore
    'AE',  # United Arab Emirates
    'IL',  # Israel
    'ZA',  # South Africa
    'NG',  # Nigeria
    'MY',  # Malaysia
    'PK',  # Pakistan
    'KE',  # Kenya
    'GH',  # Ghana
]

# Location types to include (exclude postal codes which are too granular)
ALLOWED_TYPES = ['City', 'Region', 'Country', 'District']

# DataForSEO CSV URL (updated periodically)
CSV_URL = "https://cdn.dataforseo.com/v3/locations/locations_kwrd_2025_08_05.csv"

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'data', 'locations.db')


def download_csv():
    """Download locations CSV from DataForSEO CDN."""
    print(f"Downloading locations CSV from {CSV_URL}...")
    response = requests.get(CSV_URL, timeout=60)
    response.raise_for_status()
    print(f"Downloaded {len(response.content) / 1024 / 1024:.1f} MB")
    return response.text


def create_database():
    """Create SQLite database with proper schema and indexes."""
    # Remove old database if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE locations (
            location_code INTEGER PRIMARY KEY,
            location_name TEXT NOT NULL,
            country_iso_code TEXT NOT NULL,
            location_type TEXT NOT NULL
        )
    """)
    
    # Create indexes for fast autocomplete searches
    cursor.execute("CREATE INDEX idx_name ON locations(location_name COLLATE NOCASE)")
    cursor.execute("CREATE INDEX idx_country ON locations(country_iso_code)")
    cursor.execute("CREATE INDEX idx_type ON locations(location_type)")
    
    conn.commit()
    return conn


def import_locations(conn, csv_text):
    """Parse CSV and import filtered locations."""
    cursor = conn.cursor()
    
    reader = csv.DictReader(StringIO(csv_text))
    
    total_count = 0
    imported_count = 0
    skipped_postal = 0
    skipped_country = 0
    
    for row in reader:
        total_count += 1
        
        country = row['country_iso_code']
        location_type = row['location_type']
        
        # Skip countries we don't target
        if country not in TARGET_COUNTRIES:
            skipped_country += 1
            continue
        
        # Skip postal codes and other overly granular types
        if location_type not in ALLOWED_TYPES:
            skipped_postal += 1
            continue
        
        # Import this location
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO locations VALUES (?, ?, ?, ?)",
                (
                    int(row['location_code']),
                    row['location_name'],
                    country,
                    location_type
                )
            )
            imported_count += 1
        except (ValueError, KeyError) as e:
            print(f"Warning: Skipped invalid row: {e}")
            continue
    
    conn.commit()
    
    print(f"\nImport Statistics:")
    print(f"  Total locations in CSV: {total_count:,}")
    print(f"  Skipped (wrong country): {skipped_country:,}")
    print(f"  Skipped (postal codes/etc): {skipped_postal:,}")
    print(f"  Imported successfully: {imported_count:,}")
    
    return imported_count


def verify_database(conn):
    """Verify database contents and show sample data."""
    cursor = conn.cursor()
    
    # Count by country
    print("\nLocations by Country:")
    cursor.execute("""
        SELECT country_iso_code, COUNT(*) as count
        FROM locations
        GROUP BY country_iso_code
        ORDER BY count DESC
    """)
    for country, count in cursor.fetchall():
        print(f"  {country}: {count:,}")
    
    # Count by type
    print("\nLocations by Type:")
    cursor.execute("""
        SELECT location_type, COUNT(*) as count
        FROM locations
        GROUP BY location_type
        ORDER BY count DESC
    """)
    for loc_type, count in cursor.fetchall():
        print(f"  {loc_type}: {count:,}")
    
    # Sample searches
    print("\nSample Searches:")
    for query in ['auckland', 'london', 'new york', 'mumbai']:
        cursor.execute(
            "SELECT location_name FROM locations WHERE location_name LIKE ? LIMIT 3",
            (f"%{query}%",)
        )
        results = [row[0] for row in cursor.fetchall()]
        print(f"  '{query}': {', '.join(results) if results else 'No results'}")
    
    # Database size
    db_size = os.path.getsize(DB_PATH) / 1024 / 1024
    print(f"\nDatabase Size: {db_size:.2f} MB")


def main():
    """Main import process."""
    print("=" * 60)
    print("DataForSEO Locations Import Script")
    print("=" * 60)
    
    try:
        # Download CSV
        csv_text = download_csv()
        
        # Create database
        print("\nCreating database...")
        conn = create_database()
        
        # Import locations
        print("\nImporting locations...")
        count = import_locations(conn, csv_text)
        
        if count == 0:
            print("\nERROR: No locations imported!")
            sys.exit(1)
        
        # Verify
        verify_database(conn)
        
        conn.close()
        
        print("\n" + "=" * 60)
        print(f"SUCCESS! Database created at: {DB_PATH}")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Test the database: python -c \"import sqlite3; print(sqlite3.connect('app/data/locations.db').execute('SELECT COUNT(*) FROM locations').fetchone())\"")
        print("  2. Commit to Git: git add app/data/locations.db")
        print("  3. Push to deploy: git commit -m 'Add locations database' && git push")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
