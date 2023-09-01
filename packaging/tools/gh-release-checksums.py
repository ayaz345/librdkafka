#!/usr/bin/env python3
#
# Calculate checksums for GitHub release artifacts/assets.
#
# Use the direct links rather than getting the tarball URLs from
# the GitHub API since the latter uses the git-sha1 rather than the tag
# in its zipped up content, causing checksum mismatches.
#

import sys
import requests
import hashlib


if __name__ == '__main__':

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <tag>")
        sys.exit(1)

    tag = sys.argv[1]

    print("## Checksums")
    print("Release asset checksums:")

    for ftype in ["zip", "tar.gz"]:
        url = f"https://github.com/edenhill/librdkafka/archive/{tag}.{ftype}"

        h = hashlib.sha256()

        r = requests.get(url, stream=True)
        while True:
            buf = r.raw.read(100 * 1000)
            if len(buf) == 0:
                break
            h.update(buf)

        print(f" * {tag}.{ftype} SHA256 `{h.hexdigest()}`")
