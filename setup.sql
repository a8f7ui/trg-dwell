-- setup.sql - Initialize PostgreSQL database
CREATE EXTENSION IF NOT EXISTS postgis;

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Location events (core data)
CREATE TABLE IF NOT EXISTS location_events (
    id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    address TEXT,
    dwell_time_seconds FLOAT DEFAULT 0,
    distance_m FLOAT DEFAULT 0,
    speed_mps FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(customer_id, device_id, timestamp),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

-- Known locations / geofences
CREATE TABLE IF NOT EXISTS known_locations (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    radius_meters FLOAT DEFAULT 100,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

-- Geofence visits (analytics)
CREATE TABLE IF NOT EXISTS geofence_visits (
    id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    location_id INT NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    dwell_minutes FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY(location_id) REFERENCES known_locations(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_location_events_customer_device ON location_events(customer_id, device_id);
CREATE INDEX idx_location_events_timestamp ON location_events(timestamp);
CREATE INDEX idx_known_locations_customer ON known_locations(customer_id);
CREATE INDEX idx_geofence_visits_customer ON geofence_visits(customer_id, device_id);
