#!/usr/bin/env python3
"""
Test Google Sheets connection and add a sample offer
"""

import gspread
import json
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def test_sheets_connection():
    """Test Google Sheets connection"""
    try:
        # Find credentials file
        possible_paths = [
            'service-account.json',
            'google-service-account.json',
            'credentials.json',
            os.path.expanduser('~/service-account.json')
        ]
        
        credentials_file = None
        for path in possible_paths:
            if os.path.exists(path):
                credentials_file = path
                break
        
        if not credentials_file:
            print("❌ No service account JSON file found")
            print("Expected files:")
            for path in possible_paths:
                print(f"   - {path}")
            return False
        
        print(f"🔑 Using credentials: {credentials_file}")
        
        # Load and check credentials
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
            service_email = creds_data.get('client_email')
            print(f"📧 Service account email: {service_email}")
        
        credentials = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        
        print("✅ Google Sheets client authorized successfully")
        
        # Try to open the sheet
        try:
            sheet = gc.open("Restaurant_Offers_Pending").sheet1
            print("✅ Sheet 'Restaurant_Offers_Pending' found")
        except gspread.SpreadsheetNotFound:
            print("❌ Sheet 'Restaurant_Offers_Pending' not found")
            print("Please:")
            print("1. Create a Google Sheet named exactly 'Restaurant_Offers_Pending'")
            print(f"2. Share it with: {service_email}")
            print("3. Give 'Editor' permissions")
            return False
        
        # Check if sheet has headers
        try:
            headers = sheet.row_values(1)
            if not headers:
                print("📝 Sheet is empty, adding headers...")
                headers = [
                    'timestamp', 'restaurant_id', 'restaurant_name', 'offer_type', 
                    'title', 'description', 'summary', 'valid_days_of_week',
                    'valid_start_time', 'valid_end_time', 'start_date', 'end_date',
                    'unique_usage_per_user', 'surprise_bag_data', 'status'
                ]
                sheet.append_row(headers)
                print("✅ Headers added to sheet")
            else:
                print(f"✅ Sheet has headers: {headers[:5]}...")
        except Exception as e:
            print(f"❌ Error checking/adding headers: {e}")
            return False
        
        # Test adding a sample offer
        print("🧪 Testing sample offer addition...")
        sample_offer = [
            datetime.now().isoformat(),
            1,  # restaurant_id
            "Test Restaurant",
            "Percent Discount",
            "Test 20% Off Pizza",
            "Get 20% off all pizzas",
            "20% off pizzas",
            "",  # valid_days_of_week
            "",  # valid_start_time
            "",  # valid_end_time
            "2025-09-24",  # start_date
            "",  # end_date
            False,  # unique_usage_per_user
            "",  # surprise_bag_data
            "pending"  # status
        ]
        
        sheet.append_row(sample_offer)
        print("✅ Sample offer added successfully!")
        
        # Read it back
        records = sheet.get_all_records()
        pending_count = len([r for r in records if r.get('status') == 'pending'])
        print(f"📊 Sheet now has {len(records)} total records, {pending_count} pending")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Google Sheets Connection")
    print("=" * 50)
    success = test_sheets_connection()
    
    if success:
        print("\n🎉 Google Sheets integration is working!")
        print("Now test your Streamlit app to see if offers get added.")
    else:
        print("\n❌ Please fix the issues above before proceeding.")