# Improve DB session handling

**GitHub Issue**: [#4](https://github.com/dimakrest/trading-analyst/issues/4)

## Problem

The database session is open during data fetch from Yahoo Finance. This is problematic because:
- Network I/O (fetching from Yahoo) happens while holding a database connection
- Database connections are a limited resource
- Long-running external API calls can cause connection pool exhaustion
- Session should only be open for actual database operations

## Expected Behavior

Database sessions should:
1. Only be open during actual database read/write operations
2. Not be held open during external API calls (Yahoo Finance)
3. Follow proper session lifecycle management

## Implementation Notes

- Identify where Yahoo Finance data fetching occurs
- Ensure session is closed before making external API calls
- Fetch data from Yahoo first, then open session to store results
- Review session management patterns across the codebase
