#!/usr/bin/env python3

import sys

if len(sys.argv) != 2:
    raise Exception(f'Usage: {sys.argv[0]} path/to/rdkafka.h')

kafka_h_file = sys.argv[1]
with open(kafka_h_file) as f:
    for line in f:
        if '#define RD_KAFKA_VERSION' in line:
            version = line.split()[-1]
            break
major = int(version[2:4], 16)
minor = int(version[4:6], 16)
patch = int(version[6:8], 16)
version = '.'.join(str(item) for item in (major, minor, patch))

print(version)
