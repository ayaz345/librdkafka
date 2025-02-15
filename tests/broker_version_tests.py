#!/usr/bin/env python3
#
#
# Run librdkafka regression tests on with different SASL parameters
# and broker verisons.
#
# Requires:
#  trivup python module
#  gradle in your PATH

from cluster_testing import (
    LibrdkafkaTestCluster,
    print_report_summary,
    read_scenario_conf)
from LibrdkafkaTestApp import LibrdkafkaTestApp

import subprocess
import tempfile
import os
import sys
import argparse
import json


def test_it(version, deploy=True, conf={}, rdkconf={}, tests=None,
            interact=False, debug=False, scenario="default"):
    """
    @brief Create, deploy and start a Kafka cluster using Kafka \\p version
    Then run librdkafka's regression tests.
    """

    cluster = LibrdkafkaTestCluster(version, conf,
                                    num_brokers=int(conf.get('broker_cnt', 3)),
                                    debug=debug, scenario=scenario)

    # librdkafka's regression tests, as an App.
    _rdkconf = conf.copy()  # Base rdkconf on cluster conf + rdkconf
    _rdkconf.update(rdkconf)
    rdkafka = LibrdkafkaTestApp(cluster, version, _rdkconf, tests=tests,
                                scenario=scenario)
    rdkafka.do_cleanup = False

    if deploy:
        cluster.deploy()

    cluster.start(timeout=30)

    if conf.get('test_mode', '') == 'bash':
        cmd = 'bash --rcfile <(cat ~/.bashrc; echo \'PS1="[TRIVUP:%s@%s] \\u@\\h:\\w$ "\')' % (  # noqa: E501
            cluster.name, version)
        subprocess.call(
            cmd,
            env=rdkafka.env,
            shell=True,
            executable='/bin/bash')
        report = None

    else:
        rdkafka.start()
        print(f'# librdkafka regression tests started, logs in {rdkafka.root_path()}')
        rdkafka.wait_stopped(timeout=60 * 30)

        report = rdkafka.report()
        report['root_path'] = rdkafka.root_path()

        if report.get('tests_failed', 0) > 0 and interact:
            print(
                f'# Connect to cluster with bootstrap.servers {cluster.bootstrap_servers()}'
            )
            print('# Exiting the shell will bring down the cluster. '
                  'Good luck.')
            subprocess.call(
                'bash --rcfile <(cat ~/.bashrc; echo \'PS1="[TRIVUP:%s@%s] \\u@\\h:\\w$ "\')' %  # noqa: E501
                (cluster.name, version), env=rdkafka.env, shell=True,
                executable='/bin/bash')

    cluster.stop(force=True)

    cluster.cleanup()
    return report


def handle_report(report, version, suite):
    """ Parse test report and return tuple (Passed(bool), Reason(str)) """
    test_cnt = report.get('tests_run', 0)

    if test_cnt == 0:
        return (False, 'No tests run')

    passed = report.get('tests_passed', 0)
    failed = report.get('tests_failed', 0)
    expect_fail = 'all' in suite.get(
        'expect_fail', []
    ) or version in suite.get('expect_fail', [])
    if expect_fail:
        return (
            (True, 'All %d/%d tests failed as expected' % (failed, test_cnt))
            if failed == test_cnt
            else (
                False,
                '%d/%d tests failed: expected all to fail'
                % (failed, test_cnt),
            )
        )
    if failed > 0:
        return (False, '%d/%d tests passed: expected all to pass' %
                (passed, test_cnt))
    else:
        return (True, 'All %d/%d tests passed as expected' %
                (passed, test_cnt))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Run librdkafka tests on a range of broker versions')

    parser.add_argument('--debug', action='store_true', default=False,
                        help='Enable trivup debugging')
    parser.add_argument('--conf', type=str, dest='conf', default=None,
                        help='trivup JSON config object (not file)')
    parser.add_argument('--rdkconf', type=str, dest='rdkconf', default=None,
                        help='trivup JSON config object (not file) '
                        'for LibrdkafkaTestApp')
    parser.add_argument('--scenario', type=str, dest='scenario',
                        default='default',
                        help='Test scenario (see scenarios/ directory)')
    parser.add_argument('--tests', type=str, dest='tests', default=None,
                        help='Test to run (e.g., "0002")')
    parser.add_argument('--report', type=str, dest='report', default=None,
                        help='Write test suites report to this filename')
    parser.add_argument('--interact', action='store_true', dest='interact',
                        default=False,
                        help='On test failure start a shell before bringing '
                        'the cluster down.')
    parser.add_argument('versions', type=str, nargs='*',
                        default=['0.8.1.1', '0.8.2.2', '0.9.0.1', '2.3.0'],
                        help='Broker versions to test')
    parser.add_argument('--interactive', action='store_true',
                        dest='interactive',
                        default=False,
                        help='Start a shell instead of running tests')
    parser.add_argument(
        '--root',
        type=str,
        default=os.environ.get(
            'TRIVUP_ROOT',
            'tmp'),
        help='Root working directory')
    parser.add_argument(
        '--port',
        default=None,
        help='Base TCP port to start allocating from')
    parser.add_argument(
        '--kafka-src',
        dest='kafka_path',
        type=str,
        default=None,
        help='Path to Kafka git repo checkout (used for version=trunk)')
    parser.add_argument(
        '--brokers',
        dest='broker_cnt',
        type=int,
        default=3,
        help='Number of Kafka brokers')
    parser.add_argument('--ssl', dest='ssl', action='store_true',
                        default=False,
                        help='Enable SSL endpoints')
    parser.add_argument(
        '--sasl',
        dest='sasl',
        type=str,
        default=None,
        help='SASL mechanism (PLAIN, GSSAPI)')

    args = parser.parse_args()

    rdkconf = {}

    args.conf = json.loads(args.conf) if args.conf is not None else {}
    if args.port is not None:
        args.conf['port_base'] = int(args.port)
    if args.kafka_path is not None:
        args.conf['kafka_path'] = args.kafka_path
    if args.ssl:
        args.conf['security.protocol'] = 'SSL'
    if args.sasl:
        if args.sasl == 'PLAIN' and 'sasl_users' not in args.conf:
            args.conf['sasl_users'] = 'testuser=testpass'
        args.conf['sasl_mechanisms'] = args.sasl
        args.conf['sasl_servicename'] = 'kafka'
    if args.interactive:
        args.conf['test_mode'] = 'bash'
    args.conf['broker_cnt'] = args.broker_cnt

    conf = {}
    conf |= args.conf
    if args.rdkconf is not None:
        rdkconf |= json.loads(args.rdkconf)

    conf.update(read_scenario_conf(args.scenario))

    if args.tests is not None:
        tests = args.tests.split(',')
    elif 'tests' in conf:
        tests = conf.get('tests', '').split(',')
    else:
        tests = None

    # Test version + suite matrix
    versions = conf.get('versions', args.versions)
    suites = [{'name': 'standard'}]

    pass_cnt = 0
    fail_cnt = 0
    for version in versions:
        for suite in suites:
            _conf = conf.copy()
            _conf.update(suite.get('conf', {}))
            _rdkconf = rdkconf.copy()
            _rdkconf.update(suite.get('rdkconf', {}))

            if 'version' not in suite:
                suite['version'] = {}

            # Run tests
            print(
                f"#### Version {version}, suite {suite['name']}, scenario {args.scenario}: STARTING"
            )
            report = test_it(version, tests=tests, conf=_conf,
                             rdkconf=_rdkconf,
                             interact=args.interact, debug=args.debug,
                             scenario=args.scenario)

            if not report:
                continue

            # Handle test report
            report['version'] = version
            passed, reason = handle_report(report, version, suite)
            report['PASSED'] = passed
            report['REASON'] = reason

            if passed:
                print('\033[42m#### Version %s, suite %s: PASSED: %s\033[0m' %
                      (version, suite['name'], reason))
                pass_cnt += 1
            else:
                print('\033[41m#### Version %s, suite %s: FAILED: %s\033[0m' %
                      (version, suite['name'], reason))
                fail_cnt += 1

                # Emit hopefully relevant parts of the log on failure
                subprocess.call(
                    f"grep --color=always -B100 -A10 FAIL {os.path.join(report['root_path'], 'stderr.log')}",
                    shell=True,
                )

            print(f"#### Test output: {report['root_path']}/stderr.log")

            suite['version'][version] = report

    # Write test suite report JSON file
    if args.report is not None:
        test_suite_report_file = args.report
        f = open(test_suite_report_file, 'w')
    else:
        fd, test_suite_report_file = tempfile.mkstemp(prefix='test_suite_',
                                                      suffix='.json',
                                                      dir='.')
        f = os.fdopen(fd, 'w')

    full_report = {'suites': suites, 'pass_cnt': pass_cnt,
                   'fail_cnt': fail_cnt, 'total_cnt': pass_cnt + fail_cnt}

    f.write(json.dumps(full_report))
    f.close()

    print('\n\n\n')
    print_report_summary(full_report)
    print(f'#### Full test suites report in: {test_suite_report_file}')

    if pass_cnt == 0 or fail_cnt > 0:
        sys.exit(1)
    else:
        sys.exit(0)
