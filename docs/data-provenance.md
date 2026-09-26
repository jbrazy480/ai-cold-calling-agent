# Bundled NPA timezone data

`coldcaller/assets/npa_timezones.json` is derived from the timezone prefix data in
[python-phonenumbers](https://github.com/daviddrysdale/python-phonenumbers), version
9.0.40, derived from Google's libphonenumber project.

Copyright (C) 2011-2026 The Libphonenumber Authors.
Licensed under the Apache License, Version 2.0. A copy is included in
[LICENSE-phonenumbers.txt](LICENSE-phonenumbers.txt). This data is provided without
warranties. The repository's MIT license applies to original starter code.

The transformation groups geographic prefix records by their first three NANP
area-code digits, filters US/Canada candidates, and unions the timezone sets.
The generated file contains 415 NPA entries. It deliberately retains all candidate
zones, including conservative extras inherited from the source data. It excludes
non-geographic toll-free and other unresolvable ranges. Number portability,
travel, and recent allocations mean inference can be wrong or missing. Record an
explicit recipient IANA timezone when available. Unknown entries skip safely.

Regenerate and review the diff when updating the source snapshot:

```bash
pip install phonenumbers==9.0.40
python scripts/build_npa_map.py
pytest -q
```

`phonenumbers` is a regeneration dependency only; runtime lookups need no network
or additional phone-number package.
