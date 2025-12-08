# Overview
The VPN Server Stack acts as the gateway for content requests originating from the Clientside VPN Software. It is responsible for decrypting these requests, interacting with the Content Encryption Key Management Service to determine content availability, and relaying the appropriate response back to the client.

# Endpoints:
- `/heartbeat`: a healthcheck endpoint used to check for a successful deployment of the stack
- `/download_direct`: this endpoint downloads the 10mb testing asset directly from the nforce mirror (which does not employ a CDN) and sets a baseline for internet performance
- `/download_cdn`: this endpoint downloads the same 10mb testing asset from a CDN which sets a baseline for a high performance content request
- `/use_vpn`: this endpoint will decrypt a VPN request from the user device and then either download the asset directly or from a cdn before encrypting the content and returning it to the user device
- `/use_ndnx`: this endpoint receives an e2ee request for a content key. Upon decryption, it checks for the existence of the content within the VPN-managed CDN by checking the NDNx content key cache for a corresponding encrypted content key. If it exists, it returns the encrypted content key with e2ee to the user device so that the user device can retrieve the encrypted content from a geographically local VPN-managed CDN edge node.

# Code:
[github](https://github.com/brando-bang/UoE_NDNx/blob/main/src/app/vpn_service.py)