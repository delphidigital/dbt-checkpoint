import argparse
import os
import re
import time
from typing import Any, Dict, Optional, Sequence

from dbt_checkpoint.tracking import dbtCheckpointTracking
from dbt_checkpoint.utils import (
    JsonOpenError,
    add_catalog_args,
    add_default_args,
    get_filenames,
    get_json,
    get_models,
    red,
    yellow,
)


def check_column_name_contract(
    paths: Sequence[str],
    pattern: str,
    dtype: str,
    catalog: Dict[str, Any],
    pattern_flg: bool = False,
    col_name_ignore: str = '',
) -> Dict[str, Any]:
    status_code = 0
    sqls = get_filenames(paths, [".sql"])
    filenames = set(sqls.keys())
    models = get_models(catalog, filenames)
    dtype = re.split(r', | (?!.*?, )|,|\|', dtype)
    dtype = [t.lower() for t in dtype]
    dtype_upper = [t.upper() for t in dtype]
    col_name_ignore = re.split(r', | (?!.*?, )|,|\|', col_name_ignore)
    col_name_ignore = [c.lower() for c in col_name_ignore]

    for model in models:
        for col in model.node.get("columns", []).values():
            col_name = col.get("name").lower()
            col_type = col.get("type").lower()

            # Check all files of type dtype follow naming pattern
            if col_type in dtype:
                if col_name not in col_name_ignore and re.match(pattern, col_name, re.IGNORECASE) is None and not pattern_flg:
                    status_code = 1
                    print(
                        f"{red(col_name)}: column is of type {yellow(dtype_upper)} and "
                        f"does not match regex pattern {yellow(pattern)}."
                    )

            # Check all files with naming pattern are of type dtype
            elif col_name not in col_name_ignore and re.match(pattern, col_name, re.IGNORECASE):
                status_code = 1
                print(
                    f"{red(col_name)}: name matches regex pattern {yellow(pattern)} "
                    f"and is of type {yellow(col_type)} instead of {yellow(dtype_upper)}."
                )

    return {"status_code": status_code}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    add_default_args(parser)
    add_catalog_args(parser)

    parser.add_argument(
        "--pattern",
        type=str,
        required=True,
        help="Regex pattern to match column names.",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        required=True,
        help="Expected data type(s) for the matching columns.",
    )
    parser.add_argument(
        "--pattern_flg",
        type=bool,
        required=False,
        help="Set to true if you only want to check a column name adheres to a data type.",
        default=False,
    )
    parser.add_argument(
        "--col_name_ignore",
        type=str,
        required=False,
        help="Pass a column name to ignore the data type check.",
        default='',
    )

    args = parser.parse_args(argv)

    try:
        manifest = get_json(args.manifest)
    except JsonOpenError as e:
        print(f"Unable to load manifest file ({e})")
        return 1

    try:
        catalog = get_json(args.catalog)
    except JsonOpenError as e:
        print(f"Unable to load catalog file ({e})")
        return 1

    start_time = time.time()
    hook_properties = check_column_name_contract(
        paths=args.filenames,
        pattern=args.pattern,
        dtype=args.dtype,
        catalog=catalog,
        pattern_flg=args.pattern_flg,
        col_name_ignore=args.col_name_ignore,
    )

    end_time = time.time()

    script_args = vars(args)

    tracker = dbtCheckpointTracking(script_args=script_args)
    tracker.track_hook_event(
        event_name="Hook Executed",
        manifest=manifest,
        event_properties={
            "hook_name": os.path.basename(__file__),
            "description": "Check column name abides to contract.",
            "status": hook_properties.get("status_code"),
            "execution_time": end_time - start_time,
            "is_pytest": script_args.get("is_test"),
        },
    )

    return hook_properties.get("status_code")


if __name__ == "__main__":
    exit(main())
