from typing import Optional, List
import os
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
    

app = FastAPI(title="Measurement API")

origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The API now loads DataFrames from `data/tmp/<dataset>/output_df.feather`.
# Helpers below enumerate available datasets and load the requested feather file.

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DATA_ROOT = os.path.join(_PROJECT_ROOT, "ideas", "data")
_PARSED_ROOT = os.path.join(_DATA_ROOT, "parsed")



def list_datasets() -> List[str]:
    """Return folder names in `data/tmp` that contain `output_df.feather`.
    Sorted alphabetically.
    """
    if not os.path.isdir(_PARSED_ROOT):
        return []
    names = []
    for name in os.listdir(_PARSED_ROOT):
        full = os.path.join(_PARSED_ROOT, name)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "output_df.feather")):
            names.append(name)
    return sorted(names)


def _resolve_dataset(dataset: Optional[str]) -> str:
    """Pick the dataset to use or raise informative HTTP errors.

    If `dataset` is provided, ensure it exists. If omitted and exactly one
    dataset is available, use it. Otherwise raise an error listing available datasets.
    """
    available = list_datasets()
    if dataset:
        if dataset not in available:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset}' not found; available: {available}")
        return dataset
    if len(available) == 1:
        return available[0]
    if len(available) == 0:
        raise HTTPException(status_code=404, detail="No datasets found in data/tmp")
    # Multiple available and none specified — ask client to choose
    raise HTTPException(status_code=400, detail=f"Multiple datasets available; specify one via 'dataset' query parameter: {available}")


def load_df_for_dataset(dataset: str) -> pd.DataFrame:
    path = os.path.join(_PARSED_ROOT, dataset, "output_df.feather")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Feather file not found for dataset '{dataset}'")
    return pd.read_feather(path)


@app.get("/df")
def get_df(dataset: Optional[str] = Query(None, description="Dataset subfolder name inside data/tmp."),
           limit: Optional[int] = Query(None, ge=1, description="Max number of rows to return; returns all if omitted")):
    """
    Return the requested dataset's DataFrame as JSON (list of records). If `dataset`
    is omitted and exactly one dataset exists, it will be selected automatically.
    Use `limit` to restrict rows.
    """
    ds = _resolve_dataset(dataset)
    df = load_df_for_dataset(ds)
    records = df.to_dict(orient="records")
    if limit is not None:
        records = records[:limit]
    return jsonable_encoder(records)


@app.get("/df/info")
def get_df_info(dataset: Optional[str] = Query(None, description="Dataset subfolder name inside data/tmp.")):
    """
    Return metadata about the chosen dataset's DataFrame: columns, dtypes, shape, memory usage, head and descriptive stats.
    """
    ds = _resolve_dataset(dataset)
    df = load_df_for_dataset(ds)

    # columns and dtypes
    dtypes = {str(col): str(dtype) for col, dtype in df.dtypes.items()}

    # basic stats
    info = {
        "dataset": ds,
        "columns": list(df.columns.astype(str)),
        "dtypes": dtypes,
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
        "head": df.head(10).to_dict(orient="records"),
    }

    desc_num = df.describe(include=[np.number]).to_dict()
    desc_obj = df.describe(include=[object]).to_dict()

    info["describe_numeric"] = desc_num
    info["describe_objects"] = desc_obj

    return jsonable_encoder(info)


@app.get("/datasets")
def get_datasets():
    """List available dataset folder names under `data/tmp` that contain `output_df.feather`."""
    return jsonable_encoder(list_datasets())



@app.get("/tle")
def get_tle(
    name: Optional[str] = Query(None, description="Filter by satellite name (substring match)."),
    type_filter: Optional[str] = Query(None, description="Filter by type ('Communications' or 'Other')."),
    system: Optional[str] = Query(None, description="Filter by system: 'iridium', 'starlink', 'orbcomm', 'oneweb', 'globalstar', or 'other' (everything else)."),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to include ('name', 'line1', 'line2', 'type', 'system'). If omitted, all fields are returned."),
    limit: Optional[int] = Query(None, ge=1, description="Max number of results to return; returns all if omitted")
):
    """Return parsed JSON from `ideas/step1_pull/output/tles.json` with optional filtering and field selection.

    Parameters:
    - name: Filter by satellite name (substring match, case-insensitive)
    - type_filter: Filter by type field
    - system: Filter by system (iridium, starlink, orbcomm, oneweb, globalstar, or other)
    - fields: Comma-separated list of fields to include in response
    - limit: Max number of results

    The path is resolved relative to the repository root (parent of this `data` folder).
    If the file is missing a 404 is returned.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tle_path = os.path.join(repo_root, "ideas", "step1_pull", "output", "tles.json")
    if not os.path.exists(tle_path):
        raise HTTPException(status_code=404, detail=f"TLE file not found at {tle_path}")
    try:
        with open(tle_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse JSON: {exc}")

    # Filter by name (substring, case-insensitive)
    if name:
        data = [item for item in data if name.lower() in item.get("name", "").lower()]

    # Filter by type
    if type_filter:
        data = [item for item in data if item.get("type") == type_filter]

    # Filter by system
    if system:
        system_lower = system.lower()
        if system_lower == "other":
            # "other" means everything except the known systems
            known_systems = {"iridium", "starlink", "orbcomm", "oneweb", "globalstar"}
            data = [item for item in data if item.get("system", "").lower() not in known_systems]
        else:
            # Filter by specific system (case-insensitive)
            data = [item for item in data if item.get("system", "").lower() == system_lower]

    # Select specific fields if requested
    if fields:
        field_list = [f.strip() for f in fields.split(",")]
        data = [{k: item.get(k) for k in field_list if k in item} for item in data]

    # Apply limit
    if limit is not None:
        data = data[:limit]

    return jsonable_encoder(data)


@app.get("/iridium_ira")
def iridium_ira():
    """Get Iridium IRA data as JSON"""

    # feather_path = os.path.join(_DATA_ROOT, "dummy_ira.feather")
    feather_path = os.path.join(_PARSED_ROOT, "ira.feather")
    # Ensure the feather file exists
    if not os.path.exists(feather_path):
        raise HTTPException(status_code=404, detail=f"Feather file not found at {feather_path}")
    df = pd.read_feather(feather_path)

    # Replace pandas NA with None so JSON encoders don't choke
    df = df.where(pd.notnull(df), None)

    # Convert to records (this may still include numpy types); serialize via
    # json.dumps with a fallback that converts numpy / array-like types to lists.
    records = df.to_dict(orient="records")

    def _default(o):
        # numpy arrays or pandas arrays
        if hasattr(o, "tolist"):
            return o.tolist()
        # datetimes etc. fall back to string
        try:
            return str(o)
        except Exception:
            return None

    safe_json = json.loads(json.dumps(records, default=_default))

    # If single record, return JSON object; otherwise return list
    if isinstance(safe_json, list) and len(safe_json) == 1:
        return JSONResponse(content=safe_json[0])
    return JSONResponse(content=safe_json)





if __name__ == "__main__":
    # Simple local runner for development: uvicorn must be installed.

    #uvicorn.run("measurement_api:app", host="0.0.0.0", port=9000, reload=True)
    uvicorn.run("measurement_api:app", host="192.168.254.142", port=8000, reload=True)