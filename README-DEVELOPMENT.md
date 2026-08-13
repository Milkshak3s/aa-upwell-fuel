# Development

## Layout

```
upwellfuel/
  auth_hooks.py        menu + url hooks; the only Auth integration points
  urls.py views.py     the page and its CSV export
  app_settings.py      overridable settings
  fuel/
    catalog.py         static EVE reference data (no Django imports)
    calc.py            the arithmetic (no Django imports, no ORM)
    report.py          turns aa-structures rows into projections
  templates/           the page
  tests/
testauth/              minimal Auth project used by the test suite
```

`catalog.py` and `calc.py` deliberately import nothing from Django, so the fuel
maths can be tested and reasoned about on its own. `report.py` is the only file
that touches aa-structures' models, and it only ever reads attributes — which is
why `tests/test_report.py` can drive it with stand-in objects rather than
fixtures.

## Running the tests

The arithmetic tests need nothing but Python:

```bash
python -m unittest discover -s upwellfuel/tests -t .
```

The full suite needs Alliance Auth, aa-structures and a Redis:

```bash
pip install -e .
pip install aa-structures
AA_TEST_REDIS=redis://127.0.0.1:6379/15 python runtests.py
```

Redis is not optional even under test: Auth's task statistics call
`django_redis.get_redis_connection()` directly, and the stub they fall back to
only catches Redis's own errors, not a locmem backend refusing the call. Point
`AA_TEST_REDIS` at any spare database.

If a local install is awkward, the suite also runs inside a container built from
your deployed Auth image, which has every dependency at the exact version
production uses:

```bash
kubectl run upwellfuel-test --image=<your-auth-image> --restart=Never --command -- sleep 3600
tar czf - --exclude=__pycache__ upwellfuel testauth runtests.py | \
  kubectl exec -i upwellfuel-test -- sh -c 'mkdir -p /tmp/proj && tar xzf - -C /tmp/proj'
kubectl exec upwellfuel-test -- sh -c \
  'cd /tmp/proj && AA_TEST_REDIS=redis://redis:6379/15 python runtests.py'
kubectl delete pod upwellfuel-test
```

## Checking against real structures

The measured rates this app relies on can be sanity-checked against a live
install without deploying anything, by pointing a shell at the same code:

```python
from structures.models import Structure
from upwellfuel.fuel.report import build_report

report = build_report(Structure.objects.all(), period_days=30, magmatic_gas_per_hour=55.0)
for row in report.rows:
    print(row.name, row.blocks_per_day, row.projection.rate_source)
```

Structures with the same hull and the same services should agree to within about
a percent. A row that disagrees is worth investigating before trusting the
catalog for it.

## Formatting

```bash
black upwellfuel/ && isort upwellfuel/ && flake8 upwellfuel/
```

## Releasing

`bump_and_deploy.sh` bumps the patch version, builds, uploads to TestPyPI and
pushes. `deploy_prod.sh` builds the current version and uploads to PyPI.
