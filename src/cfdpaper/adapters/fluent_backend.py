"""Optional, read-only Fluent surface extraction through PyFluent.

Native reports remain the formal integral values. The accompanying NPZ contains
the original boundary faces for regional analysis, without interpolation.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np

from .base import ExtractedRecord, ExtractionRequest, SourceChangedError, UnsupportedExtractionError
from .csv import source_sha256

_UNITS = {"temperature": "K", "heat-flux": "W/m^2"}


def pyfluent_available() -> bool:
    """Check the optional Python backend without starting a solver or license."""
    try:
        return importlib.util.find_spec("ansys.fluent.core") is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _launch_session(*, output_dir: Path, options: Mapping[str, Any]):
    if not pyfluent_available():
        raise UnsupportedExtractionError(
            "Fluent read-only extraction requires optional ansys-fluent-core; "
            "install it in the executing Python environment or export neutral CSV/NPZ."
        )
    import ansys.fluent.core as pf

    executable = options.get("executable")
    if not executable:
        return pf.launch_fluent(
            mode="solver",
            precision="double",
            processor_count=1,
            product_version=options.get("product_version"),
            ui_mode="hidden_gui" if os.name == "nt" else "no_gui",
            cwd=str(output_dir),
            start_transcript=False,
            start_watchdog=False,
        )
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"Fluent executable is missing: {executable}")
    info = output_dir / "server_info.txt"
    if info.exists():
        raise FileExistsError(f"Session info already exists: {info}")
    environment = os.environ.copy()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "grpc_proxy",
    ):
        environment.pop(key, None)
    environment.update(no_grpc_proxy="127.0.0.1,localhost", REMOTING_SERVER_ADDRESS="127.0.0.1")
    command = [
        str(executable),
        "3ddp",
        "-hidden" if os.name == "nt" else "-g",
        "-t1",
        "-nm",
        f"-sifile={info.as_posix()}",
    ]
    with (output_dir / "launcher.log").open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=output_dir,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    deadline = time.monotonic() + float(options.get("start_timeout", 180))
    while time.monotonic() < deadline:
        if info.is_file() and info.stat().st_size > 20:
            return pf.connect_to_fluent(
                server_info_file_name=str(info),
                cleanup_on_exit=True,
                start_transcript=False,
                start_watchdog=False,
            )
        if process.poll() is not None:
            raise RuntimeError(f"Fluent launcher exited; inspect {output_dir / 'launcher.log'}")
        time.sleep(0.5)
    raise TimeoutError(f"Fluent did not publish server info; inspect {output_dir / 'launcher.log'}")


def _geometry(arrays: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    vertices = np.asarray(arrays["vertices"], dtype=float).reshape(-1, 3)
    packed = np.asarray(arrays["faces"], dtype=np.int64).ravel()
    starts, areas = [], []
    cursor = 0
    while cursor < len(packed):
        starts.append(cursor)
        count = int(packed[cursor])
        stop = cursor + count + 1
        if count < 3 or stop > len(packed):
            raise ValueError("Invalid original Fluent face connectivity")
        ids = packed[cursor + 1 : stop]
        if (ids < 0).any() or (ids >= len(vertices)).any():
            raise ValueError("Fluent face connectivity refers to missing vertices")
        polygon = vertices[ids]
        local = polygon - polygon[0]
        area_vector = np.sum(np.cross(local, np.roll(local, -1, axis=0)), axis=0) / 2
        areas.append(float(np.linalg.norm(area_vector)))
        cursor = stop
    if not areas or not np.isfinite(areas).all() or not (np.asarray(areas) > 0).all():
        raise ValueError("Original Fluent surface has empty, nonfinite or zero-area faces")
    result = {key.replace("-", "_"): np.asarray(value) for key, value in arrays.items()}
    result.update(
        vertices=vertices,
        faces=packed,
        connectivity=packed,
        starts=np.asarray(starts, dtype=np.int64),
        face_area=np.asarray(areas),
    )
    result["face_area_m2"] = result["face_area"]
    result["vertices_m"] = vertices
    result["faces_connectivity"] = packed
    result["face_starts"] = result["starts"]
    native_centroids = result.get("centroid", result.get("centroids"))
    if native_centroids is None:
        raise ValueError("Fluent original face centroids are missing; no centroid is inferred")
    native_centroids = np.asarray(native_centroids).reshape(-1, 3)
    if len(native_centroids) != len(areas):
        raise ValueError("Fluent face centroids do not align with original faces")
    result["centroid_m"] = native_centroids
    for axis, name in enumerate(("centroid_x_m", "centroid_y_m", "centroid_z_m")):
        result[name] = native_centroids[:, axis]
    # These are local ordinals, not solver-global face IDs.
    result["face_ordinal"] = np.arange(len(areas), dtype=np.int64)
    return result


def _report(
    session, root: Path, label: str, zone: str, report_type: str, field: str
) -> tuple[float, str]:
    name = f"{label}_{report_type}_{field}.txt".replace("-", "_")
    target = root / "reports" / name
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        raise FileExistsError(target)
    # The client writes the original report transcript locally. This also works
    # when v231 cannot represent Unicode absolute paths or a saved case changes
    # Fluent's working directory while loading a UDF library.
    if hasattr(session, "transcript"):
        capture = root / "native-transcript.txt"
        previous = len(capture.read_text(errors="replace")) if capture.exists() else 0
        session.results.report.surface_integrals(
            report_type=report_type, surface_id=[zone], cell_report=field, write_to_file=False
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            raw = capture.read_text(errors="replace")[previous:] if capture.exists() else ""
            if re.search(r"^\s*" + re.escape(zone) + r"\s+([-+\d.eE]+)\s*$", raw, re.M):
                target.write_text(raw, encoding="utf-8")
                break
            time.sleep(0.05)
    else:
        session.results.report.surface_integrals(
            report_type=report_type,
            surface_id=[zone],
            cell_report=field,
            write_to_file=True,
            file_name=str(target),
        )
    raw = target.read_text(errors="replace")
    match = re.search(r"^\s*" + re.escape(zone) + r"\s+([-+\d.eE]+)\s*$", raw, re.M)
    if not match or not np.isfinite(float(match[1])):
        raise ValueError(f"No finite Fluent {report_type} report for {zone}: {target}")
    return float(match[1]), target.relative_to(root).as_posix()


def export_fluent_surfaces(
    request: ExtractionRequest, *, session_factory: Callable[..., Any] | None = None
) -> Path:
    """Export a saved CASE/DATA pair into neutral original-face NPZ and native reports.

    Required options: ``data_file``, ``output_dir`` and ``surfaces`` (label-to-zone
    mapping). Optional: ``executable``, ``case_id``, ``field_units``, startup options.
    On Windows versions requiring ASCII solver paths, ``solver_case_file`` and
    ``solver_data_file`` may name existing aliases of the same source files.
    ``region_bounds={"hot": {"axes": {"x": [lo, hi], "y": [lo, hi]}}}``
    adds native coordinate clips in m. A region may select one ``surface`` label;
    otherwise it applies to every selected wall. ``export_fields=False`` keeps
    native whole-wall and region reports without repeating large NPZ exports.
    No equations are advanced; no source files are written. Heat-flux signs remain
    Fluent's selected boundary-side convention and require physical interpretation.
    """
    source = request.source.resolve()
    if not source.is_file() or not source.name.lower().endswith((".cas", ".cas.h5")):
        raise ValueError("Fluent extraction requires an existing .cas or .cas.h5 source")
    if not request.options.get("data_file"):
        raise ValueError("Fluent extraction requires the saved data_file")
    data = Path(request.options["data_file"]).resolve()
    if not data.is_file() or not data.name.lower().endswith((".dat", ".dat.h5")):
        raise ValueError("Fluent data_file must be an existing .dat or .dat.h5")
    solver_case = Path(request.options.get("solver_case_file", source)).absolute()
    solver_data = Path(request.options.get("solver_data_file", data)).absolute()
    if solver_case.resolve() != source or solver_data.resolve() != data:
        raise ValueError("Fluent solver path aliases must refer to the same CASE/DATA sources")
    if not request.options.get("output_dir"):
        raise ValueError("Fluent extraction requires an isolated output_dir")
    output = Path(request.options["output_dir"]).resolve()
    if output in {source.parent, data.parent}:
        raise ValueError("Fluent output_dir must differ from the native source directory")
    if (output / "manifest.json").exists():
        raise FileExistsError(output / "manifest.json")
    surfaces = request.options.get("surfaces")
    if not isinstance(surfaces, Mapping) or not surfaces:
        raise ValueError("Fluent surfaces must map output labels to exact zone names")
    for label, zone in surfaces.items():
        if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", label):
            raise ValueError(
                "Surface labels must contain only letters, digits, underscores or hyphens"
            )
        if not isinstance(zone, str) or not zone.strip():
            raise ValueError("Each surface requires an exact nonempty zone name")
    variables = request.variables or ("temperature", "heat-flux")
    regions = request.options.get("region_bounds", {})
    if not isinstance(regions, Mapping):
        raise ValueError("region_bounds must map region labels to coordinate axes and bounds")
    for region_label, definition in regions.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", region_label):
            raise ValueError("Region labels must use letters, digits, underscores or hyphens")
        axes = definition.get("axes", {})
        if not axes or any(axis not in ("x", "y", "z") for axis in axes):
            raise ValueError("A region requires x/y/z coordinate bounds in m")
        for bounds in axes.values():
            if len(bounds) != 2 or not np.isfinite(bounds).all() or bounds[0] >= bounds[1]:
                raise ValueError("Region coordinate bounds must be finite increasing pairs in m")
    units = {**_UNITS, **dict(request.options.get("field_units", {}))}
    if any(field in _UNITS and units[field] != _UNITS[field] for field in variables):
        raise ValueError(
            "Native Fluent temperature/heat-flux units must retain the SI field definition"
        )
    if any(
        not isinstance(units.get(field), str) or not units[field].strip() for field in variables
    ):
        raise ValueError("Every requested Fluent field requires an explicit physical unit")
    before = {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in (source, data)}
    case_hash = source_sha256(source)
    output.mkdir(parents=True, exist_ok=True)
    factory = session_factory or _launch_session
    session = factory(output_dir=output, options=request.options)
    entries = []
    try:
        session.file.read(file_type="case", file_name=solver_case.as_posix())
        session.file.read(file_type="data", file_name=solver_data.as_posix())
        inventory = session.field_info.get_surfaces_info()
        missing = set(surfaces.values()) - inventory.keys()
        if missing:
            raise ValueError(f"Fluent is missing requested surface zones: {sorted(missing)}")
        fields = session.field_info.get_scalar_fields_info()
        if missing_fields := set(variables) - fields.keys():
            raise ValueError(f"Fluent is missing scalar fields: {sorted(missing_fields)}")
        detected_version = session.get_fluent_version()
        version = str(getattr(detected_version, "value", detected_version))
        if hasattr(session, "transcript"):
            # Case/UDF loading in older Windows Fluent may emit non-UTF8 paths,
            # terminating a gRPC transcript stream. Subscribe after loading;
            # the report text itself contains ASCII zone names and numbers.
            session.transcript.start(
                file_name=str(output / "native-transcript.txt"), write_to_stdout=False
            )
            time.sleep(0.2)
        for label, zone in surfaces.items():
            native, reports = {}, {}
            area, reports["area"] = _report(session, output, label, zone, "area", "temperature")
            native["area_m2"] = area
            if "temperature" in variables:
                native["temperature_area_mean_K"], reports["temperature_area_mean"] = _report(
                    session, output, label, zone, "area-weighted-avg", "temperature"
                )
            if "heat-flux" in variables:
                native["heat_flow_W"], reports["heat_flow"] = _report(
                    session, output, label, zone, "integral", "heat-flux"
                )
            surface_ids = inventory[zone]["surface_id"]
            region_results = {}
            for region_label, definition in regions.items():
                if definition.get("surface", label) not in (label, zone):
                    continue
                clipped = zone
                for axis, bounds in definition["axes"].items():
                    name = f"cfdpaper_{label}_{region_label}_{axis}"
                    session.tui.surface.iso_clip(
                        f"{axis}-coordinate",
                        name,
                        clipped,
                        "()",
                        float(bounds[0]),
                        float(bounds[1]),
                    )
                    clipped = name
                report_label = f"{label}_{region_label}"
                region_values, region_files = {}, {}
                region_values["area_m2"], region_files["area"] = _report(
                    session, output, report_label, clipped, "area", "temperature"
                )
                if region_values["area_m2"] <= 0:
                    raise ValueError(f"Native clipped region {label}/{region_label} is empty")
                if "temperature" in variables:
                    (
                        region_values["temperature_area_mean_K"],
                        region_files["temperature_area_mean"],
                    ) = _report(
                        session, output, report_label, clipped, "area-weighted-avg", "temperature"
                    )
                if "heat-flux" in variables:
                    region_values["heat_flow_W"], region_files["heat_flow"] = _report(
                        session, output, report_label, clipped, "integral", "heat-flux"
                    )
                region_results[region_label] = {
                    "source_surface": zone,
                    "clipped_surface": clipped,
                    "bounds_m": dict(definition["axes"]),
                    "native_reports": region_values,
                    "report_files": region_files,
                    "method": "Fluent coordinate iso-clip followed by native surface-integrals",
                }
            if request.options.get("export_fields", True) is False:
                entries.append(
                    {
                        "label": label,
                        "surface": zone,
                        "surface_id": surface_ids[0],
                        "zone_id": inventory[zone].get("zone_id"),
                        "path": None,
                        "native_reports": native,
                        "report_files": reports,
                        "native_report_domain": {"surface": zone, "surface_ids": list(surface_ids)},
                        "regions": region_results,
                        "exported_fields": False,
                    }
                )
                continue
            transaction = session.field_data.new_transaction()
            transaction.add_surfaces_request(
                surface_ids=surface_ids,
                provide_vertices=True,
                provide_faces=True,
                provide_faces_centroid=True,
                provide_faces_normal=True,
            )
            for field in variables:
                transaction.add_scalar_fields_request(
                    field_name=field,
                    surface_ids=surface_ids,
                    node_value=False,
                    boundary_value=True,
                )
            merged: dict[int, dict] = {int(sid): {} for sid in surface_ids}
            for batch in transaction.get_fields().values():
                for sid, arrays in batch.items():
                    if int(sid) in merged:
                        merged[int(sid)].update(arrays)
            for sid, arrays in merged.items():
                payload = _geometry(arrays)
                nfaces = len(payload["face_area"])
                for field in variables:
                    key = field.replace("-", "_")
                    values = np.asarray(payload[key], dtype=float).ravel()
                    if values.shape != (nfaces,) or not np.isfinite(values).all():
                        raise ValueError(f"Fluent field {field} does not align with original faces")
                    payload[key] = values
                relative = f"{label}_{sid}.npz"
                target = output / relative
                if target.exists():
                    raise FileExistsError(target)
                np.savez_compressed(target, **payload)
                entries.append(
                    {
                        "label": label,
                        "surface": zone,
                        "surface_id": sid,
                        "zone_id": inventory[zone].get("zone_id"),
                        "path": relative,
                        "face_count": nfaces,
                        "association": "face",
                        "node_value": False,
                        "boundary_value": True,
                        "coordinate_unit": "m",
                        "units": {
                            **{field.replace("-", "_"): units[field] for field in variables},
                            "face_area": "m^2",
                            "face_area_m2": "m^2",
                            "centroid_x_m": "m",
                            "centroid_y_m": "m",
                            "centroid_z_m": "m",
                        },
                        "area_definition": (
                            "magnitude of original polygon vector area; no display interpolation"
                        ),
                        "face_identity": (
                            "surface-local exported ordinal, not solver-global face ID"
                        ),
                        "normal_definition": (
                            "unmodified native faces-normal array; heat-flux sign is not flipped"
                        ),
                        "native_reports": native,
                        "regions": region_results,
                        "native_report_domain": {"surface": zone, "surface_ids": list(surface_ids)},
                        "report_files": reports,
                        "geometry_area_sum_m2": float(payload["face_area"].sum()),
                    }
                )
        after = {
            str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in (source, data)
        }
        if before != after:
            raise SourceChangedError("Native CASE/DATA changed during read-only Fluent extraction")
        result = {
            "adapter": "fluent",
            "solver_version": version,
            "case_id": request.options.get("case_id"),
            "source": str(source),
            "data_file": str(data),
            "solver_case_file": str(solver_case),
            "solver_data_file": str(solver_data),
            "source_hash": case_hash,
            "source_file_state": before,
            "inventory": {
                "scalar_fields": sorted(fields),
                "surfaces": [
                    {
                        "name": name,
                        "surface_ids": details.get("surface_id", []),
                        "zone_id": details.get("zone_id"),
                        "zone_type": details.get("zone_type"),
                    }
                    for name, details in inventory.items()
                ],
            },
            "surfaces": entries,
            "iterations_performed": 0,
            "source_write_performed": False,
            "heat_flux_definition": (
                "native boundary heat-flux W/m^2; selected side convention retained"
            ),
            "integral_authority": (
                "Fluent native surface-integrals; polygon sums are postprocessing diagnostics"
            ),
        }
        manifest = output / "manifest.json"
        manifest.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest
    finally:
        if hasattr(session, "transcript"):
            session.transcript.stop()
        session.exit()


def extract_fluent_records(
    request: ExtractionRequest, *, session_factory: Callable[..., Any] | None = None
) -> list[ExtractedRecord]:
    manifest = export_fluent_surfaces(request, session_factory=session_factory)
    content = json.loads(manifest.read_text(encoding="utf-8"))
    records = []
    seen_zones = set()
    for entry in content["surfaces"]:
        if entry["surface"] in seen_zones:
            continue
        seen_zones.add(entry["surface"])
        native = entry["native_reports"]
        values = {"area": native["area_m2"]}
        units = {"area": "m^2"}
        for source_key, key, unit in (
            ("temperature_area_mean_K", "temperature_area_mean", "K"),
            ("heat_flow_W", "heat_flow", "W"),
        ):
            if source_key in native:
                values[key], units[key] = native[source_key], unit
        records.append(
            ExtractedRecord(
                source_uri=request.source.resolve().as_uri(),
                locator=f"surface:{entry['surface']}:{entry['surface_id']}",
                source_hash=content["source_hash"],
                values=values,
                units=units,
                metadata={
                    **entry,
                    "manifest": str(manifest),
                    "solver_version": content["solver_version"],
                    "data_file": content["data_file"],
                    "source_file_state": content["source_file_state"],
                    "field_exports": [
                        surface["path"]
                        for surface in content["surfaces"]
                        if surface["surface"] == entry["surface"] and surface.get("path")
                    ],
                    "iterations_performed": 0,
                },
            )
        )
    return records
