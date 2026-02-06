DHCP_LEASE_FILE_DIR_PATH = "/tmp/dnsmasq"
DHCP_LEASE_FILE_PATH = DHCP_LEASE_FILE_DIR_PATH + "/dnsmasq-bng.leases"
DHCP_GRACE_SECONDS = 10
DHCP_LEASE_EXPIRY_SECONDS = 120
DHCP_NAK_TERMINATE_COUNT_THRESHOLD = 3 # How many NAKs before terminating session

MARK_DISCONNECT_GRACE_SECONDS = 10
MARK_IDLE_GRACE_SECONDS = 20
IDLE_GRACE_AFTER_CONNECT = 40 # To check for idle after initial connect where they may be no traffic for a bit i.e when s.last_traffic_seen is None

# Move this to a dynamic configuration later that can be changed at runtime
ENABLE_IDLE_DISCONNECT = False
TOMBSTONE_TTL_SECONDS = 600
TOMBSTONE_EXPIRY_GRACE_SECONDS = 60

# Event dispatcher settings
EVENT_DISPATCHER_STREAM_ID = "bng_events"
