__version__ = "0.0.2"
version_split = __version__.split(".")
version_numerical = (
    (100 * int(version_split[0]))
    + (10 * int(version_split[1]))
    + (1 * int(version_split[2]))
)
