from argparse import ArgumentParser

from fastcs.backends.asyncio_backend import AsyncioBackend
from fastcs.backends.epics.backend import EpicsBackend
from fastcs.connections import IPConnectionSettings
from fastcs.mapping import Mapping

from eiger_fastcs import __version__
from eiger_fastcs.eiger_controller import EigerController

__all__ = ["main"]


def get_controller() -> EigerController:
    ip_settings = IPConnectionSettings("127.0.0.1", 8080)
    tcont = EigerController(ip_settings)
    return tcont


# TODO: Maybe combine this with test_ioc
def create_gui() -> None:
    tcont = get_controller()
    m = Mapping(tcont)
    backend = EpicsBackend(m)
    backend.create_gui()


def test_ioc() -> None:
    tcont = get_controller()
    m = Mapping(tcont)
    backend = EpicsBackend(m)
    ioc = backend.get_ioc()

    ioc.run()


def test_asyncio_backend() -> None:
    tcont = get_controller()
    m = Mapping(tcont)
    backend = AsyncioBackend(m)
    backend.run_interactive_session()


def main(args=None):
    parser = ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=__version__)
    args = parser.parse_args(args)

    create_gui()
    test_ioc()


# test with: python -m eiger_fastcs
if __name__ == "__main__":
    main()
