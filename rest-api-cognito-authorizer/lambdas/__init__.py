import os
import sys


class _DynamicPackagePath(list):
    def __iter__(self):
        seen = set()
        for entry in super().__iter__():
            if entry not in seen:
                seen.add(entry)
                yield entry
        for entry in sys.path:
            candidate = os.path.join(entry, "lambdas")
            if os.path.isdir(candidate) and candidate not in seen:
                seen.add(candidate)
                yield candidate


__path__ = _DynamicPackagePath(__path__)
