# MCP

## Server

MCP tools are defined with FastMCP in mcp_server/server.py:

- get_customer (READ_ONLY)
- get_contract (READ_ONLY)
- get_invoice (READ_ONLY)
- create_credit (WRITE)
- request_approval (WRITE)

## Client

Tool classification metadata is defined in src/infrastructure/mcp/client.py.

## Roadmap

- Wire tools to repository-backed service layer.
- Add tool-level authorization checks and typed error mapping.
- Add contract tests for request/response schemas.
