# Circular post tangent to a box cap

CAD-Recode validation stem `239` ends with arris's L5 checker reporting
intersecting loops on a cap. In this construction the base is a 31 × 16 × 25
box below XY, and the post is a radius-3, height-19 cylinder above it.
The post attaches to the cap over its full disc, tangent to the edge at
`(-7, -3, 0)`. The footprint removes as much box-cap area as the post's
top contributes. The centroid is the volume-weighted mean of the box and
cylinder centres.

`oracle.json` records the exact fixture program on CadQuery 2.3.0 and
Open CASCADE 7.9.3.0. Its shape passes the oracle's checker. arris 0.11.1
returns a body whose cap loops intersect.

Adapted from CAD-Recode validation by Danila Rukhovich, Elona Dupont,
Dimitrios Mallis, Kseniya Cherenkova, Anis Kacem and Djamila Aouada.
Revision `17d554bbc50a23de6cf6a742a3e0ed867f000153`.
[CC-BY-NC-4.0](https://creativecommons.org/licenses/by-nc/4.0/).

arris 0.12.0 builds the expected geometry.
