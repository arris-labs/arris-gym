# Bounds of a slot ending in the far rim fillet

This case is `spacer_ring_002522_s20260505` as written by [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD), `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)). It builds a ring 1.57 thick with outside radius 52.41, fillets both rims by 0.42, then cuts a slot of width 2.5 to an axial depth of 1.285.

The floor intersects the far rim fillets. The two candidates for greatest Y are the edge of the slot at full radius and the lip above the floor. The edge wins, giving `sqrt(52.41² − 1.25²) = 52.39509137314296`. Arris reports the full radius with padding. The committed oracle report gives the correct bound within ADR-0005, but its volume differs from the annular section integral by about `9.15e-7` relative. Arris's volume, area and centroid agree with the integral.
