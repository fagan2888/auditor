# mypy: warn_unreachable = False

import argparse
import glob
import json
import sys
import os

from dp.ms import pretty_ms
from dp.run import run, load_students, load_areas
from dp.stringify import summarize
from dp.audit import ResultMsg, EstimateMsg, NoAuditsCompletedMsg, ProgressMsg, Arguments


def main() -> int:  # noqa: C901
    DEFAULT_DIR = os.getenv('DP_STUDENT_DIR', default=max(glob.iglob(os.path.expanduser('~/2019-*'))))

    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--workers', help="the number of worker processes to spawn", default=os.cpu_count())
    parser.add_argument('--dir', default=DEFAULT_DIR)
    parser.add_argument('--areas-dir', default=os.path.expanduser('~/Projects/degreepath-areas'))
    parser.add_argument("--transcript", action='store_true')
    parser.add_argument("--invocation", action='store_true')
    parser.add_argument("-q", "--quiet", action='store_true')
    parser.add_argument("--paths", dest='show_paths', action='store_const', const=True, default=True)
    parser.add_argument("--no-paths", dest='show_paths', action='store_const', const=False)
    parser.add_argument("--ranks", dest='show_ranks', action='store_const', const=True, default=True)
    parser.add_argument("--no-ranks", dest='show_ranks', action='store_const', const=False)
    parser.add_argument("--table", action='store_true')
    parser.add_argument("-n", default=1, type=int)

    cli_args = parser.parse_args()

    # deduplicate, then duplicate if requested
    data = sorted(set(tuple(stnum_code.strip().split()) for stnum_code in sys.stdin)) * cli_args.n

    if not data:
        print('expects a list of "stnum catalog-year areacode" to stdin', file=sys.stderr)
        return 1

    if cli_args.table:
        print('stnum,catalog,area_code,gpa,rank,max', flush=True)

    for stnum, catalog, area_code in data:
        student_file = os.path.join(cli_args.dir, f"{stnum}.json")
        area_file = os.path.join(cli_args.areas_dir, catalog, f"{area_code}.yaml")

        args = Arguments(print_all=False, transcript_only=cli_args.transcript)

        if cli_args.invocation:
            print(f"python3 dp.py --student '{student_file}' --area '{area_file}'")
            continue

        student = load_students(student_file)[0]
        area_spec = load_areas(area_file)[0]

        if not cli_args.quiet and not cli_args.table:
            print(f"auditing #{student['stnum']} against {area_file}", file=sys.stderr)

        try:
            for msg in run(args, area_spec=area_spec, student=student):
                if isinstance(msg, NoAuditsCompletedMsg):
                    print('no audits completed', file=sys.stderr)
                    return 2

                elif isinstance(msg, EstimateMsg):
                    print("estimate completed", file=sys.stderr)

                elif isinstance(msg, ProgressMsg):
                    if not cli_args.quiet:
                        avg_iter_time = pretty_ms(msg.avg_iter_ms, format_sub_ms=True)
                        print(f"{msg.iters:,} at {avg_iter_time} per audit (best: {msg.best_rank})", file=sys.stderr)

                elif isinstance(msg, ResultMsg):
                    result = json.loads(json.dumps(msg.result.to_dict()))
                    if cli_args.table:
                        avg_iter_time = pretty_ms(msg.avg_iter_ms, format_sub_ms=True)
                        print(','.join([
                            stnum,
                            catalog,
                            area_code,
                            str(round(float(result['gpa']), 2)),
                            str(round(float(result['rank']), 2)),
                            str(round(float(result['max_rank']))),
                        ]), flush=True)
                    else:
                        print("\n" + "".join(summarize(
                            result=result,
                            transcript=msg.transcript,
                            count=msg.iters,
                            avg_iter_ms=msg.avg_iter_ms,
                            elapsed=pretty_ms(msg.elapsed_ms),
                            show_paths=cli_args.show_paths,
                            show_ranks=cli_args.show_ranks,
                            claims=msg.result.keyed_claims(),
                        )))

                else:
                    if not cli_args.quiet:
                        print('unknown message %s' % msg, file=sys.stderr)
                    return 1

        except Exception as ex:
            print(f"error during audit of #{student['stnum']} against {area_file}", file=sys.stderr)
            print(ex, file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
