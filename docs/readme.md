# NDNx
Using a Virtual Private Network negates the performance advantage of Named Data Networking. Consider the case of retrieving an asset from a Content Delivery Network: at best, a VPN exit node that is geographically close to both a user and a CDN edge node will simply add a hop to a normal CDN request increasing latency. At worst, a geographically distant VPN exit node will ping to its own local CDN edge node and perform significantly worse than a normal CDN request.

Named Data Networking eXtensions is a solution to this problem where VPN service providers can incrementally deploy their own named data networking hardware so that privacy-required users can still benefit from geographically advantaged content retrieval while also maintaining end-to-end encryption of their traffic.

# About this Repo
This repo contains the service code and infrastructure-as-code for deploying a simulation of a geographically separated user's device and a VPN server. There are endpoints available on the two servers to allow for speed testing different configurations of content retrieval: with VPN, with CDN, with both, with neither, and with NDNx.

More information can be found in the below links:

[Project Overview](Overview.md)

[User Device](UserDevice.md)

[VPN Server](VPNServer.md)