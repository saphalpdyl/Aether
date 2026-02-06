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

    PRIMARY KEY (bng_id, bng_instance_id, seq)
);

CREATE TABLE active_sessions (
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
    output_packets   BIGINT      NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX uniq_active_attachment
ON active_sessions (nas_ip, circuit_id, remote_id);
