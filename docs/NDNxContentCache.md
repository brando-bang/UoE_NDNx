# Overview
The NDNx Content Cache server simulates a VPN-local cache. Being in the same VPC as the VPN service, it does not use e2ee communication with the VPN as in a non-simulated environment, communication would be locked down between the two. This server helps execute the NDNx content retrieval handshake by checking for the existence of an asset in the VPN-managed CDN cache and returning the proper encrypted content key that the user device should request for. The content keys are encrypted and managed in a cache to preserve the privacy of all traffic that leaves the user device through the VPN client service.

# Endpoints:
- `/heartbeat`: a healthcheck endpoint used to check for a successful deployment of the stack
- `/content_key`: this endpoint receives a desired content key from the VPN service and returns the encrypted content key for it if it exists in the VPN-managed content cache.

# Code:
[github](https://github.com/brando-bang/UoE_NDNx/blob/main/src/app/ndnx_content_key_cache.py)