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

    return {}

    # TODO: implement filtering for ring alerts 
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

    


@app.get("/network_stats_packets_over_time")
def network_stats_packets_over_time():
    """
    Return network stats DataFrame grouped by time (monthly) and number of packets as JSON (list of records).
    If `dataset` is omitted and exactly one dataset exists, it will be selected automatically.
    Use `limit` to restrict rows.
    """
    feather_path = os.path.join(_PARSED_ROOT, "df_packets_over_time.feather")
    df = pd.read_feather(feather_path)

    records = df.to_dict(orient="records")
    return jsonable_encoder(records)


@app.get("/network_stats_number_of_packets")
def network_stats_number_of_packets():
    """
    Return network stats DataFrame grouped by number of packets as JSON (list of records).
    If `dataset` is omitted and exactly one dataset exists, it will be selected automatically.
    Use `limit` to restrict rows.
    """
    feather_path = os.path.join(_PARSED_ROOT, "df_packets.feather")
    df = pd.read_feather(feather_path)
 
    records = df.to_dict(orient="records")
    return jsonable_encoder(records)


@app.get("/network_stats_number_of_jobs_per_month")
def network_stats_number_of_jobs_per_month():
    """
    Return network stats DataFrame grouped by number of jobs per month as JSON (list of records).
    If `dataset` is omitted and exactly one dataset exists, it will be selected automatically.
    Use `limit` to restrict rows.
    """
    feather_path = os.path.join(_PARSED_ROOT, "df_jobs_per_month.feather")
    df = pd.read_feather(feather_path)
    
    records = df.to_dict(orient="records")
    return jsonable_encoder(records)

@app.get("/clients_geojson")
def clients_geojson(
    sensor: Optional[str] = Query(None, description="Specific sensor name to get GeoJSON for. If omitted, returns all available sensor files as a combined FeatureCollection."),
    list_files: bool = Query(False, description="If true, returns a list of available GeoJSON files instead of the actual data.")
):
    """
    Return sensor GeoJSON data as JSON. Can return data for a specific sensor, all sensors combined, or list available files.
    
    Parameters:
    - sensor: Specific sensor name (without file extension) to get GeoJSON for
    - list_files: If true, returns list of available files instead of GeoJSON data
    """
    sensor_geojson_dir = os.path.join(_PARSED_ROOT, "sensor_geojson")
    
    if not os.path.exists(sensor_geojson_dir):
        raise HTTPException(status_code=404, detail=f"Sensor GeoJSON directory not found at {sensor_geojson_dir}")
    
    # Get list of available GeoJSON files
    available_files = [f for f in os.listdir(sensor_geojson_dir) if f.endswith('.geojson')]
    
    if list_files:
        # Return list of available files with metadata
        file_info = []
        for filename in sorted(available_files):
            file_path = os.path.join(sensor_geojson_dir, filename)
            file_size = os.path.getsize(file_path)
            sensor_name = filename.replace('_coverage_clean.geojson', '').replace('_coverage.geojson', '')
            file_info.append({
                "filename": filename,
                "sensor_name": sensor_name,
                "file_size_bytes": file_size,
                "file_size_kb": round(file_size / 1024, 1)
            })
        return jsonable_encoder({"available_files": file_info, "total_count": len(file_info)})
    
    if sensor:
        # Return specific sensor GeoJSON
        # Try different filename patterns
        possible_filenames = [
            f"{sensor}_coverage_clean.geojson",
            f"{sensor}_coverage.geojson",
            f"{sensor}.geojson"
        ]
        
        geojson_path = None
        for filename in possible_filenames:
            potential_path = os.path.join(sensor_geojson_dir, filename)
            if os.path.exists(potential_path):
                geojson_path = potential_path
                break
        
        if not geojson_path:
            available_sensors = [f.replace('_coverage_clean.geojson', '').replace('_coverage.geojson', '') 
                               for f in available_files]
            raise HTTPException(
                status_code=404, 
                detail=f"GeoJSON file not found for sensor '{sensor}'. Available sensors: {sorted(set(available_sensors))}"
            )
        
        with open(geojson_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return jsonable_encoder(data)
    
    else:
        # Return all sensors combined into one FeatureCollection
        if not available_files:
            raise HTTPException(status_code=404, detail="No GeoJSON files found in sensor directory")
        
        combined_features = []
        for filename in sorted(available_files):
            file_path = os.path.join(sensor_geojson_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if data.get("type") == "FeatureCollection" and "features" in data:
                        combined_features.extend(data["features"])
                    elif data.get("type") == "Feature":
                        combined_features.append(data)
            except Exception as e:
                # Skip files that can't be loaded but don't fail completely
                continue
        
        combined_geojson = {
            "type": "FeatureCollection",
            "features": combined_features,
            "metadata": {
                "total_sensors": len(combined_features),
                "source_files": len(available_files),
                "description": "Combined sensor coverage areas from all available sensors"
            }
        }
        
        return jsonable_encoder(combined_geojson)


@app.get("/clients")
def clients():
    feather_path = os.path.join(_PARSED_ROOT, "clients.feather")
    df = pd.read_feather(feather_path)
    # Convert binary _id to string and handle numpy arrays
    df_tst_clean = df.copy()
    if '_id' in df_tst_clean.columns:
        df_tst_clean['_id'] = df_tst_clean['_id'].apply(lambda x: x.hex() if isinstance(x, bytes) else str(x))


    # Truncate coordinates (status_location_lat, status_location_lon) to 2 decimals for privacy
    for col in ['status_location_lat', 'status_location_lon']:
        if col in df_tst_clean.columns:
            # coerce to numeric (non-numeric become NaN), then truncate instead of round
            df_tst_clean[col] = pd.to_numeric(df_tst_clean[col], errors='coerce')
            df_tst_clean[col] = np.trunc(df_tst_clean[col] * 100) / 100.0

    # Convert to records and handle numpy arrays
    records = df_tst_clean.to_dict(orient="records")

    # Convert numpy arrays to lists for JSON serialization
    for record in records:
        for key, value in record.items():
            if hasattr(value, 'tolist'):  # Check if it's a numpy array
                record[key] = value.tolist()

    return jsonable_encoder(records)


if __name__ == "__main__":
    # Simple local runner for development: uvicorn must be installed.

    #uvicorn.run("measurement_api:app", host="0.0.0.0", port=9000, reload=True)
    uvicorn.run("measurement_api:app", host="192.168.254.142", port=8000, reload=True)