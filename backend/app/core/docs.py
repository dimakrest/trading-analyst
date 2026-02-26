"""FastAPI documentation configuration and metadata.

Provides comprehensive OpenAPI documentation with custom descriptions,
examples, and proper API organization for Trading Analyst.
"""
from typing import Any

from fastapi.openapi.utils import get_openapi

# API Metadata
API_TITLE = "Trading Analyst API"
API_DESCRIPTION = """
## Trading Analyst API

A **local-first** technical analysis pattern detection system for chart pattern detection.

### Supported Patterns

The system currently supports detection of **4 basic chart patterns**:

1. **Head and Shoulders** - Reversal pattern indicating potential trend change
2. **Cup and Handle** - Continuation pattern suggesting bullish momentum
3. **Double Top** - Bearish reversal pattern at resistance levels
4. **Support/Resistance** - Key price levels for entry/exit decisions

### Key Features

- 📊 **Yahoo Finance Integration** - Real-time market data from Yahoo Finance
- 🔍 **Pattern Detection** - Automated identification of technical patterns
- 📈 **Technical Indicators** - Moving averages and trend analysis
- 🏠 **Local-First** - Designed for local development and analysis
- ⚡ **FastAPI** - High-performance async API with automatic documentation

### Data Sources

- **Primary**: Yahoo Finance API
- **Coverage**: Major stock exchanges (NYSE, NASDAQ, etc.)
- **Real-time**: Market data with minimal delay

### Performance Targets

| Operation | Target |
|-----------|--------|
| Single pattern detection | < 100ms |
| Batch detection (20 stocks) | < 5s |
| API response | < 500ms |

### Rate Limiting

- **Development**: No rate limiting (local development)
- **Production**: Standard rate limiting would apply (not applicable in local-first architecture)

### Authentication

**Note**: This is a local-first application designed for personal use.
No authentication is required for local development.

### API Versioning

Current version: **v1** - All endpoints are prefixed with `/api/v1`

### Error Handling

All endpoints follow consistent error response format:
- **4xx**: Client errors (invalid input, not found, etc.)
- **5xx**: Server errors (internal failures, external service issues)

### Support

For issues and questions, refer to the project documentation or create an issue in the repository.
"""

API_VERSION = "1.0.0"
API_CONTACT = {
    "name": "Trading Analyst",
    "url": "https://github.com/yourusername/trading_analyst",
}
API_LICENSE = {
    "name": "MIT",
    "url": "https://opensource.org/licenses/MIT",
}

# OpenAPI Tags
OPENAPI_TAGS: list[dict[str, Any]] = [
    {
        "name": "health",
        "description": "**System Health & Monitoring**\n\n"
        "Endpoints for monitoring application health, readiness, and liveness. "
        "Essential for container orchestration and load balancer probes.",
    },
    {
        "name": "account",
        "description": "**Account & Broker Status**\n\n"
        "Endpoints for checking broker connection status, account information, "
        "and data provider connectivity.",
    },
    {
        "name": "stocks",
        "description": "**Stock Market Data**\n\n"
        "Endpoints for retrieving stock price data, quotes, and symbol information. "
        "Includes historical OHLC data with technical indicators (MA 20, CCI).",
    },
    {
        "name": "configuration",
        "description": "**System Configuration**\n\n"
        "Retrieve system configuration including available patterns, symbols, "
        "technical indicators, and global settings.",
    },
    {
        "name": "analysis",
        "description": "**Technical Analysis**\n\n"
        "Comprehensive technical analysis endpoints including moving averages, "
        "momentum indicators, volatility measures, and support/resistance levels.",
    },
    {
        "name": "live-20",
        "description": "**Live 20 Mean Reversion Analysis**\n\n"
        "Analyze stocks using mean reversion strategy based on 20-day moving average. "
        "Evaluates 5 criteria (trend, MA20 distance, candle pattern, volume, CCI) "
        "to identify potential LONG (oversold bounce) setups.",
    },
]

# Response Examples
COMMON_RESPONSES = {
    400: {
        "description": "Bad Request - Invalid input parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_symbol": {
                        "summary": "Invalid Symbol Format",
                        "value": {
                            "error": "Bad Request",
                            "detail": "Invalid symbol format: ABC123XYZ. Symbol must be 1-10 alphanumeric characters.",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    },
                    "invalid_date_range": {
                        "summary": "Invalid Date Range",
                        "value": {
                            "error": "Bad Request",
                            "detail": "Start date must be before end date",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    },
                    "date_range_too_large": {
                        "summary": "Date Range Exceeds Limit",
                        "value": {
                            "error": "Bad Request",
                            "detail": "Date range cannot exceed 3 years",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    },
                    "invalid_status": {
                        "summary": "Invalid Status Value",
                        "value": {
                            "error": "Bad Request",
                            "detail": "Invalid status 'INVALID'. Valid values: PENDING, MONITORING, TRIGGERED, FILLED, CANCELLED, STOPPED_OUT",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Resource not found",
        "content": {
            "application/json": {
                "examples": {
                    "symbol_not_found": {
                        "summary": "Symbol Not Found",
                        "value": {
                            "error": "Not Found",
                            "detail": "Symbol 'INVALID' not found or has no data",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation Error - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "missing_field": {
                        "summary": "Missing Required Field",
                        "value": {
                            "error": "Validation Error",
                            "detail": [
                                {
                                    "type": "missing",
                                    "loc": ["body", "ticker"],
                                    "msg": "Field required",
                                    "input": {}
                                }
                            ],
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    },
                    "invalid_type": {
                        "summary": "Invalid Field Type",
                        "value": {
                            "error": "Validation Error",
                            "detail": [
                                {
                                    "type": "decimal_parsing",
                                    "loc": ["body", "trigger_price"],
                                    "msg": "Input should be a valid decimal",
                                    "input": "not_a_number"
                                }
                            ],
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    },
                    "custom_validation": {
                        "summary": "Custom Validation Failed",
                        "value": {
                            "error": "Validation Error",
                            "detail": [
                                {
                                    "type": "value_error",
                                    "loc": ["body", "stop_loss"],
                                    "msg": "Stop loss (198.00) must be below trigger price (195.00) for long setups",
                                    "input": 198.00
                                }
                            ],
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error - Server encountered an error",
        "content": {
            "application/json": {
                "examples": {
                    "generic_error": {
                        "summary": "Generic Internal Error",
                        "value": {
                            "error": "Internal Server Error",
                            "detail": "An unexpected error occurred",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    },
                    "database_error": {
                        "summary": "Database Error (Development Only)",
                        "value": {
                            "error": "Internal Server Error",
                            "detail": "Database connection failed",
                            "type": "DatabaseError",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    }
                }
            }
        },
    },
    503: {
        "description": "Service Unavailable - External service unavailable",
        "content": {
            "application/json": {
                "examples": {
                    "yahoo_finance_down": {
                        "summary": "Yahoo Finance Unavailable",
                        "value": {
                            "error": "Service Unavailable",
                            "detail": "External data service temporarily unavailable: Yahoo Finance API is currently unavailable",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    },
                    "broker_disconnected": {
                        "summary": "Broker Connection Lost",
                        "value": {
                            "error": "Service Unavailable",
                            "detail": "Broker connection unavailable. Please check IB Gateway/TWS connection.",
                            "timestamp": "2025-12-06T10:30:00Z",
                        }
                    }
                }
            }
        },
    },
}


def custom_openapi_schema(app) -> dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced documentation.

    Args:
        app: FastAPI application instance

    Returns:
        Dict[str, Any]: Custom OpenAPI schema
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=OPENAPI_TAGS,
        contact=API_CONTACT,
        license_info=API_LICENSE,
    )

    # Add custom schema properties
    openapi_schema["info"]["x-logo"] = {
        "url": "https://via.placeholder.com/200x50/2563eb/ffffff?text=Trading+Analyst",
        "altText": "Trading Analyst Logo",
    }

    # Add servers configuration
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Local Development Server",
            "variables": {
                "port": {
                    "default": "8000",
                    "description": "Server port (configurable via environment)",
                }
            },
        },
    ]

    # Add custom extensions
    openapi_schema["info"]["x-api-features"] = [
        "Pattern Detection",
        "Yahoo Finance Integration",
        "Technical Analysis",
        "Real-time Market Data",
        "Local-First Architecture",
    ]

    # Add global security schemes (even though not used in local development)
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API Key authentication (not required for local development)",
        }
    }

    # Add common response headers
    openapi_schema["components"]["headers"] = {
        "X-Process-Time": {
            "description": "Request processing time in milliseconds",
            "schema": {"type": "number", "example": 42.5},
        },
        "X-RateLimit-Limit": {
            "description": "Request rate limit (requests per minute)",
            "schema": {"type": "integer", "example": 60},
        },
        "X-RateLimit-Remaining": {
            "description": "Remaining requests in current window",
            "schema": {"type": "integer", "example": 45},
        },
        "X-RateLimit-Reset": {
            "description": "Timestamp when rate limit resets (Unix timestamp)",
            "schema": {"type": "integer", "example": 1733486400},
        },
    }

    # Enhanced response schemas for common errors
    openapi_schema["components"]["responses"] = COMMON_RESPONSES

    # Add example request/response schemas
    openapi_schema["components"]["examples"] = {
        "PatternDetectionRequest": {
            "summary": "Pattern Detection Request",
            "value": {
                "symbol": "AAPL",
                "period": "1y",
                "patterns": ["head_shoulders", "cup_handle"],
            },
        },
        "PatternDetectionResponse": {
            "summary": "Pattern Detection Response",
            "value": {
                "symbol": "AAPL",
                "timestamp": "2025-01-15T10:30:00Z",
                "patterns_found": [
                    {
                        "type": "cup_handle",
                        "confidence": 0.85,
                        "start_date": "2024-10-01",
                        "end_date": "2024-12-15",
                        "support_level": 180.50,
                        "resistance_level": 195.25,
                    }
                ],
                "technical_indicators": {"ma_20": 188.45, "ma_50": 185.20, "rsi": 62.3},
            },
        },
        "HealthResponse": {
            "summary": "Health Check Response",
            "value": {
                "status": "healthy",
                "timestamp": "2025-01-15T10:30:00Z",
                "version": "1.0.0",
                "environment": "development",
                "checks": {
                    "application": {"status": "healthy", "message": "Application ready"},
                    "database": {"status": "healthy", "message": "Database connected"},
                    "yahoo_finance": {"status": "healthy", "message": "External API available"},
                },
            },
        },
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def get_swagger_ui_html_config() -> dict[str, Any]:
    """Get Swagger UI HTML configuration.

    Returns:
        Dict[str, Any]: Swagger UI configuration
    """
    return {
        "swagger_js_url": "https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js",
        "swagger_css_url": "https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css",
        "swagger_ui_parameters": {
            "deepLinking": True,
            "displayRequestDuration": True,
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
            "docExpansion": "list",
            "filter": True,
            "showRequestHeaders": True,
            "syntaxHighlight.theme": "agate",
            "tryItOutEnabled": True,
            "validatorUrl": None,
        },
    }


def get_redoc_html_config() -> dict[str, Any]:
    """Get ReDoc HTML configuration.

    Returns:
        Dict[str, Any]: ReDoc configuration
    """
    return {
        "redoc_js_url": "https://unpkg.com/redoc@2.1.3/bundles/redoc.standalone.js",
        "redoc_options": {
            "expandResponses": "200,201",
            "hideDownloadButton": False,
            "hideHostname": False,
            "hideLoading": False,
            "jsonSampleExpandLevel": 2,
            "menuToggle": True,
            "nativeScrollbars": False,
            "noAutoAuth": True,
            "pathInMiddlePanel": False,
            "requiredPropsFirst": True,
            "scrollYOffset": 0,
            "showExtensions": True,
            "sortPropsAlphabetically": True,
            "theme": {
                "colors": {"primary": {"main": "#2563eb"}},
                "typography": {
                    "fontSize": "14px",
                    "headings": {"fontFamily": "Montserrat, sans-serif"},
                },
            },
        },
    }
