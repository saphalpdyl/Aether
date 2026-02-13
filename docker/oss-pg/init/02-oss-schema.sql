-- Plans define the service template: speeds, price, and the RADIUS policy
-- that gets pushed to the BNG when a subscriber connects.
CREATE TABLE plans (
    id               SERIAL      PRIMARY KEY,
    name             TEXT        NOT NULL UNIQUE,
    download_speed   INTEGER     NOT NULL,  -- kbps
    upload_speed     INTEGER     NOT NULL,  -- kbps
    price            NUMERIC(10,2) NOT NULL,
    is_active        BOOLEAN     NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Customers are the business entities (people or companies) that subscribe to services.
CREATE TABLE customers (
    id               SERIAL      PRIMARY KEY,
    name             TEXT        NOT NULL,
    email            TEXT,
    phone            TEXT,
    street           TEXT,
    city             TEXT,
    zip_code         TEXT,
    state            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Services bind a customer + plan to a physical network attachment point (circuit_id/remote_id).
-- When a DHCP session arrives, the system looks up the service by circuit_id/remote_id
-- to determine which plan (and therefore which bandwidth policy) to apply.
CREATE TABLE services (
    id               SERIAL      PRIMARY KEY,
    customer_id      INTEGER     NOT NULL REFERENCES customers(id),
    plan_id          INTEGER     NOT NULL REFERENCES plans(id),

    -- Network binding: identifies the subscriber's physical attachment on the BNG
    circuit_id       TEXT        NOT NULL,
    remote_id        TEXT        NOT NULL,

    status           TEXT        NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | SUSPENDED | TERMINATED
    billing_start    DATE        NOT NULL DEFAULT CURRENT_DATE,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (circuit_id, remote_id)
);

CREATE INDEX idx_services_customer_id ON services (customer_id);
CREATE INDEX idx_services_plan_id ON services (plan_id);
CREATE INDEX idx_services_status ON services (status);

-- Seed access routers
INSERT INTO access_routers (router_name, giaddr, bng_id) VALUES
    ('srl-access',  '10.0.0.2', 'bng-01'),
    ('srl2-access', '10.0.0.3', 'bng-01');
