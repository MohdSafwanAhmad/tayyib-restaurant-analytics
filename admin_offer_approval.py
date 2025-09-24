"""
Simple admin script to approve offers from Google Sheets
This uses your existing database connection setup
"""

import gspread
import json
from google.oauth2.service_account import Credentials
from utils.db import _connect
from datetime import datetime
import psycopg2.extras
from utils.google_sheets import get_google_sheets_client

# Google Sheets configuration
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_offer_type_id(cursor, offer_type_name):
    """Get offer type ID from name"""
    cursor.execute("SELECT id FROM offer_types WHERE en = %s", (offer_type_name,))
    result = cursor.fetchone()
    return result['id'] if result else None

def insert_offer_to_db(cursor, offer_data):
    """Insert offer into database"""
    
    # Get offer type ID
    offer_type_id = get_offer_type_id(cursor, offer_data['offer_type'])
    if not offer_type_id:
        print(f"❌ Error: Offer type '{offer_data['offer_type']}' not found")
        return None
    
    # Prepare about data
    about_data = {
        'en': {
            'title': offer_data['title'],
            'description': offer_data['description'],
            'summary': offer_data['summary']
        }
    }
    
    # Parse additional fields
    valid_days = json.loads(offer_data['valid_days_of_week']) if offer_data['valid_days_of_week'] else None
    start_time = offer_data['valid_start_time'] if offer_data['valid_start_time'] else None
    end_time = offer_data['valid_end_time'] if offer_data['valid_end_time'] else None
    end_date = offer_data['end_date'] if offer_data['end_date'] else None
    
    # Insert main offer
    insert_offer_query = """
    INSERT INTO offers (restaurant_id, about, offer_type, valid_days_of_week, 
                       valid_start_time, valid_end_time, start_date, end_date, 
                       unique_usage_per_user)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    """
    
    cursor.execute(insert_offer_query, (
        offer_data['restaurant_id'],
        json.dumps(about_data),
        offer_type_id,
        valid_days,
        start_time,
        end_time,
        offer_data['start_date'],
        end_date,
        offer_data['unique_usage_per_user']
    ))
    
    offer_id = cursor.fetchone()['id']
    
    # Insert surprise bag data if applicable
    if offer_data['surprise_bag_data']:
        surprise_bag_data = json.loads(offer_data['surprise_bag_data'])
        
        insert_sb_query = """
        INSERT INTO surprise_bags (offer_id, price, estimated_value, daily_quantity, 
                                 current_daily_quantity, total_quantity)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        
        daily_qty = surprise_bag_data.get('daily_quantity')
        
        cursor.execute(insert_sb_query, (
            offer_id,
            surprise_bag_data['price'],
            surprise_bag_data['estimated_value'],
            daily_qty,
            daily_qty,  # current_daily_quantity = daily_quantity initially
            surprise_bag_data.get('total_quantity')
        ))
    
    return offer_id

def list_pending_offers():
    """List all pending offers for review"""
    try:
        gc = get_google_sheets_client()
        sheet = gc.open("Restaurant_Offers_Pending").sheet1
        records = sheet.get_all_records()
        
        pending_offers = [r for r in records if r['status'] == 'pending']
        
        if not pending_offers:
            print("✅ No pending offers found.")
            return
        
        print(f"\n📋 Found {len(pending_offers)} pending offers:\n")
        print("-" * 100)
        
        for i, offer in enumerate(pending_offers, 1):
            print(f"{i:2d}. {offer['title'][:40]:<40} | {offer['restaurant_name'][:20]:<20} | {offer['offer_type']}")
            print(f"     Description: {offer['description'][:60]}...")
            print(f"     Submitted: {offer['timestamp'][:16]}")
            if offer['surprise_bag_data']:
                sb_data = json.loads(offer['surprise_bag_data'])
                print(f"     Surprise Bag: ${sb_data['price']} (Est. Value: ${sb_data['estimated_value']})")
            print("-" * 100)
            
    except Exception as e:
        print(f"❌ Error listing offers: {e}")

def approve_offers():
    """Main function to approve offers"""
    try:
        print("🔍 Connecting to Google Sheets...")
        gc = get_google_sheets_client()
        sheet = gc.open("Restaurant_Offers_Pending").sheet1
        records = sheet.get_all_records()
        
        pending_offers = [r for r in records if r['status'] == 'pending']
        if not pending_offers:
            print("✅ No pending offers to approve.")
            return
        
        print(f"📋 Found {len(pending_offers)} pending offers to approve...")
        
        # Confirm before proceeding
        response = input(f"\nDo you want to approve all {len(pending_offers)} offers? (y/N): ")
        if response.lower() != 'y':
            print("❌ Approval cancelled.")
            return
        
        print("🔗 Connecting to database...")
        conn = _connect()
        
        approved_count = 0
        rows_to_delete = []
        
        # Process each pending offer
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            for i, record in enumerate(records, start=2):  # start=2 because row 1 is headers
                if record['status'] == 'pending':
                    try:
                        print(f"⏳ Processing: {record['title']} for {record['restaurant_name']}")
                        
                        # Insert into database
                        offer_id = insert_offer_to_db(cursor, record)
                        
                        if offer_id:
                            print(f"✅ Created offer ID: {offer_id}")
                            rows_to_delete.append(i)
                            approved_count += 1
                        else:
                            print(f"❌ Failed to create offer: {record['title']}")
                            
                    except Exception as e:
                        print(f"❌ Error processing {record['title']}: {e}")
            
            # Commit all changes
            conn.commit()
        
        print(f"💾 Database changes committed.")
        
        # Delete approved rows from Google Sheets (in reverse order)
        print("🧹 Cleaning up Google Sheets...")
        for row_num in reversed(rows_to_delete):
            sheet.delete_rows(row_num)
            
        print(f"\n🎉 Successfully approved {approved_count} offers!")
        print(f"📝 {approved_count} rows removed from Google Sheets.")
        
    except Exception as e:
        print(f"❌ Error in approval process: {e}")
        if 'conn' in locals():
            print("🔄 Rolling back database changes...")
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import sys
    
    print("🍽️  Restaurant Offers Approval System")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'list':
            list_pending_offers()
        elif sys.argv[1] == 'approve':
            approve_offers()
        else:
            print("Usage: python admin_approve_offers.py [list|approve]")
    else:
        # Interactive mode
        print("1. List pending offers")
        print("2. Approve all pending offers")
        choice = input("\nSelect option (1/2): ")
        
        if choice == '1':
            list_pending_offers()
        elif choice == '2':
            approve_offers()
        else:
            print("Invalid option.")