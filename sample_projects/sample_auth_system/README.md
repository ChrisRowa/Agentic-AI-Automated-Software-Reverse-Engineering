# Sample Auth System

A sample authentication system for testing the reverse engineering platform.

## Requirements
- REQ-001: Users must be able to login with username and password
- REQ-002: Passwords must be hashed using bcrypt
- REQ-003: Sessions must expire after 30 minutes
- REQ-004: Failed login attempts must be logged

## Architecture
The system follows a layered architecture:
- Controllers: Handle HTTP requests
- Services: Business logic
- Repositories: Data access layer
- Models: Data structures
