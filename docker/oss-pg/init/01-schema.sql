CREATE TABLE session_events (
    bng_id           TEXT        NOT NULL,
    bng_instance_id  UUID        NOT NULL,
    seq              BIGINT      NOT NULL,

    event_type       TEXT        NOT NULL,  -- SESSION_START | SESSION_UPDATE | SESSION_STOP | POLICY_APPLY
    ts               TIMESTAMPTZ NOT NULL,

    session_id       UUID        NOT NULL,

    -- attachment identity
    nas_ip           INET        NOT NULL,
    circuit_id       TEXT        NOT NULL,
    remote_id        TEXT        NOT NULL,

    -- timestamps
    session_start    TIMESTAMPTZ NOT NULL,
    session_end       TIMESTAMPTZ, -- when event_type = SESSION_STOP
    session_last_update  TIMESTAMPTZ NOT NULL,

    -- subscriber identity
    mac_address      MACADDR,
    ip_address       INET,
    username         TEXT,

    -- absolute counters since SESSION_START
    input_octets     BIGINT, -- Relative to subscriber
    output_octets    BIGINT, -- Relative to subscriber
    input_packets    BIGINT,
    output_packets   BIGINT,

    raw_data         JSONB,

    status           TEXT,       -- ACTIVE | IDLE | EXPIRED | PENDING
    auth_state        TEXT,       -- AUTH_PENDING | AUTHORIZED | REJECTED

    -- Terminate cause
    terminate_cause TEXT, -- when event_type = SESSION_STOP

    PRIMARY KEY (bng_id, bng_instance_id, seq)
);

CREATE TABLE sessions_active (
    session_id       UUID        PRIMARY KEY,

    bng_id           TEXT        NOT NULL,
    bng_instance_id  UUID        NOT NULL,

    nas_ip           INET        NOT NULL,
    circuit_id       TEXT        NOT NULL,
    remote_id        TEXT        NOT NULL,

    mac_address      MACADDR     NOT NULL,
    ip_address       INET,

    username         TEXT,

    start_time       TIMESTAMPTZ NOT NULL,
    last_update      TIMESTAMPTZ NOT NULL,

    input_octets     BIGINT      NOT NULL DEFAULT 0,
    output_octets    BIGINT      NOT NULL DEFAULT 0,
    input_packets    BIGINT      NOT NULL DEFAULT 0,
    output_packets   BIGINT      NOT NULL DEFAULT 0,

    status           TEXT        NOT NULL DEFAULT 'ACTIVE',
    auth_state       TEXT        NOT NULL DEFAULT 'PENDING_AUTH'
);

CREATE TABLE sessions_history (
    LIKE sessions_active INCLUDING DEFAULTS INCLUDING CONSTRAINTS,

    session_end       TIMESTAMPTZ NOT NULL,
    terminate_cause   TEXT,
    terminate_source  TEXT
);

CREATE INDEX idx_sessions_history_start_time ON sessions_history (start_time);
CREATE INDEX idx_sessions_history_session_end ON sessions_history (session_end);

CREATE INDEX idx_sessions_history_range
ON sessions_history
USING GIST (tstzrange(start_time, session_end, '[)'));

CREATE UNIQUE INDEX uniq_active_attachment
ON sessions_active (nas_ip, circuit_id, remote_id);

CREATE TABLE access_routers (
    router_name        TEXT        PRIMARY KEY,
    giaddr             INET        NOT NULL,
    bng_id             TEXT,                          -- nullable until assigned
    total_interfaces   INTEGER     NOT NULL DEFAULT 5,
    is_alive           BOOLEAN     NOT NULL DEFAULT false,
    last_seen          TIMESTAMPTZ,                   -- nullable (never seen yet)
    last_ping          TIMESTAMPTZ,                   -- nullable
    active_subscribers INTEGER     NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- BNG Registry
CREATE TABLE bng_registry (
    bng_id             TEXT        PRIMARY KEY,
    bng_instance_id    UUID        NOT NULL,
    first_seen         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen          TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_alive           BOOLEAN     DEFAULT true,
    
    -- Latest health status
    mem_usage            FLOAT,
    mem_max               FLOAT,
    cpu_usage            FLOAT
);

CREATE UNIQUE INDEX uniq_bng_instance ON bng_registry (bng_id, bng_instance_id);

CREATE TABLE bng_health_events (
    bng_id             TEXT        NOT NULL,
    bng_instance_id    UUID        NOT NULL,
    ts                 TIMESTAMPTZ NOT NULL,
    mem_usage            FLOAT NOT NULL,
    mem_max               FLOAT NOT NULL,
    cpu_usage            FLOAT NOT NULL,

    PRIMARY KEY (bng_id, bng_instance_id, ts)
);

CREATE INDEX idx_bng_health_events_ts ON bng_health_events (ts);
