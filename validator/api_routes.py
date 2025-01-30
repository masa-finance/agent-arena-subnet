from fastapi import FastAPI


def register_routes(app: FastAPI, healthcheck_func):
    """
    Register API routes for the FastAPI application.

    :param app: The FastAPI application instance.
    :param healthcheck_func: The healthcheck function to register.
    """
    app.add_api_route(
        "/healthcheck",
        healthcheck_func,
        methods=["GET"],
        tags=["healthcheck"],
    )
