# app.py - Complete Flask backend with all endpoints
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from geopy.geocoders import Nominatim
import numpy as np

app = Flask(__name__)
CORS(app)

# Database connection config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'location_marketing'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

def get_db():
    """Get PostgreSQL connection"""
    import time
    last=None
    for _ in range(5):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except Exception as e:
            last=e; time.sleep(2)
    raise last

def reverse_geocode(lat, lon, timeout=10):
    """Reverse geocode lat/lon to street address"""
    try:
        geocoder = Nominatim(user_agent="location_marketing_mvp")
        location = geocoder.reverse(f"{lat}, {lon}", timeout=timeout)
        return location.address if location else f"{lat}, {lon}"
    except Exception as e:
        print(f"Geocoding error for ({lat}, {lon}): {e}")
        return f"{lat}, {lon}"

def calculate_metrics(df):
    """Calculate dwell time, distance, speed from trajectory"""
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(['device_id', 'timestamp'])
    
    # Distance (Haversine formula in meters)
    df['lat_rad'] = np.radians(df['latitude'])
    df['lon_rad'] = np.radians(df['longitude'])
    df['lat_rad_shift'] = df.groupby('device_id')['lat_rad'].shift(1)
    df['lon_rad_shift'] = df.groupby('device_id')['lon_rad'].shift(1)
    
    dlat = df['lat_rad'] - df['lat_rad_shift']
    dlon = df['lon_rad'] - df['lon_rad_shift']
    a = np.sin(dlat/2)**2 + np.cos(df['lat_rad_shift']) * np.cos(df['lat_rad']) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    df['distance_m'] = 6371000 * c
    df['distance_m'] = df['distance_m'].fillna(0)
    
    # Time delta
    df['time_delta'] = df.groupby('device_id')['timestamp'].diff().dt.total_seconds()
    df['time_delta'] = df['time_delta'].fillna(0)
    
    # Speed
    df['speed_mps'] = np.where(df['time_delta'] > 0, df['distance_m'] / df['time_delta'], 0)
    df['speed_mps'] = df['speed_mps'].clip(lower=0, upper=100)
    
    # Dwell time (stationary = speed < 1 m/s)
    df['is_stationary'] = df['speed_mps'] < 1
    df['dwell_group'] = (df.groupby('device_id')['is_stationary'] != df.groupby('device_id')['is_stationary'].shift()).cumsum()
    dwell=df.groupby(['device_id','dwell_group'])['time_delta'].transform('sum')
    df['dwell_time_seconds']=dwell.where(df['is_stationary'],0)
    df['dwell_time_seconds'] = df['dwell_time_seconds'].fillna(0)
    
    return df[['device_id', 'timestamp', 'latitude', 'longitude', 'dwell_time_seconds', 'distance_m', 'speed_mps']]

@app.route('/upload', methods=['POST'])
def upload_data():
    """Ingest CSV/JSON location data"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    customer_id = request.form.get('customer_id', 'default')
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith('.json'):
            df = pd.read_json(file)
        else:
            return jsonify({'error': 'Unsupported file format. Use CSV or JSON'}), 400
        
        required_cols = ['device_id', 'timestamp', 'latitude', 'longitude']
        if not all(col in df.columns for col in required_cols):
            return jsonify({'error': f'Missing required columns: {required_cols}'}), 400
        
        df = calculate_metrics(df)
        
        # Reverse geocode (sample to avoid rate limits)
        df['address'] = df.apply(
            lambda row: reverse_geocode(row['latitude'], row['longitude']) 
            if np.random.random() < 0.1 else f"{row['latitude']:.4f}, {row['longitude']:.4f}",
            axis=1
        )
        
        conn = get_db()
        cur = conn.cursor()
        
        for _, row in df.iterrows():
            cur.execute("""
                INSERT INTO location_events (customer_id, device_id, timestamp, latitude, longitude, address, dwell_time_seconds, distance_m, speed_mps)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (customer_id, device_id, timestamp) DO NOTHING
            """, (customer_id, row['device_id'], row['timestamp'], row['latitude'], row['longitude'], row['address'], row['dwell_time_seconds'], row['distance_m'], row['speed_mps']))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'status': 'success', 'rows_imported': len(df)}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<customer_id>', methods=['GET'])
def get_locations(customer_id):
    """Get location events for a device within date range"""
    device_id = request.args.get('device_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM location_events WHERE customer_id = %s"
        params = [customer_id]
        
        if device_id:
            query += " AND device_id = %s"
            params.append(device_id)
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY device_id, timestamp"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([dict(row) for row in rows]), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/known-locations/<customer_id>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_known_locations(customer_id):
    """CRUD for geofences"""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if request.method == 'GET':
            cur.execute("SELECT * FROM known_locations WHERE customer_id = %s ORDER BY name", (customer_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify([dict(row) for row in rows]), 200
        
        elif request.method == 'POST':
            data = request.json
            cur.execute("""
                INSERT INTO known_locations (customer_id, name, latitude, longitude, radius_meters, category)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (customer_id, data['name'], data['latitude'], data['longitude'], data.get('radius_meters', 100), data.get('category', 'Unknown')))
            location_id = cur.fetchone()['id']
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'id': location_id, 'status': 'created'}), 201
        
        elif request.method == 'PUT':
            data = request.json
            cur.execute("""
                UPDATE known_locations 
                SET name = %s, latitude = %s, longitude = %s, radius_meters = %s, category = %s
                WHERE customer_id = %s AND id = %s
            """, (data['name'], data['latitude'], data['longitude'], data.get('radius_meters', 100), data.get('category', 'Unknown'), customer_id, data['id']))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'status': 'updated'}), 200
        
        elif request.method == 'DELETE':
            location_id = request.args.get('location_id')
            cur.execute("DELETE FROM known_locations WHERE customer_id = %s AND id = %s", (customer_id, location_id))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'status': 'deleted'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analytics/<customer_id>', methods=['GET'])
def get_analytics(customer_id):
    """Behavioral insights"""
    device_id = request.args.get('device_id')
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        dwell_query = """
            SELECT address, COUNT(*) as visit_count, 
                   AVG(dwell_time_seconds) as avg_dwell_seconds
            FROM location_events
            WHERE customer_id = %s AND dwell_time_seconds > 30
        """
        params = [customer_id]
        
        if device_id:
            dwell_query += " AND device_id = %s"
            params.append(device_id)
        
        dwell_query += " GROUP BY address ORDER BY visit_count DESC LIMIT 20"
        cur.execute(dwell_query, params)
        dwell_data = [dict(row) for row in cur.fetchall()]
        
        temporal_query = """
            SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as event_count
            FROM location_events
            WHERE customer_id = %s
        """
        params = [customer_id]
        
        if device_id:
            temporal_query += " AND device_id = %s"
            params.append(device_id)
        
        temporal_query += " GROUP BY hour ORDER BY hour"
        cur.execute(temporal_query, params)
        temporal_data = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'dwell_by_location': dwell_data,
            'temporal_patterns': temporal_data
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/devices/<customer_id>', methods=['GET'])
def get_devices(customer_id):
    """List unique devices"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT device_id, COUNT(*) as event_count, MIN(timestamp) as first_seen, MAX(timestamp) as last_seen
            FROM location_events
            WHERE customer_id = %s
            GROUP BY device_id
            ORDER BY last_seen DESC
        """, (customer_id,))
        
        devices = [{'device_id': row[0], 'event_count': row[1], 'first_seen': row[2].isoformat(), 'last_seen': row[3].isoformat()} for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return jsonify(devices), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG','false').lower()=='true', host='0.0.0.0', port=5000)
