# `reward` fixtures

Each `<slug>/` holds two programs under the dialect `expected.json` names:
`program.py` builds the candidate, `target.py` the target. `expected.json`
gives the IoU from how the two parts were built (`note` says how) and the
route that must answer it at a budget the exact route needs no more than.
`sample_union_fraction` is the share of the box holding both parts that
their union fills, also from the construction: the sampled route's points
inside either part number about that share of all of them, which sets the
standard error its estimate is held to.
`cone-shifted` has no closed form: the kernel refuses the pair, and only its
route and the range of its IoU are held.
