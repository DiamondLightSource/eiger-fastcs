import asyncio
from dataclasses import dataclass
from typing import Any, Mapping
from attr import Attribute

from fastcs.attributes import AttrR, AttrRW, AttrW
from fastcs.connections import HTTPConnection, IPConnectionSettings
from fastcs.controller import Controller
from fastcs.datatypes import Bool, Float, Int, String


@dataclass
class EigerHandler:
    name: str
    update_period: float = 0.2

    async def put(
        self,
        controller: "EigerController",
        attr: AttrW,
        value: Any,
    ) -> None:
        await controller.connection.put(self.name, value)

    async def update(
        self,
        controller: "EigerController",
        attr: AttrR,
    ) -> None:
        try:
            response = await controller.connection.get(self.name)
            await attr.set(response["value"])
        except Exception as e:
            print(f"update loop failed:{e}")


class EigerController(Controller):
    detector_state = AttrR(
        String(),
        handler=EigerHandler("detector/api/1.8.0/status/state"),
    )

    def __init__(self, settings: IPConnectionSettings) -> None:
        super().__init__()
        self._ip_settings = settings

        asyncio.run(self.initialise())

    async def connect(self) -> None:
        self.connection = HTTPConnection(
            self._ip_settings, headers={"Content-Type": "application/json"}
        )

    async def initialise(self) -> None:
        # Adding extra loop prior to backend loop creating the Attributes to be PVs
        connection = HTTPConnection(
            self._ip_settings, headers={"Content-Type": "application/json"}
        )
        subsystems = ["detector", "stream", "monitor"]
        modes = ["status", "config"]
        pv_clashes = {}
        attributes: Mapping[str, Attribute] = {}

        for index, subsystem in enumerate(subsystems):
            for mode in modes:
                response = await connection.get(f"{subsystem}/api/1.8.0/{mode}/keys")
                subsystem_parameters = response["value"]
                requests = [
                    connection.get(f"{subsystem}/api/1.8.0/{mode}/{item}")
                    for item in subsystem_parameters
                ]
                values = await asyncio.gather(*requests)

                for parameter_name, parameter in zip(subsystem_parameters, values):
                    # FastCS Types
                    match parameter["value_type"]:
                        case "float":
                            datatype = Float()
                        case "int":
                            datatype = Int()
                        case "bool":
                            datatype = Bool()
                        case "string" | "datetime" | "State" | "string[]":
                            datatype = String()
                        case _:
                            print(f"Could not process {parameter_name}")

                    # finding appropriate naming to ensure repeats are not ovewritten and ensuring that PV has not been created already
                    if (
                        parameter_name in list(attributes.keys())
                        and parameter_name not in self.__dict__.keys()
                    ):
                        # Adding original instance of the duplicate into dictionary to rename original instance in attributes later
                        if parameter_name not in list(pv_clashes.keys()):
                            pv_clashes[
                                parameter_name
                            ] = f"{subsystems[index-1]}_{parameter_name}"
                        name = f"{subsystem}_{parameter_name}"
                    else:
                        name = parameter_name

                    # mapping attributes using access mode metadata
                    match parameter["access_mode"]:
                        case "r":
                            attributes[name] = AttrR(
                                datatype,
                                handler=EigerHandler(
                                    f"{subsystem}/api/1.8.0/{mode}/{parameter_name}"
                                ),
                            )
                        case "rw":
                            attributes[name] = AttrRW(
                                datatype,
                                handler=EigerHandler(
                                    f"{subsystem}/api/1.8.0/{mode}/{parameter_name}"
                                ),
                            )

        # Renaming original instance of duplicate in Attribute / Removing unique names already created
        for clash_name, unique_name in pv_clashes.items():
            if unique_name in self.__dict__.keys():
                del attributes[clash_name]
                print(
                    f"{unique_name} was already created before, {clash_name} is being deleted"
                )

            else:
                attributes[unique_name] = attributes.pop(clash_name)
                print(f"Replacing the repeat,{clash_name}, with {unique_name}")

        for name, attribute in attributes.items():
            setattr(self, name, attribute)

        # Check current state of detector_state to see if initializing is required.
        detector_state_val = await connection.get(self.detector_state.updater.name)
        if detector_state_val["value"] == "na":
            print("Initializing Detector")
            await connection.put("detector/api/1.8.0/command/initialize", "")

        a = 1
        await connection.close()

    async def close(self) -> None:
        await self.connection.close()
