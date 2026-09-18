"""Offline OpenStreetMap reference data: acquisition, extraction and lookup.

Offline is the point. The basemap and the road network are files this project
ships and ingests, not a third-party API it calls at request time. There is no
mapping API key anywhere in CivicLens: nothing here can be rate-limited, have its
free tier expire, or start returning errors during a demo.

Data is © OpenStreetMap contributors, licensed ODbL 1.0. Every surface that
renders it must carry that attribution.
"""
