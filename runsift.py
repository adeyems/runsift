"""Compare local synthetic CI-run bundles. Python 3.10+, standard library only."""
import argparse
import hashlib
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
    total_tests = 0
    for job in bundle['jobs']:
        if not isinstance(job, dict) or not {'id', 'status', 'duration_ms'} <= job.keys() or job.keys() - {'id', 'status', 'duration_ms', 'tests', 'log_excerpt'}:
            raise ValueError('Job requires id, status, duration_ms; optional tests and log_excerpt')
        identifier(job['id'], 'Job id')
        if job['id'] in seen:
            raise ValueError('Duplicate job id')
        seen.add(job['id'])
        if not isinstance(job['status'], str) or job['status'] not in STATUSES:
            raise ValueError('Job status must be passed, failed, skipped or cancelled')
        duration = job['duration_ms']
        if type(duration) is not int or not 0 <= duration <= 604_800_000:
            raise ValueError('duration_ms must be an integer from 0 to 604800000 (7 days)')
        if 'log_excerpt' in job:
            excerpt = job['log_excerpt']
            if not isinstance(excerpt, str) or len(excerpt.encode('utf-8')) > 4096 or any((ord(c) < 32 and c not in '\n\t') or 127 <= ord(c) <= 159 for c in excerpt):
                raise ValueError('log_excerpt requires at most 4096 UTF-8 bytes without terminal control characters')
        if 'tests' in job:
            if not isinstance(job['tests'], list):
                raise ValueError('tests must be a list when provided')
            total_tests += len(job['tests'])
            if total_tests > 10000:
                raise ValueError('Bundle exceeds 10000 test cases')
            test_ids = set()
            for case in job['tests']:
                exact_fields(case, ('id', 'status'), 'Test case')
                identifier(case['id'], 'Test id')
                if case['id'] in test_ids:
                    raise ValueError('Duplicate test id within job')
                test_ids.add(case['id'])
                if not isinstance(case['status'], str) or case['status'] not in STATUSES:
                    raise ValueError('Test status must be passed, failed, skipped or cancelled')
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


def compare_tests(before, after):
    # Missing test data on an existing job is unknown, not an empty test suite.
    coverage = {'baseline_provided': before is not None and 'tests' in before,
                'candidate_provided': after is not None and 'tests' in after}
    old = before.get('tests') if before is not None else []
    new = after.get('tests') if after is not None else []
    if old is None or new is None:
        return {'state': 'unavailable' if not any(coverage.values()) else 'coverage_changed',
                **coverage,
                'match': None, 'summary': None, 'cases': []}
    left = {case['id']: case['status'] for case in old}
    right = {case['id']: case['status'] for case in new}
    cases = []
    counts = dict(added=0, removed=0, changed=0, unchanged=0, newly_failing=0, recovered=0)
    for name in sorted(left.keys() | right.keys()):
        a, b = left.get(name), right.get(name)
        change = 'added' if a is None else 'removed' if b is None else 'unchanged' if a == b else 'changed'
        # Added failures are visible as added, not falsely called transitions.
        failing = a is not None and a != 'failed' and b == 'failed'
        recovered = a == 'failed' and b == 'passed'
        counts[change] += 1
        counts['newly_failing'] += int(failing)
        counts['recovered'] += int(recovered)
        cases.append({'id': name, 'change': change, 'baseline_status': a, 'candidate_status': b,
                      'newly_failing': failing, 'recovered': recovered})
    return {'state': 'compared', **coverage,
            'match': not any(counts[k] for k in ('added', 'removed', 'changed')),
            'summary': counts, 'cases': cases}


def failure_groups(bundle):
    groups = {}
    unavailable = []
    for job in bundle['jobs']:
        if job['status'] != 'failed':
            continue
        excerpt = job.get('log_excerpt')
        if not excerpt:
            unavailable.append(job['id'])
            continue
        fingerprint = hashlib.sha256(excerpt.encode('utf-8')).hexdigest()
        groups.setdefault(fingerprint, []).append(job['id'])
    return {'groups': [{'sha256': key, 'job_ids': sorted(ids)} for key, ids in sorted(groups.items())],
            'without_excerpt': sorted(unavailable), 'method': 'exact_utf8_sha256'}


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
        tests = compare_tests(before, after)
        delta = after['duration_ms'] - before['duration_ms'] if before and after else None
        significant = (abs(delta) > duration_threshold_ms and
                       abs(delta) * 100 > before['duration_ms'] * duration_threshold_percent) if delta is not None else None
        change = ('added' if before is None else 'removed' if after is None else
                  'changed' if before['status'] != after['status'] or significant or
                  tests['state'] == 'coverage_changed' or tests['match'] is False else 'unchanged')
        regression = before is not None and after is not None and before['status'] == 'passed' and after['status'] != 'passed'
        recovery = before is not None and after is not None and before['status'] != 'passed' and after['status'] == 'passed'
        counts[change] += 1
        counts['regressions'] += int(regression)
        counts['recoveries'] += int(recovery)
        jobs.append({'id': name, 'change': change,
                     'tests': tests,
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
            'summary': counts, 'jobs': jobs,
            'failure_groups': {'baseline': failure_groups(baseline), 'candidate': failure_groups(candidate)}}


def load_profile(path):
    with Path(path).open('rb') as source:
        raw = source.read(4097)
    if len(raw) > 4096:
        raise ValueError('Profile exceeds 4 KiB')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate profile key')
            result[key] = value
        return result
    profile = json.loads(raw, object_pairs_hook=unique)
    exact_fields(profile, ('version', 'duration_threshold_ms', 'duration_threshold_percent'), 'Profile')
    if type(profile['version']) is not int or profile['version'] != 1:
        raise ValueError('Unsupported profile version')
    validate_thresholds(profile['duration_threshold_ms'], profile['duration_threshold_percent'])
    return profile


def save_profile(path, ms, percent):
    validate_thresholds(ms, percent)
    with Path(path).open('x', encoding='utf-8') as output:
        json.dump({'version': 1, 'duration_threshold_ms': ms, 'duration_threshold_percent': percent}, output, indent=2)


def archive_bundle(source, directory):
    bundle = load(source)
    # run_id validation excludes separators; fixed suffix makes dot IDs harmless.
    destination = Path(directory) / (bundle['run_id'] + '.json')
    encoded = json.dumps(bundle, ensure_ascii=False, indent=2).encode('utf-8')
    if len(encoded) > MAX_BYTES:
        raise ValueError('Canonical archived bundle exceeds 2 MiB')
    with destination.open('xb') as output:
        output.write(encoded)
    return destination


def trend(bundles):
    """Ordered local observations, not an inference of flakiness or chronology."""
    if not 2 <= len(bundles) <= 20:
        raise ValueError('History requires 2–20 bundles in explicit oldest-to-newest order')
    for bundle in bundles:
        validate(bundle)
    ids = [b['run_id'] for b in bundles]
    if len(ids) != len(set(ids)):
        raise ValueError('History run IDs must be distinct')
    index = [{j['id']: j for j in b['jobs']} for b in bundles]
    jobs = []
    for name in sorted(set().union(*(j.keys() for j in index))):
        observations = [run.get(name) for run in index]
        states = [j['status'] if j else None for j in observations]
        durations = [j['duration_ms'] for j in observations if j]
        transitions = sum(a is not None and b is not None and a != b for a,b in zip(states, states[1:]))
        jobs.append({'id': name, 'statuses': states, 'observed_runs': len(durations),
                     'missing_runs': len(bundles)-len(durations), 'adjacent_status_changes': transitions,
                     'failed_runs': states.count('failed'), 'duration_min_ms': min(durations),
                     'duration_max_ms': max(durations)})
    return {'version': 1, 'run_ids': ids, 'ordering': 'caller_supplied', 'jobs': jobs,
            'scope': 'descriptive observations only; missing runs break transition counting; no flakiness verdict'}


def render_text(report):
    """Plain text from validated identifiers; raw log excerpts never appear."""
    lines = [f"RunSift: {report['baseline_run_id']} -> {report['candidate_run_id']}",
             'MATCH' if report['match'] else 'DIFFERENT']
    rules = report['comparison_rules']
    lines.append(f"Duration thresholds: {rules['duration_threshold_ms']} ms and {rules['duration_threshold_percent']}% (both must be exceeded)")
    for job in report['jobs']:
        delta = job['duration_delta_ms']
        timing = 'n/a' if delta is None else f'{delta:+d} ms'
        if job['duration_change_ignored']:
            timing += ' (within thresholds)'
        lines.append(f"{job['id']}: {job['change']}; {job['baseline_status'] or 'absent'} -> {job['candidate_status'] or 'absent'}; duration {timing}")
        tests = job['tests']
        lines.append(f"  tests: {tests['state']}")
        for case in tests['cases']:
            if case['change'] != 'unchanged':
                lines.append(f"  {case['id']}: {case['baseline_status'] or 'absent'} -> {case['candidate_status'] or 'absent'}")
    for side, groups in report['failure_groups'].items():
        lines.append(f"{side}: {len(groups['groups'])} exact-log failure groups; {len(groups['without_excerpt'])} failed jobs without excerpts")
    return '\n'.join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'archive':
        try:
            if len(argv) != 3:
                raise ValueError('Usage: runsift archive BUNDLE.json EXISTING_DIRECTORY')
            path = archive_bundle(argv[1], argv[2])
        except (ValueError, OSError, RecursionError) as error:
            print(json.dumps({'error': str(error)}), file=sys.stderr)
            return 2
        print(json.dumps({'archived': str(path)}))
        return 0
    if argv and argv[0] == 'history':
        try:
            if not 2 <= len(argv[1:]) <= 20:
                raise ValueError('History requires 2–20 bundle paths')
            result = trend([load(path) for path in argv[1:]])
        except (ValueError, OSError, RecursionError) as error:
            print(json.dumps({'error': str(error)}), file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    parser.add_argument('baseline')
    parser.add_argument('candidate')
    parser.add_argument('--duration-threshold-ms', type=int, default=None,
                        help='Ignore timing deltas at or below this many ms (default 0)')
    parser.add_argument('--duration-threshold-percent', type=int, default=None,
                        help='Ignore timing deltas at or below this integer percent of baseline (default 0)')
    parser.add_argument('--profile', help='Load versioned duration settings; conflicts with explicit thresholds')
    parser.add_argument('--save-profile', help='Save effective settings to a new file after validating inputs')
    args = parser.parse_args(argv)
    try:
        if args.profile:
            if args.duration_threshold_ms is not None or args.duration_threshold_percent is not None:
                raise ValueError('Cannot combine profile with explicit thresholds')
            settings = load_profile(args.profile)
            args.duration_threshold_ms = settings['duration_threshold_ms']
            args.duration_threshold_percent = settings['duration_threshold_percent']
        else:
            args.duration_threshold_ms = args.duration_threshold_ms or 0
            args.duration_threshold_percent = args.duration_threshold_percent or 0
        validate_thresholds(args.duration_threshold_ms, args.duration_threshold_percent)
        result = compare(load(args.baseline), load(args.candidate),
                         args.duration_threshold_ms, args.duration_threshold_percent)
        if args.save_profile:
            save_profile(args.save_profile, args.duration_threshold_ms, args.duration_threshold_percent)
    except (ValueError, OSError, RecursionError) as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 2
    print(render_text(result) if args.format == 'text' else json.dumps(result, indent=2))
    return 0 if result['match'] else 1


if __name__ == '__main__':
    sys.exit(main())
