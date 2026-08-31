$ErrorActionPreference = 'Stop'

if (-not (Get-Command snow -ErrorAction SilentlyContinue)) {
  throw "Snowflake CLI 'snow' not found on PATH. Install/configure Snowflake CLI, or run regulens-demo.sql in Snowsight."
}

$sqlFile = Join-Path $PSScriptRoot 'regulens-demo.sql'
if (-not (Test-Path $sqlFile)) {
  # fallback if files are in repo/workspace root
  $sqlFile = Join-Path (Get-Location) 'regulens-demo.sql'
}

if (-not (Test-Path $sqlFile)) {
  throw "Could not find regulens-demo.sql next to this script or in current directory."
}

# Uses your default Snowflake CLI connection/context.
# If you have multiple connections, you can set SNOWFLAKE_CONNECTIONS / use `snow connection set-default`.
snow sql -f "$sqlFile"
