import requests
from datetime import datetime
import time
import pandas as pd
import os
import json

def format_date(date_str):
    """Convert DD/MM/YYYY to YYYY-MM-DD format"""
    try:
        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
        return date_obj.strftime('%Y-%m-%d')
    except:
        return None

def check_student_status(name, dob, birthplace, auth_token):
    """Check student status via API"""
    url = "https://api-emis.kemenag.go.id/v1/students/pontrens/student-ppdb-search"
    
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    
    params = {
        "q": name,
        "fdob": dob,
        "fbirthplace": birthplace
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"\nResponse for {name}:")
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}\n")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            if results:  # If there are any results
                for student in results:
                    # Check direct status
                    if student.get('status_name') == 'active_without_rombel':
                        return True
                    
                    # Check status array if exists
                    status_array = student.get('status', [])
                    for status in status_array:
                        if status.get('status_name') == 'active_without_rombel':
                            return True
            
            return False
        else:
            print(f"Error for {name}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception for {name}: {str(e)}")
        return None

def main():
    # Get CSV file location from user
    file_path = input("Masukkan lokasi file CSV: ").strip('"')
    
    if not os.path.exists(file_path):
        print(f"Error: File tidak ditemukan di lokasi {file_path}")
        return
    
    try:
        # Read CSV file
        df = pd.read_csv(file_path)
        print(f"Berhasil membaca file. Total {len(df)} data ditemukan.")
        
        auth_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FjY291bnQtc2VydmljZS1uZ2lueC92MS9hY2NvdW50cy9sb2dpbiIsImlhdCI6MTczNDQ0NDIyOSwiZXhwIjoxNzM0NDYwNDI5LCJuYmYiOjE3MzQ0NDQyMjksImp0aSI6IlJlN0ZMSUY0bzRiS1N1MkciLCJzdWIiOjMxNTI2MywicHJ2IjoiMjNiZDVjODk0OWY2MDBhZGIzOWU3MDFjNDAwODcyZGI3YTU5NzZmNyIsInJvbGVfaWQiOjQyLCJyb2xlX2xldmVsX2lkIjo2LCJyb2xlX3Njb3BlX2lkIjo0OSwiaWRlbnRpZmlhYmxlX2ZpZWxkIjoiaW5zdGl0dXRpb25faWQiLCJpZGVudGlmaWFibGVfaWQiOjM4MDY4MSwicmVhbF9pcCI6IjExMi4yMTUuMTcyLjI0MCJ9.Ec1Gs04YmEk6BAH38WevRmOiCa96cIRrBQOVSBAliXk"
        
        results = []
        
        for index, row in df.iterrows():
            name = row['Nama Lengkap']
            dob = format_date(row['Tanggal Lahir'])
            birthplace = row['Tempat Lahir']
            
            print(f"\nChecking student {index + 1}/{len(df)}: {name}")
            print(f"DOB: {dob}")
            print(f"Birthplace: {birthplace}")
            
            time.sleep(1)
            
            status = check_student_status(name, dob, birthplace, auth_token)
            
            results.append({
                'Nama': name,
                'Tanggal Lahir': row['Tanggal Lahir'],
                'Tempat Lahir': birthplace,
                'Active Without Rombel': 'Ya' if status else 'Tidak' if status is not None else 'Error',
                'Catatan': 'Ditemukan di sistem' if status else 'Tidak ditemukan' if status is not None else 'Error saat pengecekan'
            })
            
            # Save progress
            output_path = os.path.join(os.path.dirname(file_path), 'student_status_results.csv')
            results_df = pd.DataFrame(results)
            results_df.to_csv(output_path, index=False)
            print(f"Progress saved to: {output_path}")
        
        print("\nProses selesai. Hasil telah disimpan di file 'student_status_results.csv'")
        
    except Exception as e:
        print(f"Error membaca file CSV: {str(e)}")

if __name__ == "__main__":
    main()