"""CLI entry point for TRMNL BYOS server."""


def main():
    """Run the TRMNL BYOS server."""
    import uvicorn

    from trmnl_server.config import get_config

    config = get_config()

    print(f"Starting MunichGlance TRMNL Server on {config.host}:{config.port}")

    uvicorn.run(
        "trmnl_server.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="debug" if config.debug else "info",
    )


if __name__ == "__main__":
    main()
