# arris report

Over 17900 programs: 942 arris refusals, 100 arris bugs.

Licences: ` "CC-BY-4.0" `.
arris ` "0.10.0" `; numpy ` "2.3.4" `; oracle cadquery ` "2.3.0" `, OCP ` "7.9.3.0" `, Python ` "3.12.3" `.

## Refusals

### ` "OpDegenerateError" ` (653)

- 281x ` "degenerate result: an arc's circle crosses the revolve axis: a spindle torus" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f100, +f81, +f82)" `
- 2x ` "degenerate result: the faces touch along a curve interior to both result faces (+f100, +f83, +f84)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f100, +f83, +f93)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f107, +f89, +f90)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f107, +f89, +f99)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f108, +f89, +f90)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f108, +f90, +f100)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f109, +f91, +f101)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f109, +f91, +f92)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f109, +f92, +f93)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f110, +f92, +f102)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f110, +f92, +f93)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f110, +f93, +f94)" `
- 2x ` "degenerate result: the faces touch along a curve interior to both result faces (+f122, +f103, +f113)" `
- 2x ` "degenerate result: the faces touch along a curve interior to both result faces (+f122, +f105, +f106)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f129, +f110, +f111)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f129, +f110, +f120)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f130, +f111, +f112)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f130, +f111, +f121)" `
- 3x ` "degenerate result: the faces touch along a curve interior to both result faces (+f15, +f6, +f11)" `
- 65x ` "degenerate result: the faces touch along a curve interior to both result faces (+f15, +f6, +f7)" `
- 159x ` "degenerate result: the faces touch along a curve interior to both result faces (+f2, +f5)" `
- 61x ` "degenerate result: the faces touch along a curve interior to both result faces (+f3, +f8)" `
- 11x ` "degenerate result: the faces touch along a curve interior to both result faces (+f43, +f26, +f27)" `
- 5x ` "degenerate result: the faces touch along a curve interior to both result faces (+f43, +f26, +f36)" `
- 6x ` "degenerate result: the faces touch along a curve interior to both result faces (+f47, +f30, +f31)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f47, +f30, +f40)" `
- 10x ` "degenerate result: the faces touch along a curve interior to both result faces (+f48, +f31, +f32)" `
- 6x ` "degenerate result: the faces touch along a curve interior to both result faces (+f48, +f31, +f41)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f49, +f32, +f33)" `
- 2x ` "degenerate result: the faces touch along a curve interior to both result faces (+f82, +f65, +f66)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f84, +f66, +f67)" `
- 2x ` "degenerate result: the faces touch along a curve interior to both result faces (+f84, +f67, +f68)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f85, +f67, +f77)" `
- 2x ` "degenerate result: the faces touch along a curve interior to both result faces (+f85, +f68, +f69)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f88, +f70, +f71)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f89, +f71, +f72)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f89, +f71, +f81)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f90, +f72, +f82)" `
- 1x ` "degenerate result: the faces touch along a curve interior to both result faces (+f96, +f79, +f80)" `
- 4x ` "degenerate result: the faces touch along a curve interior to both result faces (+f96, +f79, +f89)" `
- 2x ` "degenerate result: the faces touch along a curve interior to both result faces (+f99, +f80, +f81)" `
- 3x ` "degenerate result: the result's shells would touch along an edge or at a vertex, which a solid does not hold (+v1)" `

### ` "OpInternalError" ` (207)

- 176x ` "kernel bug: the face arrangement is not a subdivision: a cycle of f8's arrangement does not turn once" `
- 3x ` "kernel bug: the face arrangement is not a subdivision: a hole of f9 lies inside no region" `
- 25x ` "kernel bug: the face arrangement is not a subdivision: a section edge of f0 ends at a node nothing else reaches" `
- 3x ` "kernel bug: the face arrangement is not a subdivision: a section edge of f38 ends at a node nothing else reaches" `

### ` "OpUnsupportedError" ` (82)

- 2x ` "no closed form for +f22 (plane surface) against +e64 (circle curve)" `
- 80x ` "no closed form for +f6 (plane surface) against +v0 (point)" `

## Bugs

- ` "lobed_knob_000072_s20260505" ` (be8882b2d1bb494ad4f454dff9eb9348f0286e46015e89adebf4799615103eb8): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000093_s20260505" ` (f6bf1209f7ff84746e5a0c0c8176b058506aff024926758da511cf9841d73448): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000115_s20260507" ` (8aeb5279ed261530ff19d9bf8df88e3e9c2fc1c6f3662eb51a5aa46b8715a793): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000135_s20260505" ` (1d9d5c8689d15fed5ae98edd05933be7e22171b761bc8c443adc27a4c19265df): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000203_s20260507" ` (6ea324f774228a4f8f1bb425665810270a06c0baa78b8c1415b1fa373e900943): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000266_s20260505" ` (0aff82ea3a4ea5b9f3e8509596e4b8a8a80dd505b4daf5773ade556fa0d61015): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000301_s20260505" ` (d3503948e7ea2deeb2763400abef5d1560afd81da6f31d3350f0b31830917964): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000354_s20260507" ` (4a9376291ec2552ea2616c7f8f68eae3ce6d60e8a90a6377a0090d53344a4b24): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000493_s20260505" ` (976980755bdc1e45a3ccd853770593e5befd8277faad20c4c0892637a3b19773): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000557_s20260507" ` (0fba835577e38d0345de9a51cd64618ae2cedf4ecd84304f57bbe6427b87694c): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000770_s20260505" ` (9b9d03b636fff91d6ee0229e348ae372105d0a1fe171b2e7fcea53bb7d9212c5): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000778_s20260505" ` (68c2e5bd829b2d68d3eb6f186d75ab82c66a359792ad8d12acc169edc80c0edc): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_000802_s20260505" ` (a80d063d122edd9016e7251c37db492b3bbff7bfcfbc6327bde8c3bb97a181b8): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001098_s20260505" ` (a169cd34f823a48e57cf66143056912e31a07434b3b91392efe426b47b27f76c): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001179_s20260505" ` (ba85275c47507113ad5fb4a459916c648ee551e8922019c7c1eebfd5bb586bc9): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001355_s20260505" ` (27aabcf92f8c85afc39c2a8ecd13e48950ed64eb0c1d7ffba5943babbb2c120c): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001494_s20260505" ` (196b062287c4ea0a390433387259b79f22f9caa106a33387e7b2501b06627a37): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001614_s20260505" ` (948ca5c6637fc61e0171ca9698c59eea4948cb06cd94f0397c8043ad0494d883): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001681_s20260505" ` (aa657a92ff5158c20ca80fa97678e429cdec94edd02f4882da60fc5a2ab5bf02): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001682_s20260505" ` (e1b384426b9e2f7a8a0ec52e56fc26061409fd74e562667112700bbcd4b6a555): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_001927_s20260505" ` (7d07a86af59e5453d93964aa99b97cc0cdf3c5437596fac136d4fc1c9589156f): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_002095_s20260505" ` (eec7670c1ec327cd4dc5d952bba5dda4cd4051ea7c027a58d86aade7388934d5): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_002911_s20260505" ` (64a65b58b25f45951f538a4244e696ac5a04d2690a00575bd0d0bd177a731271): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_003289_s20260505" ` (0f71dd06460b7f2a4af1c6761bed2b0f2c0be1fbd05d91be4d6d254925f5ba10): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_003522_s20260505" ` (4f53bd2657e51b66c0165dd4339252e6257f357016796bc6989edde02be1db0d): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_003729_s20260505" ` (6aceb1820fbad4706732005aa0fac2d27ffa4e6502b008e402ad605b11acad5d): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_003796_s20260505" ` (0d624359d7bcc14640f19e857bf3b5df114432f245b1cd413a41ffabc390f665): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_003835_s20260505" ` (c6a2dae145283a6cec0d9a468f80db48874ee8cbfe5e04dbbabf39299d43f4d0): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_003936_s20260505" ` (6ad192cc0d9c63d1803ad8475d6a46e007d7cb054ad68149d6762da4b9eb46ba): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_003960_s20260505" ` (0c17e03e857dd54a6188aacc4e0d9c6776ce0374d9fe1a8fe9e05e2b657b9e11): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_004139_s20260505" ` (c2e9fde9c01b60b683941da61884675f34ff7f4bd1fa432e81effefbca546082): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_004149_s20260505" ` (3cb7dedb0d50ee6fc59494509248625e0b35e0a5e4e2ca6577fb9e01f2438184): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_004155_s20260505" ` (552904e2485c45a37a70455cfae36752cc354071f252ea82b59bb887400b3e86): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_004519_s20260505" ` (3bdd811b2c7efdc838cf24a56903ca1e7a9632593c653da95d56cc5b01ee0df3): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_004639_s20260505" ` (b6f0404246b3fbce8cff8a16c00b99bac465f2148894e920ec7cb7abd4749854): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005024_s20260505" ` (e2b83482660ac7ba8a33a509af17bb020cce8b37c31872f2e7897c3219a2699e): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005070_s20260505" ` (51ad3f6255891d895633872da12e820f7ba14874754c29dfd72143c62fd15df5): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005141_s20260505" ` (400fdcd6f2dbb1457ec7a65c5818fed86f1589ddfd1ab8a453b0cd778ae393aa): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005143_s20260505" ` (c2467c4f8b60401a1ad6d56ae4b0fe170e79bb602f6caf4be1a09802caca9387): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005246_s20260505" ` (b3f74757f19d40b22ef0997fd1f2413641bfa6a50d87102bc65506bbcf449f15): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005580_s20260505" ` (c2719e70e5970e6fca019cf4f684da833508017ddf11d2df99c44f75d9dee3e6): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005764_s20260505" ` (48409ad9c4dabf1e8dc07ed397e52761e988a5e52e64320a159cbdf5d8966eee): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005850_s20260505" ` (f932acec65ae2a84664948aa2e8106f57191e518f834e446fc575069b6ddbf58): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005851_s20260505" ` (307f3fb4ba299176fe8f85bf1544195f59df48ddf529d3a463dc23ebd4194888): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_005879_s20260505" ` (edc55ae4eaa638dfe2a83826087d510a1a7f2c613dffa3d7ae831dd7b19e8358): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006048_s20260505" ` (8a9d0e65b0a79db02db0bcee0e1907a3ee9a4646b4f8c1f185ae1b038557a82d): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006073_s20260505" ` (ab04f6f86f16d60e4be59ae9ee062284c0c4a74a1777e9c50e164c38047d60ee): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006083_s20260505" ` (265a699ff91a8b998921757a86b63a35496dee955393367aad7cfa1024251480): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006219_s20260505" ` (5c062ef73a930bb16fedade88a922fd3ecc56375f63d575b8674051ad470e511): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006504_s20260505" ` (7a926c5a378fdd03bb144e3aed09ca4f8afe05bcdaacd42ce5ddeb1ab11e2145): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006592_s20260505" ` (e2c4918a4b2146c74740841f75721ad2a184b2e40fcade90739574c1292e4791): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006621_s20260505" ` (1d2e70661bc8146235930489a9f65d0ce0e77f601aac70a406f61f22a7db86a8): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006797_s20260505" ` (8cd3768b573b6cf00c7e8f54463e2a9b690d68926608ca8c9cdb1b25d98d0373): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006809_s20260505" ` (6e94215664c57f0ce5f07762e97cbead630f2cbef70554ba78557f4caddfd0ce): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_006833_s20260505" ` (b5d4cdfa8814e7db7a8cfb2a57624f28def05a4f7506e24c503dccb5569c83fd): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007069_s20260505" ` (47cf43ccf8bbafc2bd582adbc277807ccbab6a4fb165933d312572699176296c): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007094_s20260505" ` (3197bb12c64890a473e1621bb5bb14f5a68d3e0ee90e8981418483f0abc76aee): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007148_s20260505" ` (a77315fa9ca49d510336b5de015d288d44ea5ab3790bc2a89eb75f8e59a2b8ff): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007160_s20260505" ` (6dd042308478e71a1ba941dcc5b0386239877536cd82babc38513ca7570c1c89): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007247_s20260505" ` (ae6aa7cb3b21abce7b3e8a7b37f3f9e6a23c290b7b3bcb00ca2b2e1448931f8d): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007305_s20260505" ` (b95a94539ccd08d33192fd4ed99fcb8188c573585a4dc488183b8c3f2b49a73a): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007405_s20260505" ` (ce21e9184359f9771012bb188e94d065bf6c75427a612ae127229d6c2c86dabb): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007531_s20260505" ` (176cc5deb506f73d3d79a7edfa6631e9331dc2e54f6a74b6acdeb1cd4ca3bb7f): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007598_s20260505" ` (c451ccab61736dc72f6d5096c68584a62edd161d5882fd5aa1651b560f404164): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007612_s20260505" ` (e14746cccf976b5b384c59096c24272be8a0fe62bfba34368ad61e69320d08a0): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007687_s20260505" ` (475b652103bcb7697ec475748c48fa52599283cc83583645f83f9bd9a9f43a38): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007866_s20260505" ` (125b0208d858d0b68f80062702ba52692d36ef2b61eecdbbbfc2d8f4313adc04): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007888_s20260505" ` (01c5c3e62b49e887061d8c83846d37b9b6f8354d62fd61866cadf4e454923b90): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007894_s20260505" ` (4404489359dc3231512b786407734bda82d8a11cdaf2fa96fa62a2c31f21b5b9): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_007927_s20260505" ` (075018dcb3f0c9d651f105707217f30c03beb1bde7278575d5bc0a7edf5222cb): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008148_s20260505" ` (1798282b9e01752a8725ae097551be09580c77420ba263681ee47d1d92908657): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008268_s20260505" ` (f6cebaa546ad1a267cfe16ab692d3fc166c863b084d16c66909802bb9457f520): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008277_s20260505" ` (7b77a808d1e9c68f8df4748462147b36d7947ee52187fa3bb80aeddcc8e8e244): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008466_s20260505" ` (a029939c8c47160ad7dd851bda2de3abf466d5f873675e372dd925a4139ff8e2): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008476_s20260505" ` (ff1ea9c9bcf3effd888aedda4491a26040973f611d1f1117afaecdb1d57c6b90): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008617_s20260505" ` (824a124a51c2ea6a0120a6eeabfa02e533477def51df928c0e7cf0b9858ac300): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008661_s20260505" ` (2f018d24cea29f987aa4ba21737a483e26020c4ad6bbb1d2425139500623ef5f): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008667_s20260505" ` (216ca4c6c44c752f32dc247aafde8da1e6b0fb9d24de588a950762609934fc0e): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008970_s20260505" ` (21846d16aa6996abf2d51e05f24bc81ed343f030e4a46d8a2b696213456e0607): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008996_s20260505" ` (e8d84c2b08def8afd800e37fe199e8bda62b54fa8e23bef3dee3b07f2a75f826): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_008999_s20260505" ` (71a083557c0b936d2e63286d4597f48c18701253cebf861f50b0306af9f4ed71): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_009086_s20260505" ` (103ad5c3128d175dd941b770870b00292dbb8b1ab2bb1ebe0c38bcbd8f39cb34): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_009192_s20260505" ` (9e5468599dd8cd99f3a128166c96d0213bd17497d5d90bac4fc2c9bc69e8cbc9): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_009461_s20260505" ` (d508c87d505b4dac0dbae3deff15ab7c501ce3c65d7fa159886cee3cfaf1484b): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_009549_s20260505" ` (f38048868a91f68f03236ed9f7f6d5e8bac72aae8421fc897422be8fa3fa5b2e): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_009650_s20260505" ` (be327cfa3bf278dde7b42f8fdb5b0ac8d0bd07d0d6a7886b5b4bad530865df9e): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_009876_s20260505" ` (cb570ebef0aa7c9131c9b2ef3b516e9159c02e5d7a6b9a506cd5c1b71e01ad8c): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010044_s20260505" ` (8cd9171abdd21191ec688834b2e8daf73691483b71be5b2e95541c25c5a2dd47): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010134_s20260505" ` (9364b31404b8bab9259ef18b7435f6117d986ef0374ecd04218a945e56828820): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010160_s20260505" ` (c48c3056b102fbf877382839ced9a67ddc0c36f868abadbe37a0fd0bc6f47583): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010321_s20260505" ` (9cfc2ec3efb6d7d81b42bca60a8050d6a2d9e0ee491a5fa659062b35f40d366f): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010389_s20260505" ` (5772f7449c680112ef7bf84f0ca13b5c806dc93c4f169b19c22352c5a7cb9b63): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010447_s20260505" ` (035a7aa6736d7ffd086368641a96904dfc97a9cc2b6fce68cd878e5253add841): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010465_s20260505" ` (9cf87d7a37f88d7c0ae0bbceb85021742f1a03243c571704adf7616a692686c0): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010701_s20260505" ` (d43db0c1e4fb59446dc68cd91d81c56825f84ded962d2a63087ecc277dd3379d): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_010791_s20260505" ` (51c534dd69983293723b1ce834b603608695f73ddf684f5ea059306d631d59ac): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_011295_s20260505" ` (16b07dc50dfdfc33b4a20276e0957927bda1ebb2e33382ab64220b4b3bec7bfe): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_011510_s20260505" ` (47a1fcfa7a9a947f011410da25bdfd76337c0b300b2bd05ab7e9e804a37f7e7a): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_011521_s20260505" ` (e6c9b3feb787a54242f7f1a1ea726963a7deb44f0c310e57eb3f02cd17606162): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
- ` "lobed_knob_011564_s20260505" ` (4bf823261f1290b94b3cf85040986429cfe2d162f00b679817a430116078c1e4): arris arris_refusal, oracle ok, fixture ` "tests/fixtures/regression/cq-union-three-coplanar-cylinders" `
