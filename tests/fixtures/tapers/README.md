# Taper fixtures (ADR-0027)

The programs and recorded reports run through `tools/oracle_run.py` on
CadQuery 2.3.0 and Open CASCADE 7.9.3.0. Each report keeps the program's
digest. `test_cq_taper.py` checks the agreement tolerance of ADR-0005.
The independent expectations for the constructed solids use these forms.

- **disc-frustum** uses radii 2 and 1 with axial height 3. Its slant
  length is √10. The volume is 7π, area π(5 + 3√10) and centroid
  height 33/28. The lower disc supplies the widest extent.
- **square-draft** goes from side 4 to side 2 at axial height 2 with
  slant length √5. Its volume is 56/3, area 20 + 12√5 and centroid
  height 11/14. The larger square supplies the in-plane bounds.
- **disc-apex** and **disc-past-apex** have one radius-2 cap and height
  2. The second program requests more slant length in the negative
  direction. The cone stops at the apex. Its volume is 8π/3, total area
  π(4 + 2√8) and centroid one quarter of the way to the apex.

`contexts.json` records both signs of height and angle, a displaced
centre, named and rotated frames, carried and consumed profiles, stock
fusion, use of a drafted cap, a through hole, the upper-rim chamfer and
zero taper. It also records boundary angles, inner wires, a zero slant
length, an empty stack and profiles outside the nonzero taper subset.
The outward rectangular cases use section area
`width × depth + perimeter × spread + π × spread²` at outward offset
`spread`, because the corners are quarter discs. The edge fixture
`rounded-rims` covers the removal of internal cap edges from the solid's
edge selection.

`knob-prefix` and `tee-nut-tool` adapt `knob_000063_s20260506` and
`tee_nut_000012_s20260506`, respectively, from
BenchCAD/BenchCAD `code_gen` at revision
`5919f578ab09ec283603a082fab07c7639ab56eb` (CC-BY-4.0).
The knob's first and second drafts have the same centre and lie
along +X. The tee-nut tool lies below XY.
