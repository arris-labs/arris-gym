# CadQuery profiles and through cuts

`uv run --locked tools/cq_profile_probe.py` writes `constructed.json` on
CadQuery 2.3.0 and OCP 7.9.3.0, in the synced oracle environment
(`uv sync --locked --project tools/oracle`). Each row holds the program
and its status, exception text, measures, program SHA-256 and versions.
`tests/test_profile_probe.py` checks the records offline. It compares
volume, area, centroid and bounds with ADR-0005's agreement tolerance
and asserts the number of solids separately.

The probe records measures to 12 decimal places and leaves out the STEP
hash, STEP text and wall-clock time. Across zygote runs the raw 45° slot
centroid varied by about 3e-18 and one translated slot's STEP hash
varied. These are the kinds of variation recorded in BACKLOG Findings
`oracle-nondeterministic-step`. The closed forms and the agreement
tolerance are the same for all recordings.

## Through cuts

The stock is a 10 × 8 × 4 box about the origin, with volume 320 and
area 304. A cut wholly inside its footprint, of section area A and
perimeter P, removes a volume 4A at the section's centre of mass and
changes surface area by 4P − 2A. The remaining centroid is the stock's
first moment less the cut's, divided by the remaining volume.

| Cases | Construction |
| --- | --- |
| `through-on-face`, `through-inside`, `through-above`, `through-below` | A unit bore at (1, −2) goes through the full four units from planes at z = 2, 1, 5 and −5. |
| `through-compound` | Two boxes centred at z = 0 and 8. One unit bore from z = 3 goes through both. The result has two solids and its centroid stays at (0, 0, 4). |
| `through-miss` | The bore at x = 8 lies outside the stock. The box is unchanged. |
| `through-overhang` | A 4 × 2 profile at x = 5 clips to x ∈ [3, 5], y ∈ [−1, 1]. The notch removes 16 cubic units at (4, 0, 0), removes eight square units from the caps and eight from the +X side, and adds 24 on its three inside walls. |
| `through-side` | A unit bore along X removes 10π at (0, 1, −½). The separate regression fixture records the oracle's measure error. |
| `through-polygon` | A four-sided polygon of diameter 4 is a diamond with area 8 and perimeter 8√2. |
| `through-path` | The closed triangle has area 3, perimeter 5 + √13 and centroid (0, −⅓). |
| `through-circles-at-points`, `through-rects-at-points` | Two radius-½ bores at (−3, −1) and (2, 2), or four 2 × 1 windows at x = ±2, y = ±1.5. The sections are disjoint. |
| `through-ring`, `blind-ring-through-depth` | The annulus at (1, −1) has area 3π and perimeter 6π. An annular cut through the stock should leave the box around the hole and the inner solid. `cutBlind(-5)` builds those two solids. `cutThruAll()` raises `Standard_OutOfRange` on the same wires. |
| `through-no-solid`, `through-no-wires`, `through-no-solid-or-wires` | The solid is looked for first. A solid with no pending wires raises “No pending wires present”. |

## Rectangle and circle profiles

A prism of depth 2, area A and perimeter P has volume 2A and surface
area 2A + 2P. In the six `rect-on-*` and `circle-on-rect*` cases both
wires are centred at (1, −2). A 6 × 4 rectangle contains either a
2 × 1 rectangle or a unit circle. A radius-3 circle contains a 2 × 1
rectangle. The section area is outer less inner and the perimeter is
their sum, in either wire order.

Adjacent 2 × 2 squares sharing an edge make a 4 × 2 rectangle at (1, 0).
With one unit of overlap they make a 3 × 2 rectangle at (½, 0). Both forms
extrude as one solid and cut a window of the union section. With only a
corner in common the extrusion retains two solids, each 2 × 2 × 2.

The 4 × 2 profile extrudes at the origin, a `moveTo` point or the
`center` point. Each negative dimension changes the wire's traversal
and the absolute dimensions give the same prism. A single zero
dimension makes an out-and-back line. The oracle reports one solid of
zero volume and two coincident side walls of area 2 × 2 or 4 × 2
each. Its volume centroid is the origin. Two disjoint 2 × 1 rectangles
extrude to two solids. The polar array places four at radius 3 and
turns each one through its own array angle, so the outer bounds in both
X and Y are ±4. The blind rectangular pocket at (1, −2) removes a
4 × 2 × 1 prism. Its floor replaces its one 4 × 2 opening and its
walls add area 12.

## Moving the centre

`center(2, -1)` puts a unit circle at (2, −1) even after `moveTo` or
`pushPoints`. A second `center(-1, 3)`, or a later `moveTo(-3, 4)`,
puts it at (1, 2) or (−1, 3), respectively. On the +X face the local
axes point along +Y and +Z. The call there adds a cylinder from x = 5
to 7, centred transversely at (1, −½). Its foot and the covered disc
on the stock cease to be outside faces. The centred 2 × 2 array bores
at x ∈ {−1, 3}, y ∈ {−2, 0}. A previously drawn radius-½ circle
remains at (−2, 1) when the centre moves. Adding a unit circle at
(2, −1) afterwards makes a second disjoint prism.

## Slots

The 6 × 2 profiles are 4 × 2 rectangles capped by two unit
semicircles. Their section area is 8 + π and perimeter is 8 + 2π.
The 0°, 45° and 90° extrusions have equal volume and surface area.
Their X and Y spans are (6, 2), (2 + 2√2, 2 + 2√2) and (2, 6).
A `moveTo` point translates one such prism and `pushPoints` makes
two. The 45° through slot is at (1, −1).

At length = diameter the straight edges shrink to points and
`slot2D` raises `StdFail_NotDone`. At length 2 and diameter 4 the two
semicircles cross. Each cap's signed integral is 4π − 8 and the four
wall lengths sum to 4π + 4. The oracle reports these measures for one
solid whose checker status is `invalid`.

`rect-contexts.json` records the calls refused on a single rectangle, a
rectangular array or a nested section, alongside their pinned oracle
reports. The programs start on the top workplane of the same stock.
`test_cq_rect.py` binds every report to its program and checks the
subset's refusal.

The slot fixtures under `cq/` use the same section area and perimeter.
Each polar slot is centred at (0, ±4), with its own axis at 120° or 300°.
Its X span is 4 and its Y half-span is 1 + √3. The diagonal slots at
(0, 0) and (−2, 2) have overlapping bounding boxes and a perpendicular
centreline separation of 2√2, greater than their diameter. The blind
slot is centred on the top face and cuts two units deep. The through-cut
array removes two full slots at (±2, 0). The slot revolved about Y starts
at X = 3 and spans X from 2 to 4. Pappus's theorem gives its volume and
area by multiplying the section area and perimeter by 6π.

`slot-contexts.json` records calls refused on a single slot or a slot array,
plus unsupported stacks and argument forms for `slot2D`. Its oracle reports
include an overlapping-slot blind cut that crashed. `test_cq_slot.py` binds
the reports to their exact programs and checks the subset's refusals.
