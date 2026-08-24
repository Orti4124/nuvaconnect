#!/usr/bin/env python3
"""Lanza el servidor relay de emparejamiento."""
import asyncio

from server.relay_server import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
