#!/bin/bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -keyout certs/server.key \
  -out certs/server.crt -days 365 -nodes -subj "/CN=NCPServer" 2>/dev/null \
  && echo "certs ready" || echo "install openssl first"
