-- OSS Session Events Schema

CREATE TABLE IF NOT EXISTS session_events (
    id SERIAL PRIMARY KEY,
    idempotency_key VARCHAR(64) UNIQUE,  -- For deduplication
    event_type VARCHAR(50) NOT NULL,  -- SESSION_START, SESSION_UPDATE, SESSION_END
    session_id VARCHAR(255) NOT NULL,
    mac_address VARCHAR(17),
    ip_address INET,
    circuit_id TEXT,
    remote_id TEXT,
    relay_id TEXT,
    username TEXT,
    nas_ip INET,
    input_octets BIGINT DEFAULT 0,
    output_octets BIGINT DEFAULT 0,
    input_packets BIGINT DEFAULT 0,
    output_packets BIGINT DEFAULT 0,
    session_time INTEGER DEFAULT 0,
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_session_events_session_id ON session_events(session_id);
CREATE INDEX idx_session_events_event_type ON session_events(event_type);
CREATE INDEX idx_session_events_mac_address ON session_events(mac_address);
CREATE INDEX idx_session_events_ip_address ON session_events(ip_address);
CREATE INDEX idx_session_events_timestamp ON session_events(event_timestamp);

-- Active sessions view
CREATE TABLE IF NOT EXISTS active_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    mac_address VARCHAR(17),
    ip_address INET,
    circuit_id TEXT,
    remote_id TEXT,
    relay_id TEXT,
    username TEXT,
    nas_ip INET,
    start_time TIMESTAMP WITH TIME ZONE,
    last_update TIMESTAMP WITH TIME ZONE,
    input_octets BIGINT DEFAULT 0,
    output_octets BIGINT DEFAULT 0,
    input_packets BIGINT DEFAULT 0,
    output_packets BIGINT DEFAULT 0,
    session_time INTEGER DEFAULT 0
);

CREATE INDEX idx_active_sessions_mac ON active_sessions(mac_address);
CREATE INDEX idx_active_sessions_ip ON active_sessions(ip_address);
