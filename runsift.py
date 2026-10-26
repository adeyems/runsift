"""Compare local synthetic CI-run bundles. Python 3.10+, standard library only."""
import argparse
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 2 * 1024 * 1024
STATUSES = {'passed', 'failed', 'skipped', 'cancelled'}


def exact_fields(value, names, context):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError(f'{context} must contain exactly: {", ".join(names)}')


def identifier(value, context):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise ValueError(f'{context} must be 1–128 ASCII letters, digits, dots, hyphens or underscores, starting with a letter or digit')


def validate(bundle):
    exact_fields(bundle, ('version', 'run_id', 'jobs'), 'Bundle')
    if type(bundle['version']) is not int or bundle['version'] != 1:
        raise ValueError('Unsupported bundle version; expected integer 1')
    identifier(bundle['run_id'], 'run_id')
    if not isinstance(bundle['jobs'], list) or len(bundle['jobs']) > 1000:
        raise ValueError('jobs must be a list of at most 1000 jobs')
    seen = set()
    for job in bundle['jobs']:
        exact_fields(job, ('id', 'status', 'duration_ms'), 'Job')
        identifier(job['id'], 'Job id')
        if job['id'] in seen:
            raise ValueError('Duplicate job id')
        seen.add(job['id'])
        if not isinstance(job['status'], str) or job['status'] not in STATUSES:
            raise ValueError('Job status must be passed, failed, skipped or cancelled')
        duration = job['duration_ms']
        if type(duration) is not int or not 0 <= duration <= 604_800_000:
            raise ValueError('duration_ms must be an integer from 0 to 604800000 (7 days)')
    return bundle


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError('Non-finite JSON numbers are not supported')

    with Path(path).open('rb') as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Bundle exceeds 2 MiB')
    try:
        bundle = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('Bundle must be valid UTF-8 JSON without excessive nesting') from None
    return validate(bundle)


def validate_thresholds(duration_threshold_ms, duration_threshold_percent):
    for value, name, upper in [(duration_threshold_ms, 'duration_threshold_ms', 604_800_000),
                               (duration_threshold_percent, 'duration_threshold_percent', 10000)]:
        if type(value) is not int or not 0 <= value <= upper:
            raise ValueError(f'{name} must be an integer from 0 to {upper}')


def compare(baseline, candidate, duration_threshold_ms=0, duration_threshold_percent=0):
    validate_thresholds(duration_threshold_ms, duration_threshold_percent)
    validate(baseline)
    validate(candidate)
    old = {job['id']: job for job in baseline['jobs']}
    new = {job['id']: job for job in candidate['jobs']}
    jobs = []
    counts = dict(added=0, removed=0, changed=0, unchanged=0, regressions=0, recoveries=0)
    for name in sorted(old.keys() | new.keys()):
        before, after = old.get(name), new.get(name)
        delta = after['duration_ms'] - before['duration_ms'] if before and after else None
        significant = (abs(delta) > duration_threshold_ms and
                       abs(delta) * 100 > before['duration_ms'] * duration_threshold_percent) if delta is not None else None
        change = ('added' if before is None else 'removed' if after is None else
                  'changed' if before['status'] != after['status'] or significant else 'unchanged')
        regression = before is not None and after is not None and before['status'] == 'passed' and after['status'] != 'passed'
        recovery = before is not None and after is not None and before['status'] != 'passed' and after['status'] == 'passed'
        counts[change] += 1
        counts['regressions'] += int(regression)
        counts['recoveries'] += int(recovery)
        jobs.append({'id': name, 'change': change,
                     'baseline_status': before['status'] if before else None,
                     'candidate_status': after['status'] if after else None,
                     'baseline_duration_ms': before['duration_ms'] if before else None,
                     'candidate_duration_ms': after['duration_ms'] if after else None,
                     'duration_delta_ms': delta,
                     'duration_change_exceeds_thresholds': significant,
                     'duration_change_ignored': delta != 0 and not significant if delta is not None else None,
                     'status_regression': regression, 'status_recovery': recovery})
    return {'version': 1, 'baseline_run_id': baseline['run_id'], 'candidate_run_id': candidate['run_id'],
            'match': not any(counts[key] for key in ('added', 'removed', 'changed')),
            'comparison_rules': {'duration_threshold_ms': duration_threshold_ms,
                                 'duration_threshold_percent': duration_threshold_percent,
                                 'duration_rule': 'absolute_delta_strictly_exceeds_both'},
            'summary': counts, 'jobs': jobs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline')
    parser.add_argument('candidate')
    parser.add_argument('--duration-threshold-ms', type=int, default=0,
                        help='Ignore timing deltas at or below this many ms (default 0)')
    parser.add_argument('--duration-threshold-percent', type=int, default=0,
                        help='Ignore timing deltas at or below this integer percent of baseline (default 0)')
    args = parser.parse_args(argv)
    try:
        validate_thresholds(args.duration_threshold_ms, args.duration_threshold_percent)
        result = compare(load(args.baseline), load(args.candidate),
                         args.duration_threshold_ms, args.duration_threshold_percent)
    except (ValueError, OSError, RecursionError) as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['match'] else 1


if __name__ == '__main__':
    sys.exit(main())
