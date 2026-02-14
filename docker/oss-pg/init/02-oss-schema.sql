-- Plans define the service template: speeds, price, and the RADIUS policy
-- that gets pushed to the BNG when a subscriber connects.
CREATE TABLE plans (
    id               SERIAL      PRIMARY KEY,
    name             TEXT        NOT NULL UNIQUE,
    download_speed   INTEGER     NOT NULL,  -- kbps
    upload_speed     INTEGER     NOT NULL,  -- kbps
    download_burst   INTEGER     NOT NULL,  -- kbit
    upload_burst     INTEGER     NOT NULL,  -- kbit
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
    plan_id          INTEGER     NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,

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

-- Seed example plans (no services attached by default)
INSERT INTO plans (name, download_speed, upload_speed, download_burst, upload_burst, price, is_active) VALUES
    ('Bronze 25/10', 25000, 10000, 1000, 500, 29.99, true),
    ('Silver 100/30', 100000, 30000, 3000, 1200, 49.99, true),
    ('Gold 300/100', 300000, 100000, 8000, 3000, 79.99, true),
    ('Legacy 10/5', 10000, 5000, 500, 250, 19.99, false);

-- Seed example customers (OSS-side entities)
INSERT INTO customers (name, email, phone, street, city, zip_code, state) VALUES
    ('Acme Bakery', 'ops@acmebakery.example', '+1-555-0100', '101 Market St', 'Springfield', '01103', 'MA'),
    ('Northside Clinic', 'it@northsideclinic.example', '+1-555-0101', '22 Health Ave', 'Hartford', '06103', 'CT'),
    ('River Apartments', 'manager@riverapts.example', '+1-555-0102', '78 River Rd', 'Providence', '02903', 'RI'),
    ('Maya Patel', 'maya.patel@example.com', '+1-555-0103', '14 Oak Lane', 'Nashua', '03060', 'NH');

-- Seed access routers
INSERT INTO access_routers (router_name, giaddr, bng_id) VALUES
    ('srl-access',  '10.0.0.2', 'bng-01'),
    ('srl2-access', '10.0.0.3', 'bng-01');

-- Seed default service: Acme Bakery on srl-access, Gold plan
-- RADIUS username: bng-01/000000000002/srl-access=7Cdefault=7Cirb1=7C1:0
INSERT INTO services (customer_id, plan_id, circuit_id, remote_id) VALUES
    (1, 3, 'srl-access|default|irb1|1:0', '000000000002');
