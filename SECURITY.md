# Security

## Scope

This project is a lab environment designed for learning and experimentation. It is **not intended for production use**. Default credentials are used throughout for convenience in the emulated topology.

## Known Considerations

- RADIUS shared secrets and database passwords are hardcoded defaults (`testing123`, `oss`, `test`).
- The BNG processes raw network packets with elevated privileges (`CAP_NET_RAW`, `CAP_NET_ADMIN`).
- The API layer has no authentication — all endpoints are publicly accessible within the lab network.
- CORS is configured to allow all origins.

## Reporting

If you discover a security issue in the project's code (e.g., a vulnerability that would be exploitable if this were deployed in a real network), please open a GitHub issue. Since this is a lab project with no real users or data at risk, public disclosure is fine.
